"""
Query Ports — consumer-owned, read-only cross-context interfaces (ADR-010).

These are the *read* interfaces the Copilot bounded context needs in order to
synchronously assemble an application-scoped grounding set for explainability.
They are declared here, inside the consuming context, expressing exactly the
reads Copilot requires — no more (Interface Segregation + Dependency Inversion).

Architectural rules (ADR-010):

- **Read-only.** Every method returns data; none mutates state, emits a domain
  event, or writes to the outbox.  Query Ports MUST NEVER be used for
  transactional business logic — any state change flows through domain services
  and Domain Events, never through a port.
- **Consumer-owned.** The interfaces belong to Copilot, not to the producing
  contexts.  The Finding/Policy/Review/etc. contexts remain unaware of Copilot.
- **No repository imports.** This module imports only from the Python standard
  library and ``mil.kernel``.  It does NOT import ``mil.finding``,
  ``mil.policy``, ``mil.review``, ``mil.evidence``, ``mil.document``,
  ``mil.application``, or ``mil.audit``.  Concrete adapters that satisfy these
  ports are wired ONLY in the composition root and are NOT implemented here.

The return types are Copilot-owned, read-only *view* value objects.  They
duplicate only the minimal fields Copilot needs (Principle V least-data) and
carry through provenance/attribution (Principles II, III, XII) so that a
Copilot response can cite and explain a record without importing the producing
context's internal model.

This module is architecture preparation only: it defines interfaces and view
shapes.  It contains no adapters, no persistence, no wiring, and no Copilot
service.  Those belong to Sprint 7.

Dependency rule: imports only ``mil.kernel`` types and the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime
    from uuid import UUID

# ---------------------------------------------------------------------------
# Read-only view value objects (consumer-owned)
#
# Each view is the minimal, detached, read-only projection of a producing
# context's record that Copilot needs for grounding, citation, and
# explanation.  They are plain frozen dataclasses — not ORM models, not
# persistence.  Adapters (Sprint 7, composition root) map a producing
# context's row onto the corresponding view.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplicationView:
    """Minimal read view of a mortgage application."""

    id: UUID
    tenant_id: UUID
    status: str
    created_at: datetime


@dataclass(frozen=True)
class DocumentView:
    """Minimal read view of a submitted source document."""

    id: UUID
    application_id: UUID
    document_type: str
    filename: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class DocumentTextView:
    """
    Read view of a document's persisted raw extracted text (Output 1 of the
    Document Intelligence pipeline — the OCR/document-understanding stage).

    Distinct from ``DocumentView`` (upload metadata): this carries the actual
    transcribed content so Copilot can ground free-form questions (e.g.
    "summarize this mortgage") that a structured ``EvidenceView`` fact alone
    cannot answer, while remaining resolvable back to its source document for
    citation.
    """

    document_id: UUID
    provider_version: str
    page_count: int
    full_text: str
    processed_at: datetime


@dataclass(frozen=True)
class EvidenceView:
    """
    Read view of a provenance-bearing evidence fact.

    Carries the Principle II provenance attributes so a Copilot citation can
    point at the exact source (document, page, field) and extraction lineage.
    """

    id: UUID
    application_id: UUID
    document_id: UUID
    evidence_type: str
    value_text: str
    confidence: float
    page_number: int
    field_location: str | None
    extraction_method: str
    extraction_model_version: str
    extracted_at: datetime


@dataclass(frozen=True)
class FindingView:
    """
    Read view of an AI-generated finding.

    Carries the five explainability fields (Principle III) and the versioned
    attribution (Principle XII) so Copilot can explain *what/why/evidence/
    confidence/action* and cite the exact model/prompt/extraction versions.
    """

    id: UUID
    application_id: UUID
    finding_type: str
    title: str
    rationale: str
    evidence_summary: str
    confidence_label: str
    recommended_action: str
    model_version: str
    prompt_version: str
    extraction_version: str
    created_at: datetime


@dataclass(frozen=True)
class PolicyResultView:
    """Read view of a single policy evaluation result for a finding."""

    id: UUID
    finding_id: UUID
    policy_version: str
    rule_ref: str
    status: str
    rationale: str
    evaluated_at: datetime


@dataclass(frozen=True)
class ReviewSessionView:
    """Read view of a human review session for a finding."""

    id: UUID
    finding_id: UUID
    application_id: UUID
    status: str
    assigned_reviewer_id: UUID | None
    created_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True)
class ReviewActionView:
    """
    Read view of a single, immutable review action (including overrides).

    Carries full attribution (Principle VIII): actor, prior/new status,
    reason, and — for overrides — previous and new value.
    """

    id: UUID
    review_session_id: UUID
    action_type: str
    actor_user_id: UUID | None
    actor_type: str
    previous_status: str
    new_status: str
    reason: str | None
    previous_value: str | None
    new_value: str | None
    created_at: datetime


@dataclass(frozen=True)
class ReviewCommentView:
    """Read view of a single immutable review comment."""

    id: UUID
    review_session_id: UUID
    author_user_id: UUID
    comment_text: str
    created_at: datetime


@dataclass(frozen=True)
class AuditEventView:
    """
    Read view of an immutable audit event.

    Supports "search an application's history" and audit-friendly explanations
    without granting Copilot any write access to the audit log.
    """

    id: UUID
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_id: UUID | None
    actor_type: str
    occurred_at: datetime
    event_data: Mapping[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Query Ports (read-only Protocols)
#
# Structural interfaces.  A concrete adapter (Sprint 7, composition root) that
# wraps the corresponding producing-context read repository will satisfy each
# Protocol.  Nothing here imports or references those repositories.
# ---------------------------------------------------------------------------


class ApplicationReader(Protocol):
    """Read port over the Application context."""

    def get_by_id(self, application_id: UUID) -> ApplicationView | None: ...


class DocumentTextReader(Protocol):
    """Read port over a document's persisted raw extracted text."""

    def get_for_application(self, application_id: UUID) -> Sequence[DocumentTextView]: ...


class DocumentReader(Protocol):
    """Read port over the Document context."""

    def get_for_application(self, application_id: UUID) -> Sequence[DocumentView]: ...


class EvidenceReader(Protocol):
    """Read port over the Evidence context."""

    def get_for_application(self, application_id: UUID) -> Sequence[EvidenceView]: ...


class FindingReader(Protocol):
    """Read port over the Finding context."""

    def get_for_application(self, application_id: UUID) -> Sequence[FindingView]: ...

    def get_by_id(self, finding_id: UUID) -> FindingView | None: ...


class PolicyResultReader(Protocol):
    """Read port over the Policy context."""

    def get_for_finding(self, finding_id: UUID) -> Sequence[PolicyResultView]: ...


class ReviewReader(Protocol):
    """Read port over the Review context."""

    def get_session_for_finding(self, finding_id: UUID) -> ReviewSessionView | None: ...

    def get_actions_for_session(self, review_session_id: UUID) -> Sequence[ReviewActionView]: ...

    def get_comments_for_session(self, review_session_id: UUID) -> Sequence[ReviewCommentView]: ...


class AuditReader(Protocol):
    """Read port over the Audit context."""

    def get_for_application(self, application_id: UUID) -> Sequence[AuditEventView]: ...
