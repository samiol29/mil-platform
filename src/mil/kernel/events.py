"""
Canonical domain event definitions for the MIL Platform.

Domain events represent significant, irreversible state changes within a
bounded context.  They are the primary coordination mechanism between
bounded contexts: the entity that experiences the state change emits an
event; other bounded contexts subscribe to be notified and react.

Event design rules:
- Every event is an immutable frozen dataclass.
- Events carry enough data for subscribers to act without further queries.
- Every event records the tenant, correlation ID, and UTC occurrence time.
- Event names are past-tense facts: DocumentIngested, not DocumentIngest.
- Events are serialisable to plain dicts for broker transport and audit log.

The ``KW_ONLY`` sentinel on ``DomainEvent`` makes ``event_id``,
``occurred_at``, and ``correlation_id`` keyword-only in generated
``__init__`` signatures.  Subclass required fields remain positional, so
callers construct events naturally::

    event = DocumentIngested(
        tenant_id=tenant_id,
        document_id=doc_id,
        application_id=app_id,
        storage_reference="s3://...",
        content_hash="sha256:...",
    )

Dependency rule: this module imports from ``mil.kernel.types`` only.
No bounded context code should be imported here.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from mil.kernel.types import (
        ApplicationId,
        DocumentId,
        EvidenceItemId,
        FindingId,
        PolicyPackId,
        ReviewSessionId,
        TenantId,
        WorkflowRunId,
    )


# ---------------------------------------------------------------------------
# Internal helpers (not exported)
# ---------------------------------------------------------------------------


def _new_event_id() -> str:
    return str(uuid4())


def _now_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Base domain event
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class DomainEvent:
    """
    Immutable base class for all MIL domain events.

    The ``tenant_id`` field is a required positional argument.  The
    ``event_id``, ``occurred_at``, and ``correlation_id`` fields are
    keyword-only with auto-generated or empty defaults so subclass required
    positional fields can follow without violating Python's default-argument
    ordering rules.

    Equality and hashing are based on ``event_id`` alone.  Two event
    instances that share the same ``event_id`` represent the same occurrence
    (e.g. a republished event after a retry) and are considered identical.

    Subclasses MUST be frozen dataclasses and MUST NOT add mutable fields.
    """

    tenant_id: TenantId
    _: dataclasses.KW_ONLY
    event_id: str = dataclasses.field(default_factory=_new_event_id)
    occurred_at: datetime = dataclasses.field(default_factory=_now_utc)
    correlation_id: str = ""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DomainEvent):
            return NotImplemented
        return self.event_id == other.event_id

    def __hash__(self) -> int:
        return hash(self.event_id)

    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-safe plain dict suitable for broker transport."""
        result: dict[str, object] = {}
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if isinstance(value, UUID):
                result[f.name] = str(value)
            elif isinstance(value, datetime):
                result[f.name] = value.isoformat()
            elif isinstance(value, tuple):
                result[f.name] = [str(v) if isinstance(v, UUID) else v for v in value]
            else:
                result[f.name] = value
        result["event_type"] = type(self).__name__
        return result


# ---------------------------------------------------------------------------
# Document Processing events
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class DocumentIngested(DomainEvent):
    """
    Emitted when a document has been successfully stored and associated with
    a mortgage application.

    The Intelligence Orchestrator subscribes to this event to start the
    OCR and evidence extraction workflow.
    """

    document_id: DocumentId
    application_id: ApplicationId
    storage_reference: str
    content_hash: str
    document_name: str = ""


@dataclasses.dataclass(frozen=True, eq=False)
class OCRCompleted(DomainEvent):
    """
    Emitted when the OCR stage of the pipeline has produced and persisted a
    validated ``OCRResult`` for a document.

    The Intelligence Orchestrator (and, in a later sprint, the Extraction
    stage) subscribes to this event to advance the pipeline. ``provider_version``
    records which OCR engine produced the text, satisfying Principle XII; the
    persisted ``OCRResult`` is the deterministic, immutable source of truth.

    The ``correlation_id`` (inherited, keyword-only) carries the workflow run
    identity for end-to-end tracing (ADR-009).
    """

    document_id: DocumentId
    application_id: ApplicationId
    workflow_run_id: WorkflowRunId
    provider_version: str
    page_count: int


# ---------------------------------------------------------------------------
# Evidence Management events
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class EvidenceExtracted(DomainEvent):
    """
    Emitted when structured evidence items have been extracted from a document.

    The Intelligence Orchestrator subscribes to this event to trigger
    finding generation once all document evidence is available.

    ``evidence_item_ids`` is a tuple (immutable) of the IDs of every evidence
    item produced by this extraction pass.  ``extraction_version`` records the
    provider version that produced the evidence, required by Principle XII
    (Deterministic Intelligence).
    """

    document_id: DocumentId
    application_id: ApplicationId
    evidence_item_ids: tuple[EvidenceItemId, ...]
    extraction_version: str


# ---------------------------------------------------------------------------
# Finding Management events
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class FindingGenerated(DomainEvent):
    """
    Emitted when a new finding has been created for a mortgage application.

    ``finding_type`` is a short machine-readable classifier (e.g.
    ``"income_verification"``, ``"property_value"``).  ``policy_version``
    is the version string of the Policy Pack used to generate the finding,
    required by Principle XII.
    """

    finding_id: FindingId
    application_id: ApplicationId
    finding_type: str
    policy_version: str


