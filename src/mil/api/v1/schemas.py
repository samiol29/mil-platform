"""
Pydantic request and response DTOs for the MIL Platform REST API (v1).

All schemas use Pydantic v2.  Route handlers must not return domain model
objects directly — they must convert to a response schema before returning.

Schema → domain model coupling:
  The ``from_model`` classmethods accept the corresponding domain ORM objects
  (imported under ``TYPE_CHECKING`` to prevent runtime circular imports).
  The field mapping is explicit — no ``from_attributes`` magic — so that
  schema changes are always deliberate.

Dependency rule: imports domain model types under ``TYPE_CHECKING`` only.
No bounded context import appears at runtime.  Pydantic and standard library
only at runtime.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mil.kernel.types import Confidence

if TYPE_CHECKING:
    from mil.application.models import MortgageApplication, Party
    from mil.audit.models import AuditEvent
    from mil.copilot.models import CopilotResponse, CopilotSession
    from mil.document.models import Document
    from mil.evidence.models import EvidenceItem
    from mil.finding.models import Finding

# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Canonical error response body — mirrors ``APIErrorResponse``."""

    code: str
    message: str
    details: list[object] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Application schemas
# ---------------------------------------------------------------------------


class CreateApplicationRequest(BaseModel):
    """Request body for POST /v1/applications."""

    los_reference: str | None = Field(
        default=None,
        description="External LOS application identifier; may be provided later.",
        max_length=255,
    )
    loan_number: str | None = Field(
        default=None,
        description="Lender loan identifier, distinct from los_reference; may be provided later.",
        max_length=255,
    )


class ApplicationResponse(BaseModel):
    """Application resource representation."""

    id: UUID
    los_reference: str | None = None
    loan_number: str | None = None
    status: str
    active_policy_pack_id: UUID | None = None
    party_count: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, app: MortgageApplication) -> ApplicationResponse:
        parties: list[object] = list(app.parties) if app.parties is not None else []
        return cls(
            id=app.id,
            los_reference=app.los_reference,
            loan_number=app.loan_number,
            status=app.status,
            active_policy_pack_id=app.active_policy_pack_id,
            party_count=len(parties),
            created_at=app.created_at,
            updated_at=app.updated_at,
        )


class ApplicationListResponse(BaseModel):
    """Paginated application list."""

    items: list[ApplicationResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Party schemas
# ---------------------------------------------------------------------------


class AddPartyRequest(BaseModel):
    """Request body for POST /v1/applications/{id}/parties."""

    party_type: str = Field(
        description="Role the party plays: APPLICANT, CO_APPLICANT, GUARANTOR, CORPORATE_ENTITY.",
    )
    display_name: str = Field(
        description="Non-PII display label for this party (e.g. 'Primary Borrower').",
        min_length=1,
        max_length=255,
    )


class PartyResponse(BaseModel):
    """Party resource representation."""

    id: UUID
    application_id: UUID
    party_type: str
    display_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, party: Party) -> PartyResponse:
        return cls(
            id=party.id,
            application_id=party.application_id,
            party_type=party.party_type,
            display_name=party.display_name,
            created_at=party.created_at,
        )


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    """
    Document resource representation.

    ``document_type`` maps to ``Document.mime_type``.  In Sprint 3D the form
    field ``document_type`` (a business classification such as BANK_STATEMENT)
    is stored as ``mime_type`` on the domain model.  A dedicated
    ``document_type`` column will be added in a future sprint migration once
    the business classification taxonomy is finalised.

    ``evidence_item_count``, ``page_count``, ``ingestion_completed_at``, and
    ``ingestion_error`` reflect real pipeline outcome state persisted on
    ``Document`` by ``DocumentService.complete_processing`` /
    ``fail_processing`` — they remain at their defaults (``0`` / ``None``)
    while the document is PENDING or IN_PROGRESS.

    ``filename`` (``Document.original_filename``) was omitted from this
    schema when it was first written even though the column has always
    existed on the model — added here (additive-only, per Constitution
    Principle IX) because the Document Viewer (tasks.md T064/T066) has no
    other way to label which document is open.
    """

    id: UUID
    application_id: UUID
    party_id: UUID | None = None
    filename: str = Field(description="The originally uploaded file's name.")
    document_type: str = Field(
        description="Business document classification (e.g. BANK_STATEMENT, PAYSLIP)."
    )
    ingestion_status: str
    content_hash: str = Field(description="SHA-256 hex digest of the original file bytes.")
    uploaded_at: datetime
    uploaded_by: UUID
    evidence_item_count: int = 0
    page_count: int | None = None
    ingestion_completed_at: datetime | None = None
    ingestion_error: str | None = None

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, doc: Document) -> DocumentResponse:
        return cls(
            id=doc.id,
            application_id=doc.application_id,
            party_id=doc.party_id,
            filename=doc.original_filename,
            document_type=doc.mime_type,
            ingestion_status=doc.ingestion_status,
            content_hash=doc.content_hash,
            uploaded_at=doc.uploaded_at,
            uploaded_by=doc.uploaded_by,
            evidence_item_count=doc.evidence_item_count,
            page_count=doc.page_count,
            ingestion_completed_at=doc.ingestion_completed_at,
            ingestion_error=doc.ingestion_error,
        )


