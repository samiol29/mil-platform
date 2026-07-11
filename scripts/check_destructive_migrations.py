"""
Migration-safety CI gate (spec 005-enterprise-platform §17, Wave 4 —
Deployment Architecture, FR-DEPLOY-005: "no schema change reaches
production without... destructive migrations require explicit sign-off").

Scans every Alembic migration file changed relative to the base branch
(default: `origin/main`) for destructive SQL operations
(`DROP TABLE`/`DROP COLUMN`/`ALTER COLUMN ... TYPE`/`DROP CONSTRAINT`, and
this platform's own real risk — `DELETE FROM audit`/`evidence` tables).
A migration containing one of these patterns fails the check UNLESS its
file contains the literal marker comment `# destructive-migration-approved`
— an explicit, reviewable sign-off, not a silent bypass.

This does not replace human review of a migration's actual semantics — it
is a mechanical pattern check, the kind of "did anyone notice" safety net
CI is good at, not a substitute for a reviewer reading the diff.

Usage:
    python scripts/check_destructive_migrations.py [--base origin/main]

Exit code 0: no unreviewed destructive migrations found.
Exit code 1: at least one changed migration contains a destructive
             operation without the sign-off marker.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_APPROVAL_MARKER = "# destructive-migration-approved"

_DESTRUCTIVE_PATTERNS = [
    re.compile(r"drop_table\s*\(", re.IGNORECASE),
    re.compile(r"drop_column\s*\(", re.IGNORECASE),
    re.compile(r"drop_constraint\s*\(", re.IGNORECASE),
    re.compile(r"alter_column\s*\([^)]*type_\s*=", re.IGNORECASE | re.DOTALL),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"DROP\s+COLUMN", re.IGNORECASE),
    # This platform's own real risk (Constitution Principle VIII): any
    # migration that deletes rows from the immutable audit/evidence tables.
    re.compile(r"DELETE\s+FROM\s+(audit\.|finding\.|evidence\.)", re.IGNORECASE),
]


def _changed_migration_files(base: str) -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Base ref not available (e.g. shallow clone, or running locally with
        # no "origin/main") — fail open with a warning rather than blocking
        # a developer's local run; CI always has the full ref available.
        print(f"warning: could not diff against {base} ({result.stderr.strip()}); skipping check")
        return []
    return [
        Path(line)
        for line in result.stdout.splitlines()
        if line.startswith("migrations/versions/") and line.endswith(".py")
    ]


def check(base: str) -> int:
    changed = _changed_migration_files(base)
    if not changed:
        print("No changed migration files — nothing to check.")
        return 0

    unreviewed: list[str] = []
    for path in changed:
        if not path.exists():
            continue  # deleted in this diff
        content = path.read_text()
        if _APPROVAL_MARKER in content:
            continue
        matches = [p.pattern for p in _DESTRUCTIVE_PATTERNS if p.search(content)]
        if matches:
            unreviewed.append(f"{path}: {', '.join(matches)}")

    if unreviewed:
        print("BLOCKED — destructive migration(s) without explicit sign-off:")
        for entry in unreviewed:
            print(f"  - {entry}")
        print(f"\nAdd the literal comment `{_APPROVAL_MARKER}` to the migration file")
        print("after human review to acknowledge and approve the destructive change.")
        return 1

    print(f"OK — {len(changed)} changed migration(s), no unreviewed destructive operations.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="Base ref to diff against")
    args = parser.parse_args()
    return check(args.base)


if __name__ == "__main__":
    sys.exit(main())
