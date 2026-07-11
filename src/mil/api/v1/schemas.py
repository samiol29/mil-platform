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
from typing import TYPE_CHECKING, Literal
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
    escalated_to_role: str | None = None
    escalated_to_user_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(
        cls,
        finding: Finding,
        *,
        state: str,
        policy_version: str | None,
        escalated_to_role: str | None = None,
        escalated_to_user_id: UUID | None = None,
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
            escalated_to_role=escalated_to_role,
            escalated_to_user_id=escalated_to_user_id,
            created_at=finding.created_at,
        )


class VerifyFindingRequest(BaseModel):
    """Request body for POST /v1/findings/{id}/verify. Empty — verification needs no reason."""


class OverrideFindingRequest(BaseModel):
    """Request body for POST /v1/findings/{id}/override."""

    reason: str = Field(description="Why the finding is being overridden.", min_length=1)
    previous_value: str = Field(description="The finding's value before this override.")
    new_value: str = Field(description="The corrected value.", min_length=1)


class EscalateFindingRequest(BaseModel):
    """Request body for POST /v1/findings/{id}/escalate (spec 002 FR-054)."""

    reason: str = Field(description="Why the finding is being escalated.", min_length=1)
    target_role: str = Field(
        description="The role this finding is being escalated to.", min_length=1
    )
    target_user_id: UUID | None = Field(
        default=None,
        description="Reserved for a future direct-assignment refinement; NULL means any holder of target_role.",
    )


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


# ---------------------------------------------------------------------------
# Enterprise Administration schemas (spec 005 §15)
# ---------------------------------------------------------------------------


class CreateUserRequest(BaseModel):
    """Request body for creating a platform user."""

    external_identity_id: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=1)
    display_name: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    """Platform user resource representation. Never returns ``email_hash`` raw."""

    id: UUID
    tenant_id: UUID
    display_name: str
    is_active: bool
    roles: list[str] = Field(default_factory=list)
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]


class AssignRoleRequest(BaseModel):
    """Request body for assigning a role to a user."""

    role_name: str = Field(min_length=1, max_length=100)


class RoleAssignmentResponse(BaseModel):
    id: UUID
    user_id: UUID
    role_id: UUID
    role_name: str
    assigned_by: UUID
    assigned_at: datetime
    revoked_at: datetime | None = None


class TenantConfigurationRequest(BaseModel):
    """Request body for setting a tenant configuration key."""

    config_value: dict[str, object]


class TenantConfigurationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    config_key: str
    config_value: dict[str, object]
    updated_by_user_id: UUID
    updated_at: datetime


class TenantConfigurationListResponse(BaseModel):
    items: list[TenantConfigurationResponse]


class CreateApiKeyRequest(BaseModel):
    """Request body for creating a scoped, expiring API key."""

    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    ttl_days: int = Field(gt=0, le=365, default=90)


class ApiKeyResponse(BaseModel):
    """API key metadata. Never includes the raw key (see ``ApiKeyCreatedResponse``)."""

    id: UUID
    tenant_id: UUID
    name: str
    scopes: list[str]
    expires_at: datetime
    revoked_at: datetime | None = None
    created_by_user_id: UUID
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned exactly once, at creation time — includes the raw key value."""

    raw_key: str


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyResponse]


# ---------------------------------------------------------------------------
# Policy Engine / Policy Administration schemas (spec 005 §3/§4)
# ---------------------------------------------------------------------------


class PolicyRuleResponse(BaseModel):
    id: UUID
    policy_pack_id: UUID
    rule_key: str
    name: str
    description: str
    severity: str
    created_at: datetime


class PolicyPackResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    version: str
    name: str
    jurisdiction: str | None = None
    is_active: bool
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    created_at: datetime


class PolicyPackListResponse(BaseModel):
    items: list[PolicyPackResponse]


class CreatePolicyPackRequest(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    content_hash: str = Field(min_length=1, max_length=128)
    jurisdiction: str | None = None


class AddPolicyRuleRequest(BaseModel):
    rule_key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str
    severity: str = Field(min_length=1, max_length=50)


class PolicyPackApprovalResponse(BaseModel):
    id: UUID
    policy_pack_id: UUID
    requested_by_user_id: UUID
    decided_by_user_id: UUID | None = None
    decision: str
    reason: str | None = None
    decided_at: datetime | None = None
    created_at: datetime


class PolicyPackApprovalListResponse(BaseModel):
    items: list[PolicyPackApprovalResponse]


class RejectPolicyPackRequest(BaseModel):
    reason: str = Field(min_length=1)


class PolicyResultResponse(BaseModel):
    id: UUID
    finding_id: UUID
    application_id: UUID
    policy_pack_id: UUID
    policy_version: str
    outcome: str
    triggered_rule_keys: list[str]
    evaluated_rule_keys: list[str] | None = None
    passed_rule_keys: list[str] | None = None
    evaluated_at: datetime
    created_at: datetime


class PolicyResultListResponse(BaseModel):
    items: list[PolicyResultResponse]


# ---------------------------------------------------------------------------
# Collaboration schemas (spec 005 §9)
# ---------------------------------------------------------------------------


class PostCommentRequest(BaseModel):
    comment_text: str = Field(min_length=1)
    mentioned_user_ids: list[UUID] = Field(default_factory=list)


class EditCommentRequest(BaseModel):
    comment_text: str = Field(min_length=1)


class ReviewCommentResponse(BaseModel):
    id: UUID
    review_session_id: UUID
    author_user_id: UUID
    comment_text: str
    mentioned_user_ids: list[str]
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    created_at: datetime


class ReviewCommentListResponse(BaseModel):
    items: list[ReviewCommentResponse]


# ---------------------------------------------------------------------------
# Assignment schemas (spec 005 §1, Wave 2 — RM/Banker Workspace)
# ---------------------------------------------------------------------------


class SetAssignmentRequest(BaseModel):
    owner_user_id: UUID
    reviewer_user_id: UUID | None = None


class AssignmentResponse(BaseModel):
    id: UUID
    application_id: UUID
    owner_user_id: UUID
    reviewer_user_id: UUID | None = None
    assigned_by_user_id: UUID
    assigned_at: datetime


class AssignmentHistoryResponse(BaseModel):
    id: UUID
    application_id: UUID
    owner_user_id: UUID
    reviewer_user_id: UUID | None = None
    assigned_by_user_id: UUID
    assigned_at: datetime
    created_at: datetime


class AssignmentHistoryListResponse(BaseModel):
    items: list[AssignmentHistoryResponse]


class PortfolioResponse(BaseModel):
    """RM's own portfolio: applications they own, with real, already-fetched fields only."""

    items: list[ApplicationResponse]