# ---------------------------------------------------------------------------
# Evidence schemas
# ---------------------------------------------------------------------------


class EvidenceItemResponse(BaseModel):
    """
    Evidence item resource representation.

    ``confidence`` is the platform-wide HIGH/MEDIUM/LOW band (``mil.kernel
    .types.Confidence``, the same fixed-threshold mapping every confidence
    score in the platform uses — never a per-endpoint reinterpretation),
    lower-cased to match the frontend's confidence-band vocabulary (spec
    003 FR-061). ``field_location``, ``page_number``, ``extraction_method``,
    ``extraction_model_version``, and ``extracted_at`` are five of the seven
    Constitution Principle II provenance attributes; ``document_id`` and
    ``application_id`` are the remaining two.
    """

    id: UUID
    application_id: UUID
    document_id: UUID
    party_id: UUID | None = None
    evidence_type: str
    value_text: str | None = None
    value_numeric: str | None = None
    currency: str | None = None
    page_number: int | None = None
    field_location: dict[str, object] | None = None
    confidence: str
    extraction_method: str
    extraction_model_version: str
    extracted_at: datetime
    supersedes_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, item: EvidenceItem) -> EvidenceItemResponse:
        return cls(
            id=item.id,
            application_id=item.application_id,
            document_id=item.document_id,
            party_id=item.party_id,
            evidence_type=item.evidence_type,
            value_text=item.value_text,
            value_numeric=str(item.value_numeric) if item.value_numeric is not None else None,
            currency=item.currency,
            page_number=item.page_number,
            field_location=item.field_location,
            confidence=Confidence(score=float(item.extraction_confidence)).label.lower(),
            extraction_method=item.extraction_method,
            extraction_model_version=item.extraction_model_version,
            extracted_at=item.extracted_at,
            supersedes_id=item.supersedes_id,
            created_at=item.created_at,
        )


# ---------------------------------------------------------------------------
# Finding schemas
# ---------------------------------------------------------------------------


class FindingResponse(BaseModel):
    """
    Finding resource representation — all five explainability fields
    (``what``, ``why``, ``evidence_refs``, ``confidence``,
    ``recommended_action``) and attribution fields (``model_version``,
    ``prompt_version``, ``extraction_version``, ``policy_version``) are
    always present, never optional (spec 002 FR-031, FR-051; Constitution
    Principle XII) — a Finding with any missing is a defect in the data
    layer, not a state this schema represents as absent.

    ``policy_version`` is resolved from ``policy.policy_results`` (joined
    on ``finding_id``, not stored on ``Finding`` itself) by the route
    handler and passed in explicitly.
    """

    id: UUID
    application_id: UUID
    what: str
    why: str
    evidence_refs: list[UUID]
    confidence: str
    recommended_action: str
    state: str
    model_version: str
    prompt_version: str
    extraction_version: str
    policy_version: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(
        cls,
        finding: Finding,
        *,
        state: str,
        policy_version: str | None,
    ) -> FindingResponse:
        return cls(
            id=finding.id,
            application_id=finding.application_id,
            what=finding.title,
            why=finding.rationale,
            evidence_refs=[UUID(i) for i in finding.evidence_item_ids],
            confidence=Confidence(score=float(finding.confidence_score)).label.lower(),
            recommended_action=finding.recommended_action,
            state=state,
            model_version=finding.model_version,
            prompt_version=finding.prompt_version,
            extraction_version=finding.extraction_version,
            policy_version=policy_version,
            created_at=finding.created_at,
        )


class VerifyFindingRequest(BaseModel):
    """Request body for POST /v1/findings/{id}/verify. Empty — verification needs no reason."""


class OverrideFindingRequest(BaseModel):
    """Request body for POST /v1/findings/{id}/override."""

    reason: str = Field(description="Why the finding is being overridden.", min_length=1)
    previous_value: str = Field(description="The finding's value before this override.")
    new_value: str = Field(description="The corrected value.", min_length=1)


