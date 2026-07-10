"""
Deterministic large-dataset seed script for the Underwriter Workspace (spec 002).

Generates a configurable number (default 100,000) of ``core.applications`` rows,
each with at least one ``core.parties`` APPLICANT row carrying a realistic
synthetic borrower name, plus a realistic ``loan_number`` and ``los_reference``,
a status drawn from a realistic operational distribution, and ``created_at`` /
``updated_at`` timestamps spread over the last several months so the frontend's
derived SLA-age indicator (spec 002 FR-021) has a realistic range to render
against.

Purpose (tasks.md T126, resolves post-analysis finding G1): User Story 2
("Locate Applications Without Technical Identifiers") requires searching a
100,000+-row queue by borrower name, loan number, or LOS reference and
confirming a newest-first default ordering and sub-2-second search latency —
none of which is testable without a dataset at that scale. This script is the
sole source of that dataset, reused by:

- Playwright E2E (``frontend/e2e/search-queue.spec.ts``,
  ``frontend/e2e/performance/queue-scale.spec.ts``,
  ``frontend/e2e/saved-views.spec.ts``) via a subprocess invocation from
  Playwright global setup;
- manual QA, run directly from the command line.

Determinism: every value is derived from a single seeded ``random.Random``
instance (default seed 20260706). The same ``--seed``/``--count`` combination
always produces byte-identical rows (including UUIDs), so a test run against
this data is reproducible across machines and CI runs.

Design notes:

- This script writes directly via SQLAlchemy Core bulk ``insert()`` against
  the ``MortgageApplication`` and ``Party`` tables, not through
  ``ApplicationService`` / the aggregate. At 100,000+ rows, going through the
  aggregate (with its domain-event bookkeeping and audit-write-per-row) is
  neither necessary nor performant for bulk fixture data. Audit events are
  intentionally not written for seeded rows for the same reason — this is
  synthetic fixture data, not a real reviewable business event stream.
- The dev-bearer identity user (``core.users`` row matching
  ``DevBearerIdentityProvider``) is seeded first (idempotent) so
  ``created_by`` satisfies its foreign key and E2E/manual QA can browse the
  seeded data as the built-in dev principal.
- Borrower names are entirely synthetic (drawn from fixed first/last name
  pools, deterministically combined) — no real personal data is generated or
  stored, consistent with the platform's non-PII display_name convention.

Usage::

    python scripts/seed_large_dataset.py                       # 100,000 rows, default seed
    python scripts/seed_large_dataset.py --count 5000 --seed 7  # smaller run, different seed
    python scripts/seed_large_dataset.py --reset                # truncate this tenant's rows first
"""

from __future__ import annotations

import argparse
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, delete, insert
from sqlalchemy.orm import sessionmaker

from mil.application.models import ApplicationStatus, MortgageApplication, Party, PartyType
from mil.identity.dev_seed import seed_development_identity
from mil.identity.provider import DEV_TENANT_ID, DEV_USER_ID
from mil.kernel.config import get_settings

DEFAULT_SEED = 20260706
DEFAULT_COUNT = 100_000
BATCH_SIZE = 2_000

# Realistic operational status distribution: a live underwriting queue skews
# toward in-flight and completed applications, with a smaller long tail of
# fresh drafts and withdrawals.
_STATUS_WEIGHTS: list[tuple[str, float]] = [
    (ApplicationStatus.DRAFT, 0.08),
    (ApplicationStatus.SUBMITTED, 0.14),
    (ApplicationStatus.IN_REVIEW, 0.28),
    (ApplicationStatus.REVIEW_COMPLETE, 0.42),
    (ApplicationStatus.WITHDRAWN, 0.08),
]

# Fixed, synthetic name pools — no real individuals. Deterministically
# combined to produce a large, realistic-looking set of distinct borrower
# names for name-search testing.
_FIRST_NAMES: list[str] = [
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "John",
    "Jennifer",
    "Michael",
    "Linda",
    "David",
    "Elizabeth",
    "William",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
    "Christopher",
    "Nancy",
    "Daniel",
    "Lisa",
    "Matthew",
    "Margaret",
    "Anthony",
    "Betty",
    "Mark",
    "Sandra",
    "Donald",
    "Ashley",
    "Steven",
    "Emily",
    "Paul",
    "Kimberly",
    "Andrew",
    "Donna",
    "Joshua",
    "Michelle",
    "Kenneth",
    "Carol",
    "Kevin",
    "Amanda",
    "Brian",
    "Melissa",
    "George",
    "Deborah",
    "Edward",
    "Stephanie",
    "Ronald",
    "Rebecca",
    "Timothy",
    "Sharon",
    "Jason",
    "Laura",
    "Jeffrey",
    "Cynthia",
    "Ryan",
    "Kathleen",
    "Amy",
    "Jacob",
    "Angela",
    "Gary",
    "Nicholas",
    "Shirley",
    "Eric",
    "Anna",
    "Jonathan",
    "Ruth",
    "Stephen",
    "Brenda",
    "Larry",
    "Pamela",
    "Justin",
    "Nicole",
    "Scott",
    "Katherine",
    "Brandon",
    "Samantha",
]
_LAST_NAMES: list[str] = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
    "Walker",
    "Young",
    "Allen",
    "King",
    "Wright",
    "Scott",
    "Torres",
    "Nguyen",
    "Hill",
    "Flores",
    "Green",
    "Adams",
    "Nelson",
    "Baker",
    "Hall",
    "Rivera",
    "Campbell",
    "Mitchell",
    "Carter",
    "Roberts",
    "Gomez",
    "Phillips",
    "Evans",
    "Turner",
    "Diaz",
    "Parker",
    "Cruz",
    "Edwards",
    "Collins",
    "Reyes",
    "Stewart",
    "Morris",
    "Morales",
    "Murphy",
    "Cook",
    "Rogers",
    "Gutierrez",
    "Ortiz",
    "Morgan",
    "Cooper",
    "Peterson",
    "Bailey",
]