# ---------------------------------------------------------------------------
# LOS Integration schemas (spec 005 §2, Wave 2)
# ---------------------------------------------------------------------------


class CreateLOSConnectionRequest(BaseModel):
    vendor_type: str = Field(min_length=1, max_length=100)


class LOSConnectionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    vendor_type: str
    status: str
    created_by_user_id: UUID
    created_at: datetime


class LOSConnectionListResponse(BaseModel):
    items: list[LOSConnectionResponse]


class PushReadinessRequest(BaseModel):
    is_ready: bool
    summary: str = Field(min_length=1)
    missing_items: list[str] = Field(default_factory=list)


class LOSSyncEventResponse(BaseModel):
    id: UUID
    application_id: UUID
    direction: str
    outcome: str
    detail: dict[str, object]
    error_message: str | None = None
    initiated_by_user_id: UUID
    occurred_at: datetime


class LOSSyncEventListResponse(BaseModel):
    items: list[LOSSyncEventResponse]


# ---------------------------------------------------------------------------
# Universal Search schemas (spec 005 §7, Wave 2)
# ---------------------------------------------------------------------------


class ApplicationSearchResult(BaseModel):
    kind: Literal["application"] = "application"
    application: ApplicationResponse


class DocumentSearchResult(BaseModel):
    kind: Literal["document"] = "document"
    document_id: UUID
    application_id: UUID
    filename: str
    uploaded_at: datetime


SearchResult = ApplicationSearchResult | DocumentSearchResult


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


# ---------------------------------------------------------------------------
# Notification schemas (spec 005 §13, Wave 2)
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    id: UUID
    recipient_user_id: UUID
    audit_event_id: UUID
    # Denormalised, read-only fields resolved from the referenced AuditEvent
    # at read time — never stored on Notification itself (see model
    # docstring: no duplicate event model).
    event_type: str
    event_data: dict[str, object]
    occurred_at: datetime
    read_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


# ---------------------------------------------------------------------------
# Borrower Identity Resolution schemas (spec 005 §5, Wave 3)
# ---------------------------------------------------------------------------


class IdentityMatchCandidateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    party_id: UUID
    candidate_party_id: UUID
    match_score: float
    match_basis: dict[str, object]
    status: str
    reviewed_by_user_id: UUID | None = None
    reason: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class IdentityMatchCandidateListResponse(BaseModel):
    items: list[IdentityMatchCandidateResponse]


class RejectMatchRequest(BaseModel):
    reason: str | None = None


class BorrowerIdentityResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    primary_display_name: str
    created_at: datetime


class BorrowerIdentityMemberResponse(BaseModel):
    id: UUID
    borrower_identity_id: UUID
    party_id: UUID
    application_id: UUID
    linked_by_user_id: UUID
    linked_at: datetime
    unlinked_at: datetime | None = None
    unlinked_by_user_id: UUID | None = None


class BorrowerIdentityMemberListResponse(BaseModel):
    items: list[BorrowerIdentityMemberResponse]


