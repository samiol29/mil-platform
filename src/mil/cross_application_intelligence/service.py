"""
Pure, domain-agnostic derivation functions for Cross-Application Intelligence
(spec 005-enterprise-platform §6, Wave 3).

Every function here takes plain input dataclasses and returns
``CrossApplicationObservation`` — never a bare score, always a citation of
which applications/documents/findings produced it (Principle III). None of
these functions has side effects, calls a repository, or checks
permissions; the caller (``mil.api.deps``'s composition class) is
responsible for RBAC and for assembling the inputs from real data.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class DocumentSignal:
    """A minimal, domain-agnostic view of a Document for reuse detection."""

    document_id: UUID
    application_id: UUID
    content_hash: str
    filename: str


@dataclass(frozen=True)
class FindingSignal:
    """A minimal, domain-agnostic view of a Finding for pattern detection."""

    finding_id: UUID
    application_id: UUID
    finding_type: str
    lifecycle_state: str


@dataclass(frozen=True)
class CrossApplicationObservation:
    """
    One observation about a borrower's history across applications.

    ``kind`` is a stable machine-readable category; ``description`` is the
    plain-language explanation of *why* this observation exists (never a
    bare score); ``application_ids``/``document_ids``/``finding_ids`` are
    the exact evidence a reviewer can click through to verify it.
    """

    kind: str
    description: str
    application_ids: tuple[UUID, ...]
    document_ids: tuple[UUID, ...] = ()
    finding_ids: tuple[UUID, ...] = ()


def find_reused_documents(documents: list[DocumentSignal]) -> list[CrossApplicationObservation]:
    """
    Group documents by ``content_hash``; a hash shared across more than one
    *application* (not just multiple rows in one application — that's a
    normal duplicate-upload case already handled by Phase 4.5's own
    duplicate-detection UI) is a real, evidence-backed reuse signal.
    """
    by_hash: dict[str, list[DocumentSignal]] = defaultdict(list)
    for doc in documents:
        by_hash[doc.content_hash].append(doc)

    observations: list[CrossApplicationObservation] = []
    for content_hash, group in by_hash.items():
        distinct_applications = {d.application_id for d in group}
        if len(distinct_applications) < 2:
            continue
        filenames = sorted({d.filename for d in group})
        observations.append(
            CrossApplicationObservation(
                kind="REUSED_DOCUMENT",
                description=(
                    f"The same document (hash {content_hash[:12]}…, "
                    f"filename(s): {', '.join(filenames)}) appears across "
                    f"{len(distinct_applications)} of this borrower's applications."
                ),
                application_ids=tuple(sorted(distinct_applications, key=str)),
                document_ids=tuple(d.document_id for d in group),
            )
        )
    return observations


def find_repeated_finding_types(findings: list[FindingSignal]) -> list[CrossApplicationObservation]:
    """
    Group findings by ``finding_type``; a type recurring across more than
    one application is a real, evidence-backed pattern — e.g. the same kind
    of discrepancy flagged on two separate applications for this borrower.
    """
    by_type: dict[str, list[FindingSignal]] = defaultdict(list)
    for finding in findings:
        by_type[finding.finding_type].append(finding)

    observations: list[CrossApplicationObservation] = []
    for finding_type, group in by_type.items():
        distinct_applications = {f.application_id for f in group}
        if len(distinct_applications) < 2:
            continue
        observations.append(
            CrossApplicationObservation(
                kind="REPEATED_FINDING_TYPE",
                description=(
                    f"Findings of type '{finding_type}' were generated on "
                    f"{len(distinct_applications)} of this borrower's applications "
                    f"({len(group)} finding(s) total)."
                ),
                application_ids=tuple(sorted(distinct_applications, key=str)),
                finding_ids=tuple(f.finding_id for f in group),
            )
        )
    return observations


def summarize_review_outcomes(findings: list[FindingSignal]) -> CrossApplicationObservation | None:
    """
    A single observation summarizing this borrower's review history across
    every linked application — real ``lifecycle_state`` counts, not a
    fabricated risk score. Returns ``None`` when there are no findings at
    all (nothing to summarize, not a zero-value observation).
    """
    if not findings:
        return None

    distinct_applications = {f.application_id for f in findings}
    counts: dict[str, int] = defaultdict(int)
    for finding in findings:
        counts[finding.lifecycle_state] += 1

    parts = ", ".join(f"{count} {state.lower()}" for state, count in sorted(counts.items()))
    return CrossApplicationObservation(
        kind="REVIEW_OUTCOME_SUMMARY",
        description=(
            f"Across {len(distinct_applications)} application(s), this borrower has "
            f"{len(findings)} finding(s): {parts}."
        ),
        application_ids=tuple(sorted(distinct_applications, key=str)),
        finding_ids=tuple(f.finding_id for f in findings),
    )