@dataclass(frozen=True)
class _SeededRow:
    application_id: uuid.UUID
    loan_number: str
    los_reference: str
    status: str
    created_at: datetime
    updated_at: datetime
    borrower_name: str
    include_co_applicant: bool


def _weighted_status(rng: random.Random) -> str:
    roll = rng.random()
    cumulative = 0.0
    for status, weight in _STATUS_WEIGHTS:
        cumulative += weight
        if roll <= cumulative:
            return status
    return _STATUS_WEIGHTS[-1][0]


def _deterministic_uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(bytes=rng.randbytes(16), version=4)


def _generate_rows(*, count: int, seed: int) -> list[_SeededRow]:
    """Deterministically generate ``count`` rows from a seeded RNG."""
    rng = random.Random(seed)
    now = datetime.now(UTC)
    rows: list[_SeededRow] = []
    for n in range(count):
        # Spread creation across the last ~180 days, and let updated_at land
        # anywhere between creation and now — this gives the frontend's
        # derived SLA-age indicator (on-track / at-risk / overdue) a realistic
        # spread to render against.
        age_days = rng.uniform(0, 180)
        created_at = now - timedelta(days=age_days)
        updated_at = created_at + timedelta(days=rng.uniform(0, max(age_days, 0.01)))
        first = rng.choice(_FIRST_NAMES)
        last = rng.choice(_LAST_NAMES)
        rows.append(
            _SeededRow(
                application_id=_deterministic_uuid(rng),
                loan_number=f"{rng.randint(1_000_000_000, 9_999_999_999)}",
                los_reference=f"LOS-{n + 1:07d}",
                status=_weighted_status(rng),
                created_at=created_at,
                updated_at=updated_at,
                borrower_name=f"{first} {last}",
                include_co_applicant=rng.random() < 0.20,
            )
        )
    return rows


def _application_values(
    row: _SeededRow, *, tenant_id: uuid.UUID, created_by: uuid.UUID
) -> dict[str, object]:
    return {
        "id": row.application_id,
        "tenant_id": tenant_id,
        "los_reference": row.los_reference,
        "loan_number": row.loan_number,
        "status": row.status,
        "active_policy_pack_id": None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "created_by": created_by,
    }


def _party_values(row: _SeededRow) -> list[dict[str, object]]:
    parties = [
        {
            "id": uuid.uuid4(),
            "application_id": row.application_id,
            "party_type": PartyType.APPLICANT.value,
            "display_name": row.borrower_name,
            "created_at": row.created_at,
        }
    ]
    if row.include_co_applicant:
        parties.append(
            {
                "id": uuid.uuid4(),
                "application_id": row.application_id,
                "party_type": PartyType.CO_APPLICANT.value,
                "display_name": f"{row.borrower_name} (Co-Applicant)",
                "created_at": row.created_at,
            }
        )
    return parties


def run(
    *,
    count: int = DEFAULT_COUNT,
    seed: int = DEFAULT_SEED,
    tenant_id: uuid.UUID = DEV_TENANT_ID,
    created_by: uuid.UUID = DEV_USER_ID,
    reset: bool = False,
    batch_size: int = BATCH_SIZE,
) -> int:
    """
    Seed ``count`` deterministic applications (plus parties) for ``tenant_id``.

    Returns the number of application rows written. Idempotent per
    ``(seed, count)`` pair only when combined with ``reset=True`` — without
    reset, re-running with the same seed re-generates the same UUIDs and will
    raise a primary-key violation if those rows already exist, by design (it
    surfaces an accidental double-seed rather than silently duplicating).
    """
    settings = get_settings()
    engine = create_engine(settings.database_sync_url)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    seed_development_identity(factory)

    rows = _generate_rows(count=count, seed=seed)

    with factory() as session:
        if reset:
            application_ids = [r.application_id for r in rows]
            session.execute(delete(Party).where(Party.application_id.in_(application_ids)))
            session.execute(
                delete(MortgageApplication).where(MortgageApplication.id.in_(application_ids))
            )
            session.commit()

        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            session.execute(
                insert(MortgageApplication),
                [_application_values(r, tenant_id=tenant_id, created_by=created_by) for r in batch],
            )
            party_rows: list[dict[str, object]] = []
            for r in batch:
                party_rows.extend(_party_values(r))
            session.execute(insert(Party), party_rows)
            session.commit()

    engine.dispose()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed a deterministic large application dataset for User Story 2 testing."
    )
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of applications.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed (determinism).")
    parser.add_argument(
        "--tenant-id", type=str, default=str(DEV_TENANT_ID), help="Tenant UUID to seed under."
    )
    parser.add_argument(
        "--created-by",
        type=str,
        default=str(DEV_USER_ID),
        help="core.users.id to attribute rows to.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete this seed's rows (by their deterministic IDs) before inserting.",
    )
    args = parser.parse_args()

    written = run(
        count=args.count,
        seed=args.seed,
        tenant_id=uuid.UUID(args.tenant_id),
        created_by=uuid.UUID(args.created_by),
        reset=args.reset,
    )
    print(f"Seeded {written} applications (seed={args.seed}).")


if __name__ == "__main__":
    main()