# ---------------------------------------------------------------------------
# Cross-Application Intelligence schemas (spec 005 §6, Wave 3)
# ---------------------------------------------------------------------------


class CrossApplicationObservationResponse(BaseModel):
    kind: str
    description: str
    application_ids: list[UUID]
    document_ids: list[UUID] = Field(default_factory=list)
    finding_ids: list[UUID] = Field(default_factory=list)


class CrossApplicationSignalListResponse(BaseModel):
    items: list[CrossApplicationObservationResponse]


# ---------------------------------------------------------------------------
# Operational Dashboard schemas (spec 005 §10, Wave 3)
# ---------------------------------------------------------------------------


class QueueDepthRowResponse(BaseModel):
    workflow_type: str
    status: str
    count: int


class QueueDepthResponse(BaseModel):
    items: list[QueueDepthRowResponse]


class PoisonJobResponse(BaseModel):
    id: UUID
    workflow_run_id: UUID
    step_name: str
    status: str
    retry_count: int
    max_retries: int
    error_code: str | None = None
    error_message: str | None = None
    updated_at: datetime


class PoisonJobListResponse(BaseModel):
    items: list[PoisonJobResponse]


class ApplicationFunnelRowResponse(BaseModel):
    status: str
    count: int
    avg_seconds_since_updated: float


class ApplicationFunnelResponse(BaseModel):
    items: list[ApplicationFunnelRowResponse]


class JobQueueHealthResponse(BaseModel):
    pending_count: int
    processing_count: int
    dead_letter_count: int


# ---------------------------------------------------------------------------
# Business Analytics schemas (spec 005 §11, Wave 3)
# ---------------------------------------------------------------------------


class ApplicationStatusCountResponse(BaseModel):
    status: str
    count: int


class FindingOutcomeRowResponse(BaseModel):
    lifecycle_state: str
    count: int


class PolicyOutcomeRowResponse(BaseModel):
    policy_version: str
    outcome: str
    count: int


class BusinessAnalyticsSnapshotResponse(BaseModel):
    application_counts_by_status: list[ApplicationStatusCountResponse]
    finding_outcomes: list[FindingOutcomeRowResponse]
    policy_outcomes: list[PolicyOutcomeRowResponse]
    document_count: int
    evidence_count: int
    average_review_duration_seconds: float | None = None


# ---------------------------------------------------------------------------
# Customer Portal schemas (spec 005 §12, Wave 4)
# ---------------------------------------------------------------------------


class CreateChecklistItemRequest(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    document_type: str = Field(min_length=1, max_length=100)
    party_id: UUID | None = None


class ChecklistItemResponse(BaseModel):
    id: UUID
    application_id: UUID
    party_id: UUID | None = None
    label: str
    document_type: str
    status: str
    requested_by_user_id: UUID
    fulfilled_document_id: UUID | None = None
    requested_at: datetime


class ChecklistItemListResponse(BaseModel):
    items: list[ChecklistItemResponse]


class InviteBorrowerRequest(BaseModel):
    party_id: UUID
    email: str = Field(min_length=3, max_length=320)


class InviteBorrowerResponse(BaseModel):
    portal_account_id: UUID
    status: str
    # Empty when the account was already invited/active — no email/SMS
    # provider exists in this platform (an honest, disclosed gap); the
    # inviting user relays this link/token to the borrower out-of-band.
    activation_token: str


class PortalActivateRequest(BaseModel):
    party_id: UUID
    token: str = Field(min_length=1)


class PortalSessionResponse(BaseModel):
    session_token: str


class PortalStatusResponse(BaseModel):
    """A borrower-safe, plain-language status label — never the internal enum verbatim."""

    status_label: str


PORTAL_STATUS_LABELS: dict[str, str] = {
    "DRAFT": "Getting started",
    "SUBMITTED": "Application received",
    "IN_REVIEW": "Documents under review",
    "REVIEW_COMPLETE": "Review complete",
    "WITHDRAWN": "Application withdrawn",
}


# ---------------------------------------------------------------------------
# Security & Compliance schemas (spec 005 §16, Wave 4)
# ---------------------------------------------------------------------------


class SetRetentionPolicyRequest(BaseModel):
    data_category: str = Field(min_length=1, max_length=50)
    retention_period_days: int = Field(gt=0)
    action: Literal["ARCHIVE", "DELETE"]


class RetentionPolicyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    data_category: str
    retention_period_days: int
    action: str


class RetentionPolicyListResponse(BaseModel):
    items: list[RetentionPolicyResponse]


class AccessLogEntryResponse(BaseModel):
    event_type: str
    actor_id: UUID | None = None
    actor_type: str
    occurred_at: datetime


class AccessLogResponse(BaseModel):
    application_id: UUID
    from_date: datetime
    to_date: datetime
    items: list[AccessLogEntryResponse]