# ---------------------------------------------------------------------------
# Audit schemas
# ---------------------------------------------------------------------------


class AuditEventResponse(BaseModel):
    """Read-only audit trail entry — no mutation affordance exists at any layer."""

    id: UUID
    application_id: UUID | None = None
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_id: UUID | None = None
    actor_type: str
    event_data: dict[str, object]
    occurred_at: datetime
    sequence_number: int | None = None

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, event: AuditEvent) -> AuditEventResponse:
        return cls(
            id=event.id,
            application_id=event.application_id,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            actor_id=event.actor_id,
            actor_type=event.actor_type,
            event_data=event.event_data,
            occurred_at=event.occurred_at,
            sequence_number=event.sequence_number,
        )


# ---------------------------------------------------------------------------
# Auth / System schemas
# ---------------------------------------------------------------------------


class CurrentUserResponse(BaseModel):
    """Response for GET /v1/me — the authenticated caller's identity."""

    user_id: UUID
    tenant_id: UUID
    roles: list[str]
    email: str
    display_name: str


class HealthResponse(BaseModel):
    """Response for GET /v1/health."""

    status: str = "ok"
    version: str = "1.0.0"
    environment: str = "development"
    uptime_seconds: float = 0.0


class ReadinessCheck(BaseModel):
    """One dependency check performed by GET /v1/ready."""

    name: str
    status: str = Field(description="'ok' or 'fail'.")
    detail: str | None = None


class ReadinessResponse(BaseModel):
    """Response for GET /v1/ready."""

    status: str = Field(description="'ready' or 'not_ready'.")
    checks: list[ReadinessCheck]


class LivenessResponse(BaseModel):
    """Response for GET /v1/live."""

    status: str = "alive"


class HistogramMetric(BaseModel):
    """Aggregate statistics for one histogram metric."""

    count: int
    sum: float
    average: float
    minimum: float
    maximum: float


class MetricsResponse(BaseModel):
    """Response for GET /v1/metrics."""

    counters: dict[str, float]
    histograms: dict[str, HistogramMetric]


# ---------------------------------------------------------------------------
# Copilot schemas (US2 Sprint 7C)
# ---------------------------------------------------------------------------


class CopilotQueryRequest(BaseModel):
    """Request body for POST /v1/copilot/query."""

    application_id: UUID
    session_id: UUID | None = Field(
        default=None,
        description=(
            "Existing Copilot session to resume. Omit to start a new session for this application."
        ),
    )
    question: str = Field(
        description="The reviewer's natural-language question.",
        min_length=1,
        max_length=2000,
    )


class CitationSchema(BaseModel):
    """A single citation grounding a Copilot response."""

    kind: str = Field(
        description=("APPLICATION, DOCUMENT, EVIDENCE, FINDING, POLICY_RESULT, or REVIEW_ACTION.")
    )
    ref: str = Field(description="Identifier of the cited governed record.")
    locator: str | None = Field(
        default=None, description="Optional finer-grained locator (e.g. a page or field)."
    )


class CopilotResponseSchema(BaseModel):
    """A grounded Copilot response to a single query."""

    id: UUID
    query_id: UUID
    session_id: UUID
    answer: str
    prompt_version: str
    model_version: str
    citations: list[CitationSchema]
    created_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, response: CopilotResponse, *, session_id: UUID) -> CopilotResponseSchema:
        return cls(
            id=response.id,
            query_id=response.query_id,
            session_id=session_id,
            answer=response.answer_text,
            prompt_version=response.prompt_version,
            model_version=response.model_version,
            citations=[CitationSchema(**citation) for citation in response.citations],
            created_at=response.created_at,
        )


class CopilotSessionResponse(BaseModel):
    """Copilot session resource representation."""

    id: UUID
    application_id: UUID
    tenant_id: UUID
    created_by_user_id: UUID
    correlation_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, session: CopilotSession) -> CopilotSessionResponse:
        return cls(
            id=session.id,
            application_id=session.application_id,
            tenant_id=session.tenant_id,
            created_by_user_id=session.created_by_user_id,
            correlation_id=session.correlation_id,
            created_at=session.created_at,
        )


class CopilotHistoryItem(BaseModel):
    """One query paired with its response (if any) in a session's history."""

    query_id: UUID
    question: str
    asked_by_user_id: UUID
    asked_at: datetime
    response: CopilotResponseSchema | None = None


class CopilotHistoryResponse(BaseModel):
    """Ordered query/response history for a Copilot session."""

    session_id: UUID
    items: list[CopilotHistoryItem]