@dataclasses.dataclass(frozen=True, eq=False)
class FindingStateChanged(DomainEvent):
    """
    Emitted when a finding transitions between lifecycle states.

    Examples: Extracted → NeedsReview, NeedsReview → Verified.
    ``changed_by_user_id`` is the string representation of the user ID
    responsible for the transition (empty for system-driven transitions).
    """

    finding_id: FindingId
    application_id: ApplicationId
    from_state: str
    to_state: str
    changed_by_user_id: str = ""


# ---------------------------------------------------------------------------
# Policy Evaluation events
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class PolicyEvaluated(DomainEvent):
    """
    Emitted when a Finding has been evaluated against a Policy Pack and the
    result has been persisted.

    US2 Sprint 5's minimal additive event (no ``PolicyEvaluated`` existed
    prior to this sprint). ``policy_pack_id`` and ``policy_version`` record
    the Policy Pack and provider version the evaluation ran under, required
    by Principle XII. ``outcome`` is the summary verdict (e.g. ``"PASS"``,
    ``"FLAGGED"``, ``"REJECTED"``).
    """

    finding_id: FindingId
    application_id: ApplicationId
    policy_pack_id: PolicyPackId
    policy_version: str
    outcome: str


# ---------------------------------------------------------------------------
# Review & Verification events
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class OverrideRecorded(DomainEvent):
    """
    Emitted when a human reviewer overrides an AI-generated finding.

    Engineering Constitution Principle I (Human Decision Authority) requires
    that every override is recorded with full attribution: the reviewer
    identity, the reason, and the before/after values.

    ``previous_value`` and ``new_value`` are string representations of the
    relevant finding attribute that was changed.
    """

    finding_id: FindingId
    application_id: ApplicationId
    reviewer_user_id: str
    override_reason: str
    previous_value: str = ""
    new_value: str = ""


@dataclasses.dataclass(frozen=True, eq=False)
class ReviewStarted(DomainEvent):
    """
    Emitted when a Review Session is created for a Finding, handing it off
    for human review (Engineering Constitution Principle I — Human Decision
    Authority).

    US2 Sprint 6's minimal additive event (no ``ReviewStarted`` existed prior
    to this sprint). The Review worker emits this immediately after creating
    the ``ReviewSession`` in response to ``PolicyEvaluated`` — it records that
    a human handoff occurred, not any decision outcome.
    """

    review_session_id: ReviewSessionId
    finding_id: FindingId
    application_id: ApplicationId


@dataclasses.dataclass(frozen=True, eq=False)
class ReviewCompleted(DomainEvent):
    """
    Emitted when the Review stage of the intelligence pipeline has completed
    its automated portion (the ``ReviewSession`` has been created and handed
    off) — Review is the final planned step of the ``FINDING_GENERATION``
    workflow (ADR-009).

    This is distinct from a human rendering a final verdict (approve, reject,
    override): those are recorded via ``ReviewSession``/``ReviewAction`` rows
    and, for overrides, via ``OverrideRecorded`` — asynchronously, outside the
    workflow's step machinery, whenever a reviewer acts. ``status`` reflects
    the session's status at the moment this event was emitted (``PENDING_REVIEW``
    unless a reviewer has already acted, e.g. under replay).

    US2 Sprint 6's minimal additive event (no ``ReviewCompleted`` existed
    prior to this sprint).
    """

    review_session_id: ReviewSessionId
    finding_id: FindingId
    application_id: ApplicationId
    status: str


# ---------------------------------------------------------------------------
# Orchestration events
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, eq=False)
class WorkflowStarted(DomainEvent):
    """
    Emitted when the Intelligence Orchestrator creates a new workflow run.

    Records the application the run coordinates and the workflow type
    (e.g. ``"DOCUMENT_INGESTION"``, ``"FINDING_GENERATION"``).  The pinned
    version set lives on the ``WorkflowRun`` itself (ADR-009); this event is a
    lifecycle signal, not the attribution record.

    The ``correlation_id`` (inherited, keyword-only) carries the workflow run
    identity so the whole pipeline execution can be reconstructed end-to-end
    (ADR-009, Principle X).
    """

    workflow_run_id: WorkflowRunId
    application_id: ApplicationId
    workflow_type: str


@dataclasses.dataclass(frozen=True, eq=False)
class WorkflowStepCompleted(DomainEvent):
    """
    Emitted when a single workflow step completes successfully.

    ``step_name`` identifies the step within the run; ``step_order`` is its
    position in the declared step sequence.  The orchestrator uses this signal
    to dispatch the next step (US2 Sprint 2+); in Sprint 1 it is a lifecycle
    fact recorded for observability.
    """

    workflow_run_id: WorkflowRunId
    step_name: str
    step_order: int = 0


@dataclasses.dataclass(frozen=True, eq=False)
class WorkflowCompleted(DomainEvent):
    """
    Emitted when every step of a workflow run has completed successfully and
    the run reaches its successful terminal state.

    The Intelligence Orchestrator emits this as the run's final lifecycle
    signal.  Downstream consumers must not infer completion from delivery
    order — they read it from this event and from workflow state.
    """

    workflow_run_id: WorkflowRunId
    application_id: ApplicationId
    workflow_type: str


@dataclasses.dataclass(frozen=True, eq=False)
class WorkflowStepFailed(DomainEvent):
    """
    Emitted when a workflow step fails after exhausting all retry attempts.

    The Intelligence Orchestrator subscribes to this event to trigger
    compensating actions and escalation to the Audit & Governance module.

    ``retry_count`` is the number of attempts that were made before the step
    was declared failed.  ``error_code`` is the platform error code string
    from ``ErrorCode`` (e.g. ``"PROVIDER_UNAVAILABLE"``).
    """

    workflow_run_id: WorkflowRunId
    step_name: str
    error_code: str
    error_message: str
    retry_count: int = 0
