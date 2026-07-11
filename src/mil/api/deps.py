"""
FastAPI dependency providers for the MIL Platform API.

Every reusable concern — authentication, database sessions, and service
construction — lives here as a ``Depends``-injectable callable.  Route handlers
must never instantiate services, sessions, or security objects directly.

Authentication scheme (Sprint 3D dev mode):
    ``Authorization: Bearer <token>``

    ``<token>`` is a Base64URL-encoded JSON object with the fields:
        ``user_id``    — string UUID of the authenticated user
        ``tenant_id``  — string UUID of the user's institution
        ``roles``      — list of role strings (e.g. ["RELATIONSHIP_MANAGER"])
        ``email``      — string (optional, defaults to "")
        ``display_name`` — string (optional, defaults to "")

    In development mode (``MIL_ENV=development``) the literal token ``"dev"``
    is accepted and resolves to an ADMIN-role development user. Production
    deployments replace this function with a real JWT verification implementation.

Dependency graph::

    get_current_user          -- verifies bearer token, returns AuthenticatedUser
    get_db                    -- yields a synchronous SQLAlchemy Session
    get_application_service   -- builds ApplicationService from session
    get_document_service      -- builds DocumentService from session + container
    get_document_ingestion_trigger -- builds DocumentIngestionTrigger from session + container
    get_finding_trigger       -- builds FindingTrigger from session + container
    get_copilot_service       -- builds CopilotService from session + container

Override any dependency in tests via ``app.dependency_overrides``.

Dependency rule: imports from ``mil.kernel``, ``mil.application``,
``mil.document``, ``mil.audit``, and the Python standard library only.

``get_document_ingestion_trigger``, ``get_finding_trigger``, and
``get_copilot_service`` are the exceptions. ``get_document_ingestion_trigger``
starts the ``DOCUMENT_INGESTION`` workflow (OCR -> Extraction) for the upload
composition point. ``get_finding_trigger`` composes the Application and
Finding/Orchestrator bounded contexts for the single DRAFT -> SUBMITTED
composition point (ADR-009). ``get_copilot_service`` composes the
Application, Document, Evidence, Finding, Policy, and Review bounded
contexts' existing repositories into the Copilot bounded context's read-only
Query Ports (ADR-010) via ``mil.copilot.adapters`` — the one module in
``mil.copilot`` permitted to reference those repositories. All three mirror
how ``workers/*.py`` composition roots wire multiple bounded contexts
together for job-triggered flows: this module is the sanctioned place for
that composition for HTTP-triggered flows; no bounded-context module itself
(including ``mil.copilot.service`` and ``mil.copilot.ports``) gains a new
cross-context dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from mil.application.repository import ApplicationRepository
from mil.application.service import ApplicationService
from mil.assignment.repository import AssignmentRepository
from mil.assignment.service import AssignmentService
from mil.audit.repository import AuditRepository
from mil.audit.writer import AuditWriter
from mil.borrower_identity.repository import BorrowerIdentityRepository
from mil.borrower_identity.service import BorrowerIdentityService, PartyMatchInput
from mil.compliance.repository import ComplianceRepository
from mil.compliance.service import ComplianceService
from mil.copilot.adapters import (
    ApplicationReaderAdapter,
    DocumentReaderAdapter,
    DocumentTextReaderAdapter,
    EvidenceReaderAdapter,
    FindingReaderAdapter,
    PolicyResultReaderAdapter,
    ReviewReaderAdapter,
)
from mil.copilot.repository import CopilotRepository
from mil.copilot.service import CopilotService
from mil.cross_application_intelligence.service import (
    CrossApplicationObservation,
    DocumentSignal,
    FindingSignal,
    find_repeated_finding_types,
    find_reused_documents,
    summarize_review_outcomes,
)
from mil.document.ocr_repository import OCRResultRepository
from mil.document.repository import DocumentRepository
from mil.document.service import DocumentService
from mil.evidence.repository import EvidenceRepository
from mil.evidence.service import EvidenceService
from mil.finding.repository import FindingRepository
from mil.finding.service import FindingService
from mil.identity.provider import (
    DevBearerIdentityProvider,
    IdentityProvider,
    populate_authenticated_user,
)
from mil.identity.repository import IdentityRepository
from mil.identity.service import IdentityService
from mil.integration.repository import IntegrationRepository
from mil.integration.service import IntegrationService
from mil.kernel.config import Settings
from mil.kernel.errors import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from mil.kernel.providers.storage import StorageProvider
from mil.kernel.security import AuthenticatedUser, Permission, Role, require_permission
from mil.kernel.types import TenantId, UserId
from mil.notification.repository import NotificationRepository
from mil.notification.service import NotificationService
from mil.orchestrator.repository import WorkflowRepository
from mil.policy.repository import PolicyRepository
from mil.policy.service import PolicyService
from mil.portal.auth import PortalSessionClaims
from mil.portal.repository import PortalRepository
from mil.portal.service import PortalService
from mil.review.models import ESCALATED, PENDING_REVIEW
from mil.review.repository import ReviewRepository
from mil.review.service import ReviewService

if TYPE_CHECKING:
    from collections.abc import Generator
    from datetime import datetime

    from mil.application.models import MortgageApplication, Party
    from mil.audit.models import AuditEvent
    from mil.borrower_identity.models import (
        BorrowerIdentity,
        BorrowerIdentityMember,
        IdentityMatchCandidate,
    )
    from mil.compliance.models import DataRetentionPolicy
    from mil.document.models import Document
    from mil.finding.models import Finding
    from mil.identity.provider import TokenClaims
    from mil.integration.models import LOSSyncEvent
    from mil.kernel.container import Container
    from mil.notification.models import Notification
    from mil.orchestrator.models import WorkflowRun, WorkflowStep
    from mil.portal.models import DocumentChecklistItem, PortalAccount
    from mil.review.models import ReviewSession

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authentication dependency
# ---------------------------------------------------------------------------

# Fallback provider used ONLY when no DI container is bound to the app (e.g. a
# TestClient constructed without triggering the ASGI lifespan). A deployed
# process always binds a container at startup, and ``build_container`` refuses
# to start a non-development process without a real ``IdentityProvider``
# registered — so this development fallback is never reachable in a running
# staging/production deployment (Backend Freeze Patch v1.0).
_FALLBACK_DEV_IDENTITY_PROVIDER = DevBearerIdentityProvider()

# Registers an HTTP Bearer security scheme in the OpenAPI document (Backend
# Freeze Patch v1.0, OpenAPI integration) so Swagger UI renders the
# "Authorize" button and a lock icon on every endpoint that depends on
# ``get_current_user``, and sends the entered token as the ``Authorization``
# header automatically. ``auto_error=False`` so this dependency only *extracts*
# the credentials — ``get_current_user`` still raises the platform's own
# ``AUTHENTICATION_REQUIRED`` 401 body for a missing/malformed/invalid token,
# exactly as before this scheme was introduced.
bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description=(
        "Bearer token verified by the platform's IdentityProvider. In "
        "development, use the literal token `dev` for a built-in ADMIN "
        "principal, or a Base64URL-encoded JSON object with `user_id`, "
        "`tenant_id`, and optional `roles`/`email`/`display_name`."
    ),
    auto_error=False,
)


def _resolve_identity_provider(request: Request) -> IdentityProvider:
    """
    Resolve the active ``IdentityProvider`` for this request from the DI
    container, falling back to the development provider only when no container
    is bound (see ``_FALLBACK_DEV_IDENTITY_PROVIDER``).
    """
    from mil.kernel.container import Container

    container = getattr(request.app.state, "container", None)
    if isinstance(container, Container) and container.is_registered(IdentityProvider):
        return container.resolve(IdentityProvider)  # type: ignore[type-abstract]
    return _FALLBACK_DEV_IDENTITY_PROVIDER


def _authenticated_user_from_claims(claims: TokenClaims) -> AuthenticatedUser:
    """Map normalised ``TokenClaims`` onto the request principal."""
    try:
        user_id = UserId(UUID(claims.subject))
    except (ValueError, AttributeError) as exc:
        raise AuthenticationError("Invalid bearer token: subject is not a valid user id.") from exc
    return populate_authenticated_user(claims, user_id=user_id)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    """
    Verify the ``Authorization: Bearer <token>`` header and return the
    authenticated principal.

    The token is extracted by FastAPI's ``HTTPBearer`` security dependency
    (``bearer_scheme``), which also registers the scheme in the OpenAPI
    document so Swagger UI shows the "Authorize" button and sends the token
    automatically. Token verification itself is still delegated to the
    ``IdentityProvider`` resolved from the DI container (Backend Freeze Patch
    v1.0). In development this is the ``DevBearerIdentityProvider`` (the
    literal ``"dev"`` token and Base64URL JSON tokens are accepted);
    staging/production register a signature-verifying provider, and
    ``build_container`` refuses to start without one.

    Raises:
        HTTPException(401): If the header is absent, not a bearer token, or
            the token itself is invalid.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Authorization header must be 'Bearer <token>'.",
            },
        )

    token = credentials.credentials
    provider = _resolve_identity_provider(request)
    try:
        claims = provider.validate_token(token)
        user = _authenticated_user_from_claims(claims)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": exc.message},
        ) from exc
    _bind_user_to_log_context(user)
    return user


def _bind_user_to_log_context(user: AuthenticatedUser) -> None:
    """
    Merge the authenticated caller's identity into the structured log context.

    Sprint 8 (Production Hardening): every log line emitted while handling
    this request should carry ``tenant_id`` and ``user_id`` alongside the
    ``request_id``/``correlation_id`` the telemetry middleware already set.
    """
    from dataclasses import replace

    from mil.kernel.observability import get_log_context, set_log_context

    current = get_log_context()
    set_log_context(replace(current, tenant_id=str(user.tenant_id), user_id=str(user.user_id)))


# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------


def get_db(request: Request) -> Generator[Session, None, None]:
    """
    Yield a synchronous SQLAlchemy ``Session`` for the duration of the request.

    Commits on clean exit; rolls back on any exception.  The session is closed
    in all cases.

    Requires ``request.app.state.session_factory`` to be set by the
    application lifespan (set up in ``create_app()``).
    """
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Container dependency
# ---------------------------------------------------------------------------


def get_container(request: Request) -> Container:
    """Return the DI container stored in application state."""
    return request.app.state.container  # type: ignore[no-any-return]


def get_app_settings(request: Request) -> Settings:
    """
    Return the active platform ``Settings``.

    Reads the settings bound to ``app.state`` by the lifespan handler; falls
    back to ``get_settings()`` when no lifespan ran (e.g. a TestClient built
    without the ASGI lifespan). Used by route handlers that need configuration
    values such as the maximum upload size.
    """
    from mil.kernel.config import get_settings

    settings = getattr(request.app.state, "settings", None)
    if settings is not None:
        return settings  # type: ignore[no-any-return]
    return get_settings()


# ---------------------------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------------------------

CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


# ---------------------------------------------------------------------------
# Customer Portal authentication (spec 005-enterprise-platform §12, Wave 4)
#
# A deliberately separate ``HTTPBearer`` scheme instance and verification
# function from ``get_current_user`` above — a portal session token and an
# internal-staff token share no code path, no claim shape, and no key
# material (``Settings.mil_portal_secret_key`` vs. the internal
# ``IdentityProvider``), so a portal token can never be accepted by an
# internal endpoint or vice versa (the spec's own explicit acceptance
# criterion).
# ---------------------------------------------------------------------------

portal_bearer_scheme = HTTPBearer(
    scheme_name="PortalBearerAuth",
    description="Customer Portal session token, issued by POST /v1/portal/auth/activate.",
    auto_error=False,
)


def get_current_portal_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(portal_bearer_scheme)],
    settings: SettingsDep,
) -> PortalSessionClaims:
    """Verify a portal session token and return its claims."""
    from mil.portal.auth import verify_portal_token

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Authorization header must be 'Bearer <portal session token>'.",
            },
        )
    try:
        return verify_portal_token(
            credentials.credentials,
            settings.mil_portal_secret_key.get_secret_value().encode("utf-8"),
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": exc.message},
        ) from exc


CurrentPortalClaims = Annotated[PortalSessionClaims, Depends(get_current_portal_claims)]


def get_application_service(session: DbSession) -> ApplicationService:
    """
    Build and return an ``ApplicationService`` wired to the request session.

    The audit writer and repository share the same session, ensuring atomicity
    of domain mutations and audit events within a single transaction.
    """
    audit = AuditWriter(session)
    repo = ApplicationRepository(session, audit)
    return ApplicationService(repo)


def get_document_service(
    session: DbSession,
    container: Annotated[object, Depends(get_container)],
) -> DocumentService:
    """
    Build and return a ``DocumentService`` wired to the request session and
    the platform's ``StorageProvider`` and ``EventBus`` from the DI container.
    """
    from mil.kernel.container import Container
    from mil.kernel.event_bus import EventBus
    from mil.kernel.observability import MetricEmitter
    from mil.kernel.providers.storage import StorageProvider

    c = container
    if not isinstance(c, Container):
        raise RuntimeError("DI container not available on app state.")

    storage = c.resolve(StorageProvider)  # type: ignore[type-abstract]
    event_bus = c.resolve(EventBus)  # type: ignore[type-abstract]
    metrics = c.resolve(MetricEmitter)  # type: ignore[type-abstract]
    audit = AuditWriter(session, metrics=metrics)
    repo = DocumentRepository(session, audit)
    return DocumentService(repo, storage, event_bus)


def get_storage_provider(
    container: Annotated[object, Depends(get_container)],
) -> StorageProvider:
    """
    Resolve the platform's ``StorageProvider`` from the DI container.

    Exposed as its own dependency (distinct from ``get_document_service``,
    which already resolves one internally for writes) so a read-only content
    endpoint can retrieve document bytes without constructing a full
    ``DocumentService`` — mirrors the existing retrieval call already used
    by ``workers.document_pipeline`` (``storage.retrieve(document
    .storage_reference)``), not new storage-access logic.
    """
    from mil.kernel.container import Container

    c = container
    if not isinstance(c, Container):
        raise RuntimeError("DI container not available on app state.")
    return c.resolve(StorageProvider)  # type: ignore[type-abstract]


class DocumentIngestionTrigger:
    """
    Composition-root wrapper that starts the ``DOCUMENT_INGESTION`` workflow.

    Bound to the request's session and DI container. ``trigger()`` is a thin
    delegation to ``workers.document_pipeline.start_document_ingestion_workflow``
    — this class exists only so ``mil.api.v1.documents`` can depend on a type
    re-exported from ``mil.api.deps`` (its declared dependency) rather than
    importing ``workers.document_pipeline`` or any bounded-context module
    directly. Mirrors ``FindingTrigger`` below.
    """

    def __init__(self, *, session: Session, container: Container) -> None:
        self._session = session
        self._container = container

    def trigger(self, document: Document) -> WorkflowRun:
        """Start (or return the existing) DOCUMENT_INGESTION workflow run."""
        from workers.document_pipeline import start_document_ingestion_workflow

        return start_document_ingestion_workflow(
            self._session,
            self._container,
            document_id=document.id,
            application_id=document.application_id,
            tenant_id=document.tenant_id,
        )


def get_document_ingestion_trigger(
    session: DbSession,
    container: Annotated[object, Depends(get_container)],
) -> DocumentIngestionTrigger:
    """
    Build and return a ``DocumentIngestionTrigger`` wired to the request
    session and the platform DI container.

    Called immediately after a successful upload so the ``DOCUMENT_INGESTION``
    workflow run (and its first dispatched OCR job) commits in the same
    transaction as the new ``Document`` row — without this, an uploaded
    document is stored but the OCR/Extraction pipeline never starts.
    """
    from mil.kernel.container import Container

    c = container
    if not isinstance(c, Container):
        raise RuntimeError("DI container not available on app state.")
    return DocumentIngestionTrigger(session=session, container=c)


class FindingTrigger:
    """
    Composition-root wrapper that starts the ``FINDING_GENERATION`` workflow.

    Bound to the request's session and DI container. ``trigger()`` is a thin
    delegation to ``workers.finding_pipeline.start_finding_generation_workflow``
    — this class exists only so ``mil.api.v1.applications`` can depend on a
    type re-exported from ``mil.api.deps`` (its declared dependency) rather
    than importing ``workers.finding_pipeline`` or any bounded-context module
    directly.
    """

    def __init__(self, *, session: Session, container: Container) -> None:
        self._session = session
        self._container = container

    def trigger(self, application: MortgageApplication) -> WorkflowRun:
        """Start (or return the existing) FINDING_GENERATION workflow run."""
        from workers.finding_pipeline import start_finding_generation_workflow

        return start_finding_generation_workflow(
            self._session,
            self._container,
            application_id=application.id,
            tenant_id=application.tenant_id,
        )


def get_finding_trigger(
    session: DbSession,
    container: Annotated[object, Depends(get_container)],
) -> FindingTrigger:
    """
    Build and return a ``FindingTrigger`` wired to the request session and the
    platform DI container.

    Per ADR-009, Finding generation is triggered by the application's
    DRAFT -> SUBMITTED transition and evaluates all of its evidence, never per
    document. ``FindingTrigger`` composes the Orchestrator, Evidence, and
    Finding contexts for that single trigger point, bound to the same session
    as the submit request so the workflow run and its dispatch commit in the
    same transaction as the application's state change.
    """
    from mil.kernel.container import Container

    c = container
    if not isinstance(c, Container):
        raise RuntimeError("DI container not available on app state.")
    return FindingTrigger(session=session, container=c)


def get_copilot_service(
    session: DbSession,
    container: Annotated[object, Depends(get_container)],
) -> CopilotService:
    """
    Build and return a ``CopilotService`` wired to the request session, the
    platform's ``InferenceProvider``, and the six read-only Query Port
    adapters (ADR-010).

    This is the sanctioned composition point for the Copilot bounded
    context's cross-context reads (see the module docstring). Each adapter
    wraps an existing repository bound to the same session as the
    ``CopilotRepository`` and ``AuditWriter``, so a single request reads
    committed state consistently. ``mil.copilot.service`` never imports any
    of the repository types constructed here.
    """
    from mil.kernel.container import Container
    from mil.kernel.observability import MetricEmitter
    from mil.kernel.providers.inference import InferenceProvider

    c = container
    if not isinstance(c, Container):
        raise RuntimeError("DI container not available on app state.")

    inference = c.resolve(InferenceProvider)  # type: ignore[type-abstract]
    metrics = c.resolve(MetricEmitter)  # type: ignore[type-abstract]
    audit = AuditWriter(session, metrics=metrics)
    repo = CopilotRepository(session)

    document_repo = DocumentRepository(session, audit)
    return CopilotService(
        repo,
        audit,
        inference=inference,
        applications=ApplicationReaderAdapter(ApplicationRepository(session, audit)),
        documents=DocumentReaderAdapter(document_repo),
        document_texts=DocumentTextReaderAdapter(document_repo, OCRResultRepository(session)),
        evidence=EvidenceReaderAdapter(EvidenceRepository(session)),
        findings=FindingReaderAdapter(FindingRepository(session)),
        policy_results=PolicyResultReaderAdapter(PolicyRepository(session)),
        reviews=ReviewReaderAdapter(ReviewRepository(session)),
    )


def get_evidence_service(session: DbSession) -> EvidenceService:
    """Build and return an ``EvidenceService`` wired to the request session."""
    audit = AuditWriter(session)
    repo = EvidenceRepository(session)
    return EvidenceService(repo, audit)


def get_finding_service(session: DbSession) -> FindingService:
    """Build and return a ``FindingService`` wired to the request session."""
    audit = AuditWriter(session)
    repo = FindingRepository(session)
    return FindingService(repo, audit)


def get_audit_repository(session: DbSession) -> AuditRepository:
    """Build and return an ``AuditRepository`` wired to the request session."""
    return AuditRepository(session)


def get_identity_service(session: DbSession) -> IdentityService:
    """Build and return an ``IdentityService`` wired to the request session."""
    audit = AuditWriter(session)
    repo = IdentityRepository(session)
    return IdentityService(repo, audit)


def get_policy_service(session: DbSession) -> PolicyService:
    """Build and return a ``PolicyService`` wired to the request session."""
    audit = AuditWriter(session)
    repo = PolicyRepository(session)
    return PolicyService(repo, audit)


def get_assignment_service(session: DbSession) -> AssignmentService:
    """Build and return an ``AssignmentService`` wired to the request session."""
    audit = AuditWriter(session)
    repo = AssignmentRepository(session)
    return AssignmentService(repo, audit)


class RmWorkspace:
    """
    Composition-root wrapper for the RM/Banker Workspace's portfolio view
    (spec 005-enterprise-platform §1, Wave 2).

    Composes Assignment + Application's existing repositories for the one
    HTTP composition point (``GET /v1/rm/portfolio``) that needs both —
    mirrors ``FindingReviewActions``'s existing pattern above. No bounded
    context gains a new cross-context dependency; only this composition
    class does.
    """

    def __init__(self, *, session: Session) -> None:
        self._applications = ApplicationRepository(session, AuditWriter(session))
        self._assignment_service = AssignmentService(
            AssignmentRepository(session), AuditWriter(session)
        )

    def get_portfolio(self, user: AuthenticatedUser) -> list[MortgageApplication]:
        assignments = self._assignment_service.get_portfolio(user)
        applications = [self._applications.get_by_id(a.application_id) for a in assignments]
        return [app for app in applications if app is not None]


def get_rm_workspace(session: DbSession) -> RmWorkspace:
    return RmWorkspace(session=session)


class IntegrationWorkspace:
    """
    Composition-root wrapper for LOS Integration HTTP actions (spec 005-
    enterprise-platform §2, Wave 2).

    Resolves the application's real ``los_reference`` (Application bounded
    context) and the registered ``LOSAdapter`` (DI container) so that
    ``mil.integration`` itself never imports either — mirrors
    ``RmWorkspace``/``FindingReviewActions``'s existing composition pattern.
    """

    def __init__(self, *, session: Session, container: object) -> None:
        from mil.kernel.container import Container
        from mil.kernel.providers.los_adapter import LOSAdapter

        if not isinstance(container, Container):
            raise RuntimeError("DI container not available on app state.")

        self._applications = ApplicationRepository(session, AuditWriter(session))
        self._service = IntegrationService(
            IntegrationRepository(session),
            AuditWriter(session),
            container.resolve(LOSAdapter),  # type: ignore[type-abstract]
        )

    def _los_reference_or_404(self, application_id: UUID) -> str:
        application = self._applications.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application", application_id)
        if application.los_reference is None:
            raise ValidationError(
                "Application has no los_reference set — nothing to sync/push against",
                field="los_reference",
            )
        return application.los_reference

    def sync_application(self, user: AuthenticatedUser, application_id: UUID) -> LOSSyncEvent:
        los_reference = self._los_reference_or_404(application_id)
        return self._service.sync_application(
            user, application_id=application_id, los_reference=los_reference
        )

    def push_readiness(
        self,
        user: AuthenticatedUser,
        application_id: UUID,
        *,
        is_ready: bool,
        summary: str,
        missing_items: tuple[str, ...] = (),
    ) -> LOSSyncEvent:
        los_reference = self._los_reference_or_404(application_id)
        return self._service.push_readiness(
            user,
            application_id=application_id,
            los_reference=los_reference,
            is_ready=is_ready,
            summary=summary,
            missing_items=missing_items,
        )

    @property
    def service(self) -> IntegrationService:
        """Direct access for connection-management/read endpoints that don't need los_reference."""
        return self._service


def get_integration_workspace(
    session: DbSession, container: Annotated[object, Depends(get_container)]
) -> IntegrationWorkspace:
    return IntegrationWorkspace(session=session, container=container)


class SearchWorkspace:
    """
    Composition-root wrapper for Universal Search (spec 005-enterprise-
    platform §7, Wave 2 — Universal Search Expansion).

    Composes the Application and Document bounded contexts' existing
    ``search``/``search_for_tenant`` repository methods into one endpoint
    (``GET /v1/search``) — no new search infrastructure, no new bounded
    context imports either context into the other; only this composition
    class references both. Deliberately modular: adding a third entity kind
    (e.g. Finding) later is one more method here and one more branch in the
    route's ``kinds`` handling, not a redesign.
    """

    def __init__(self, *, session: Session) -> None:
        self._applications = ApplicationRepository(session, AuditWriter(session))
        self._documents = DocumentRepository(session, AuditWriter(session))

    def search_applications(self, tenant_id: UUID, query: str) -> list[MortgageApplication]:
        return self._applications.get_for_tenant(tenant_id, search=query)

    def search_documents(self, tenant_id: UUID, query: str) -> list[Document]:
        return self._documents.search_for_tenant(tenant_id, query)


def get_search_workspace(session: DbSession) -> SearchWorkspace:
    return SearchWorkspace(session=session)


def get_notification_service(session: DbSession) -> NotificationService:
    """
    Build and return a ``NotificationService`` wired to the request session.

    Used both to read/mark-read a caller's own notifications, and — by other
    route modules (``mil.api.v1.comments``, ``mil.api.v1.assignments``) — to
    call ``notify()`` after their own action's audit event has been written,
    pointing the new notification at that same event id. No new cross-
    context import: those route modules depend on this dependency exactly
    like they depend on their own service's.
    """
    return NotificationService(NotificationRepository(session))


class NotificationWorkspace:
    """
    Composition-root wrapper for reading notifications (spec 005-enterprise-
    platform §13, Wave 2). Resolves each ``Notification``'s referenced
    ``AuditEvent`` (Audit bounded context) to build a displayable response —
    mirrors ``RmWorkspace``/``IntegrationWorkspace``'s existing pattern.
    """

    def __init__(self, *, session: Session) -> None:
        self._service = NotificationService(NotificationRepository(session))
        self._audit = AuditRepository(session)

    def list_for_caller(
        self, caller: AuthenticatedUser
    ) -> list[tuple[Notification, AuditEvent | None]]:
        notifications = self._service.list_for_caller(caller)
        return [(n, self._audit.get_by_id(n.audit_event_id)) for n in notifications]

    def unread_count(self, caller: AuthenticatedUser) -> int:
        return self._service.unread_count(caller)

    def mark_read(
        self, caller: AuthenticatedUser, notification_id: UUID
    ) -> tuple[Notification, AuditEvent | None]:
        notification = self._service.mark_read(caller, notification_id)
        return notification, self._audit.get_by_id(notification.audit_event_id)


def get_notification_workspace(session: DbSession) -> NotificationWorkspace:
    return NotificationWorkspace(session=session)


class BorrowerIdentityWorkspace:
    """
    Composition-root wrapper for Borrower Identity Resolution HTTP actions
    (spec 005-enterprise-platform §5, Wave 3).

    Composes the Application bounded context's ``Party`` reads (needed to
    build ``PartyMatchInput`` and, on confirm, to resolve each party's
    ``application_id`` for ``BorrowerIdentityMember`` linking) with the
    Borrower Identity Resolution bounded context's own service — mirrors
    ``RmWorkspace``/``IntegrationWorkspace``'s existing pattern. Neither
    bounded context imports the other; only this composition class does.
    """

    def __init__(self, *, session: Session) -> None:
        self._applications = ApplicationRepository(session, AuditWriter(session))
        self._repo = BorrowerIdentityRepository(session)
        self._service = BorrowerIdentityService(self._repo, AuditWriter(session))

    @staticmethod
    def _to_match_input(party: Party) -> PartyMatchInput:
        return PartyMatchInput(
            party_id=party.id,
            application_id=party.application_id,
            display_name=party.display_name,
            external_identifier_hash=party.external_identifier_hash,
            identifier_type=party.identifier_type,
        )

    def compute_candidates(
        self, caller: AuthenticatedUser, party_id: UUID
    ) -> list[IdentityMatchCandidate]:
        subject = self._applications.get_party_by_id(party_id)
        if subject is None:
            raise NotFoundError("Party", party_id)
        others = self._applications.get_parties_for_tenant(caller.tenant_id)
        return self._service.compute_candidates(
            caller,
            tenant_id=caller.tenant_id,
            subject=self._to_match_input(subject),
            others=[self._to_match_input(p) for p in others if p.id != party_id],
        )

    def get_candidates_for_party(
        self, caller: AuthenticatedUser, party_id: UUID
    ) -> list[IdentityMatchCandidate]:
        return self._service.get_candidates_for_party(caller, party_id)

    def confirm_match(self, caller: AuthenticatedUser, candidate_id: UUID) -> BorrowerIdentity:
        candidate = self._service.get_candidate(caller, candidate_id)
        identity = self._service.confirm_match(caller, candidate)
        for party_id in (candidate.party_id, candidate.candidate_party_id):
            party = self._applications.get_party_by_id(party_id)
            if party is None:
                continue
            self._service.link_member(
                caller,
                identity=identity,
                party_id=party.id,
                application_id=party.application_id,
            )
        return identity

    def reject_match(
        self, caller: AuthenticatedUser, candidate_id: UUID, reason: str | None = None
    ) -> IdentityMatchCandidate:
        candidate = self._service.get_candidate(caller, candidate_id)
        return self._service.reject_match(caller, candidate, reason)

    def get_identity(self, caller: AuthenticatedUser, identity_id: UUID) -> BorrowerIdentity:
        return self._service.get_identity(caller, identity_id)

    def get_members(
        self, caller: AuthenticatedUser, identity_id: UUID
    ) -> list[BorrowerIdentityMember]:
        return self._service.get_members(caller, identity_id)

    def get_identity_for_party(
        self, caller: AuthenticatedUser, party_id: UUID
    ) -> BorrowerIdentity | None:
        return self._service.get_identity_for_party(caller, party_id)


def get_borrower_identity_workspace(session: DbSession) -> BorrowerIdentityWorkspace:
    return BorrowerIdentityWorkspace(session=session)


class CrossApplicationIntelligenceWorkspace:
    """
    Composition-root wrapper for Cross-Application Intelligence (spec 005-
    enterprise-platform §6, Wave 3 — a "flagship capability" built on top of
    Borrower Identity Resolution).

    Resolves a ``BorrowerIdentity``'s active members (Borrower Identity
    Resolution bounded context) to the real applications they reference,
    fetches each application's Documents and Findings (existing repository
    methods, no new cross-context import inside either bounded context),
    and calls ``mil.cross_application_intelligence``'s pure derivation
    functions. Read-only; gated by the same
    ``READ_CROSS_APPLICATION_IDENTITY`` permission as viewing the identity
    itself — this module only ever surfaces observations, never decisions
    (Principle I), so it needs no new permission of its own.
    """

    def __init__(self, *, session: Session) -> None:
        self._borrower_identity = BorrowerIdentityService(
            BorrowerIdentityRepository(session), AuditWriter(session)
        )
        self._identity_repo = BorrowerIdentityRepository(session)
        self._documents = DocumentRepository(session, AuditWriter(session))
        self._findings = FindingRepository(session)

    def get_signals(
        self, caller: AuthenticatedUser, identity_id: UUID
    ) -> list[CrossApplicationObservation]:
        # get_identity self-checks READ_CROSS_APPLICATION_IDENTITY and tenant scope.
        self._borrower_identity.get_identity(caller, identity_id)
        members = self._identity_repo.get_active_members_for_identity(identity_id)
        application_ids = {m.application_id for m in members}

        document_signals: list[DocumentSignal] = []
        finding_signals: list[FindingSignal] = []
        for application_id in application_ids:
            for doc in self._documents.get_for_application(application_id):
                document_signals.append(
                    DocumentSignal(
                        document_id=doc.id,
                        application_id=application_id,
                        content_hash=doc.content_hash,
                        filename=doc.original_filename,
                    )
                )
            for finding in self._findings.get_for_application(application_id):
                finding_signals.append(
                    FindingSignal(
                        finding_id=finding.id,
                        application_id=application_id,
                        finding_type=finding.finding_type,
                        lifecycle_state=finding.lifecycle_state,
                    )
                )

        observations: list[CrossApplicationObservation] = [
            *find_reused_documents(document_signals),
            *find_repeated_finding_types(finding_signals),
        ]
        review_summary = summarize_review_outcomes(finding_signals)
        if review_summary is not None:
            observations.append(review_summary)
        return observations


def get_cross_application_intelligence_workspace(
    session: DbSession,
) -> CrossApplicationIntelligenceWorkspace:
    return CrossApplicationIntelligenceWorkspace(session=session)


@dataclass(frozen=True)
class QueueDepthRow:
    """One (workflow_type, status, count) row (spec 005-enterprise-platform §10, Wave 3)."""

    workflow_type: str
    status: str
    count: int


@dataclass(frozen=True)
class ApplicationFunnelRow:
    """One (status, count, avg_seconds_since_updated) row (spec 005 §10, Wave 3)."""

    status: str
    count: int
    avg_seconds_since_updated: float


@dataclass(frozen=True)
class JobQueueHealth:
    """Real, process-wide job queue counters (spec 005-enterprise-platform §14, Wave 4)."""

    pending_count: int
    processing_count: int
    dead_letter_count: int


class OperationalWorkspace:
    """
    Composition-root wrapper for the Operational Dashboard (spec 005-
    enterprise-platform §10, Wave 3).

    Reuses ``WorkflowRepository``/``ApplicationRepository``'s existing
    aggregate methods — no new tracking mechanism, no materialized view or
    scheduled refresh job (an honest scope reduction from the original
    spec wording, documented in §10's implementation-correction note): both
    aggregates are cheap, indexed, on-demand queries at this platform's
    real data volumes. Gated by the existing ``Permission.READ_OPERATIONAL``
    (already defined, previously only consumed by ``GET /v1/metrics``).
    """

    def __init__(self, *, session: Session, job_queue: object | None = None) -> None:
        self._workflows = WorkflowRepository(session)
        self._applications = ApplicationRepository(session, AuditWriter(session))
        self._job_queue = job_queue

    def get_queue_depth(self, caller: AuthenticatedUser) -> list[QueueDepthRow]:
        require_permission(caller, Permission.READ_OPERATIONAL)
        rows = self._workflows.count_by_type_and_status(caller.tenant_id)
        return [
            QueueDepthRow(workflow_type=wt, status=status, count=count)
            for wt, status, count in rows
        ]

    def get_poison_jobs(self, caller: AuthenticatedUser) -> list[WorkflowStep]:
        require_permission(caller, Permission.READ_OPERATIONAL)
        return self._workflows.get_poison_steps(caller.tenant_id)

    def get_funnel(self, caller: AuthenticatedUser) -> list[ApplicationFunnelRow]:
        require_permission(caller, Permission.READ_OPERATIONAL)
        rows = self._applications.get_status_funnel(caller.tenant_id)
        return [
            ApplicationFunnelRow(status=status, count=count, avg_seconds_since_updated=avg_seconds)
            for status, count, avg_seconds in rows
        ]

    def get_job_queue_health(self, caller: AuthenticatedUser) -> JobQueueHealth:
        """
        Real, process-wide job queue health (spec 005-enterprise-platform
        §14, Wave 4 — Production Infrastructure) — reuses the existing
        ``JobQueue`` abstraction's own counters (``pending_count``/
        ``processing_count``/``dead_letter_count``, the last backed by the
        real dead-letter mechanism this wave added to ``RedisJobQueue``).
        Not tenant-scoped: the broker has no tenant concept — this is a
        process-wide operational signal, same as ``GET /v1/metrics``.
        """
        require_permission(caller, Permission.READ_OPERATIONAL)
        if self._job_queue is None:
            return JobQueueHealth(pending_count=0, processing_count=0, dead_letter_count=0)
        return JobQueueHealth(
            pending_count=self._job_queue.pending_count(),  # type: ignore[attr-defined]
            processing_count=self._job_queue.processing_count(),  # type: ignore[attr-defined]
            dead_letter_count=self._job_queue.dead_letter_count(),  # type: ignore[attr-defined]
        )


def get_operational_workspace(
    session: DbSession, container: Annotated[object, Depends(get_container)]
) -> OperationalWorkspace:
    from mil.kernel.container import Container
    from mil.kernel.job_queue import JobQueue

    job_queue = None
    if isinstance(container, Container) and container.is_registered(JobQueue):
        job_queue = container.resolve(JobQueue)
    return OperationalWorkspace(session=session, job_queue=job_queue)


@dataclass(frozen=True)
class FindingOutcomeRow:
    """One (lifecycle_state, count) row (spec 005-enterprise-platform §11, Wave 3)."""

    lifecycle_state: str
    count: int


@dataclass(frozen=True)
class PolicyOutcomeRow:
    """One (policy_version, outcome, count) row (spec 005 §11, Wave 3)."""

    policy_version: str
    outcome: str
    count: int


@dataclass(frozen=True)
class BusinessAnalyticsSnapshot:
    """
    A current-snapshot analytics view (spec 005-enterprise-platform §11,
    Wave 3 — Business Analytics). Every field is a real, on-demand
    aggregate over already-persisted data; none is a historical trend —
    this platform has no time-series metrics substrate (§10's
    implementation-correction note applies here too), so trend fields are
    simply not present rather than fabricated. ``average_review_duration_
    seconds`` is ``None`` when no review session has closed yet, an honest
    absence rather than a zero.
    """

    application_counts_by_status: tuple[tuple[str, int], ...]
    finding_outcomes: tuple[FindingOutcomeRow, ...]
    policy_outcomes: tuple[PolicyOutcomeRow, ...]
    document_count: int
    evidence_count: int
    average_review_duration_seconds: float | None


class BusinessAnalyticsWorkspace:
    """
    Composition-root wrapper for Business Analytics (spec 005-enterprise-
    platform §11, Wave 3).

    Composes existing repositories' aggregate methods
    (``ApplicationRepository.get_status_funnel``,
    ``FindingRepository.count_by_lifecycle_state``,
    ``PolicyRepository.count_by_version_and_outcome``,
    ``DocumentRepository``/``EvidenceRepository.count_for_tenant``,
    ``ReviewRepository.get_average_duration_seconds``) into one read-only
    snapshot. No ``ReportDefinition``/scheduled-report infrastructure is
    built (an honest scope reduction from the original spec wording,
    documented in §11's implementation-correction note) — this is a
    current-state view, not a scheduled report; RM productivity
    (per-owner Assignment counts) is likewise not included, disclosed as a
    real gap: ``Assignment`` has no ``tenant_id`` column, so a tenant-scoped
    breakdown would require a join through ``MortgageApplication`` not
    built this wave. Gated by a new ``Permission.READ_ANALYTICS``.
    """

    def __init__(self, *, session: Session) -> None:
        self._applications = ApplicationRepository(session, AuditWriter(session))
        self._findings = FindingRepository(session)
        self._policy = PolicyRepository(session)
        self._documents = DocumentRepository(session, AuditWriter(session))
        self._evidence = EvidenceRepository(session)
        self._review = ReviewRepository(session)

    def get_snapshot(self, caller: AuthenticatedUser) -> BusinessAnalyticsSnapshot:
        require_permission(caller, Permission.READ_ANALYTICS)
        tenant_id = caller.tenant_id

        funnel = self._applications.get_status_funnel(tenant_id)
        application_counts = tuple((status, count) for status, count, _avg in funnel)

        finding_rows = tuple(
            FindingOutcomeRow(lifecycle_state=state, count=count)
            for state, count in self._findings.count_by_lifecycle_state(tenant_id)
        )
        policy_rows = tuple(
            PolicyOutcomeRow(policy_version=version, outcome=outcome, count=count)
            for version, outcome, count in self._policy.count_by_version_and_outcome(tenant_id)
        )

        return BusinessAnalyticsSnapshot(
            application_counts_by_status=application_counts,
            finding_outcomes=finding_rows,
            policy_outcomes=policy_rows,
            document_count=self._documents.count_for_tenant(tenant_id),
            evidence_count=self._evidence.count_for_tenant(tenant_id),
            average_review_duration_seconds=self._review.get_average_duration_seconds(tenant_id),
        )


def get_business_analytics_workspace(session: DbSession) -> BusinessAnalyticsWorkspace:
    return BusinessAnalyticsWorkspace(session=session)


class PortalWorkspace:
    """
    Composition-root wrapper for the Customer Portal (spec 005-enterprise-
    platform §12, Wave 4).

    Composes ``mil.portal``'s own service with the Application bounded
    context (resolving a checklist item's/portal account's application via
    ``Party``) and the Document bounded context (reusing the *exact* upload
    contract — ``DocumentService.ingest_document`` + the existing
    ``DocumentIngestionTrigger`` — FR-CP-003: no separate upload pipeline).

    Portal-facing methods take a *verified* ``PortalSessionClaims`` (never
    a client-supplied ``applicationId``/``partyId``) and resolve the
    caller's own application strictly from ``claims.party_id`` — this is
    the concrete mechanism behind "a borrower can only ever reach their own
    application's checklist."
    """

    def __init__(
        self,
        *,
        session: Session,
        document_service: DocumentService,
        ingestion_trigger: DocumentIngestionTrigger,
    ) -> None:
        self._applications = ApplicationRepository(session, AuditWriter(session))
        self._repo = PortalRepository(session)
        self._service = PortalService(self._repo, AuditWriter(session))
        self._compliance = ComplianceService(ComplianceRepository(session), AuditWriter(session))
        self._documents = document_service
        self._ingestion_trigger = ingestion_trigger

    def _item_or_404(self, item_id: UUID) -> DocumentChecklistItem:
        item = self._repo.get_item_by_id(item_id)
        if item is None:
            raise NotFoundError("DocumentChecklistItem", item_id)
        return item

    # ------------------------------------------------------------------
    # Internal-staff methods (self-checking internal RBAC via PortalService)
    # ------------------------------------------------------------------

    def create_checklist_item(
        self,
        caller: AuthenticatedUser,
        *,
        application_id: UUID,
        label: str,
        document_type: str,
        party_id: UUID | None = None,
    ) -> DocumentChecklistItem:
        return self._service.create_checklist_item(
            caller,
            tenant_id=caller.tenant_id,
            application_id=application_id,
            label=label,
            document_type=document_type,
            party_id=party_id,
        )

    def get_checklist_for_application(
        self, caller: AuthenticatedUser, application_id: UUID
    ) -> list[DocumentChecklistItem]:
        return self._service.get_checklist_for_application(caller, application_id)

    def waive_item(self, caller: AuthenticatedUser, item_id: UUID) -> DocumentChecklistItem:
        item = self._item_or_404(item_id)
        return self._service.waive_item(caller, item)

    def invite_borrower(
        self, caller: AuthenticatedUser, *, party_id: UUID, email: str
    ) -> tuple[PortalAccount, str]:
        import hashlib

        email_hash = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
        return self._service.invite_borrower(
            caller, tenant_id=caller.tenant_id, party_id=party_id, email_hash=email_hash
        )

    # ------------------------------------------------------------------
    # Portal-facing methods (verified PortalSessionClaims — no internal RBAC)
    # ------------------------------------------------------------------

    def activate_account(self, *, party_id: UUID, raw_token: str, secret: bytes) -> str:
        """
        Activate a portal account and return a fresh session token.

        Also records an explicit, timestamped consent
        (`Permission.MANAGE_COMPLIANCE`-gated administration aside — this
        is the portal-safe consent primitive, no internal RBAC) at the
        exact moment of activation, per spec 005-enterprise-platform §16
        FR-SEC-002: "consent to data processing captured at portal account
        activation... never inferred from 'they used the portal.'" This is
        a real recorded event, not an implicit assumption.
        """
        from mil.portal.auth import issue_portal_token

        account = self._service.get_account_for_party(party_id)
        if account is None:
            raise NotFoundError("PortalAccount", party_id)
        self._service.activate_account(account, raw_token)
        self._compliance.record_consent(
            tenant_id=account.tenant_id,
            consent_type="PORTAL_DATA_PROCESSING",
            consent_text_version="v1",
            portal_account_id=account.id,
        )
        return issue_portal_token(
            account_id=account.id,
            party_id=account.party_id,
            tenant_id=account.tenant_id,
            secret=secret,
        )

    def get_checklist_for_claims(self, claims: PortalSessionClaims) -> list[DocumentChecklistItem]:
        party = self._applications.get_party_by_id(claims.party_id)
        if party is None:
            raise NotFoundError("Party", claims.party_id)
        return self._service.get_items_for_application(party.application_id)

    def get_status_for_claims(self, claims: PortalSessionClaims) -> MortgageApplication:
        party = self._applications.get_party_by_id(claims.party_id)
        if party is None:
            raise NotFoundError("Party", claims.party_id)
        application = self._applications.get_by_id(party.application_id)
        if application is None:
            raise NotFoundError("MortgageApplication", party.application_id)
        return application

    def upload_for_claims(
        self,
        claims: PortalSessionClaims,
        *,
        item_id: UUID,
        content: bytes,
        original_filename: str,
        document_type: str,
    ) -> DocumentChecklistItem:
        """
        Fulfill a checklist item by uploading its document, reusing the
        exact internal upload contract (FR-CP-003).

        A synthetic ``AuthenticatedUser`` with ``Role.PORTAL_ACCOUNT`` (the
        narrowest possible role — ``Permission.UPLOAD_DOCUMENT`` only, see
        that role's own docstring in ``mil.kernel.security``) satisfies
        ``DocumentService.ingest_document``'s existing RBAC check without
        adding a second upload code path. The checklist item's own
        ``application_id`` — not a client-supplied value — is what the
        document gets attached to, and the item must belong to the
        claims-resolved party's application, or this raises ``NotFoundError``
        (a borrower can never fulfill another application's checklist item).
        """
        party = self._applications.get_party_by_id(claims.party_id)
        if party is None:
            raise NotFoundError("Party", claims.party_id)
        item = self._item_or_404(item_id)
        if item.application_id != party.application_id:
            raise NotFoundError("DocumentChecklistItem", item_id)

        portal_actor = AuthenticatedUser(
            user_id=UserId(claims.account_id),
            tenant_id=TenantId(claims.tenant_id),
            roles=frozenset({Role.PORTAL_ACCOUNT}),
        )
        document = self._documents.ingest_document(
            portal_actor,
            application_id=party.application_id,
            content=content,
            original_filename=original_filename,
            mime_type=document_type,
            party_id=party.id,
        )
        self._ingestion_trigger.trigger(document)
        return self._service.fulfill_item(item, document.id)


def get_portal_workspace(
    session: DbSession,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    ingestion_trigger: Annotated[DocumentIngestionTrigger, Depends(get_document_ingestion_trigger)],
) -> PortalWorkspace:
    return PortalWorkspace(
        session=session, document_service=document_service, ingestion_trigger=ingestion_trigger
    )


@dataclass(frozen=True)
class AccessLogEntry:
    """One audit event surfaced in a compliance access-log report (spec 005 §16, Wave 4)."""

    event_type: str
    actor_id: UUID | None
    actor_type: str
    occurred_at: datetime


class ComplianceWorkspace:
    """
    Composition-root wrapper for Security & Compliance (spec 005-
    enterprise-platform §16, Wave 4).

    Composes ``mil.compliance``'s own service (retention policy CRUD) with
    the Audit bounded context's existing, already-persisted `AuditEvent`
    table (FR-SEC-003's access-log report) — no new parallel logging
    mechanism, per the spec's own explicit requirement and this section's
    implementation-correction note (a direct on-demand query, not a
    persisted `ComplianceReportRequest`/async job).
    """

    def __init__(self, *, session: Session) -> None:
        self._service = ComplianceService(ComplianceRepository(session), AuditWriter(session))
        self._audit_repo = AuditRepository(session)

    def set_retention_policy(
        self,
        caller: AuthenticatedUser,
        *,
        data_category: str,
        retention_period_days: int,
        action: str,
    ) -> DataRetentionPolicy:
        return self._service.set_retention_policy(
            caller,
            tenant_id=caller.tenant_id,
            data_category=data_category,
            retention_period_days=retention_period_days,
            action=action,
        )

    def get_retention_policies(self, caller: AuthenticatedUser) -> list[DataRetentionPolicy]:
        return self._service.get_retention_policies(caller, caller.tenant_id)

    def get_access_log(
        self,
        caller: AuthenticatedUser,
        *,
        application_id: UUID,
        from_date: datetime,
        to_date: datetime,
    ) -> list[AccessLogEntry]:
        require_permission(caller, Permission.READ_COMPLIANCE)
        events = self._audit_repo.get_for_application_in_range(
            application_id, from_date=from_date, to_date=to_date
        )
        return [
            AccessLogEntry(
                event_type=e.event_type,
                actor_id=e.actor_id,
                actor_type=e.actor_type,
                occurred_at=e.occurred_at,
            )
            for e in events
        ]


def get_compliance_workspace(session: DbSession) -> ComplianceWorkspace:
    return ComplianceWorkspace(session=session)


def get_review_service(session: DbSession) -> ReviewService:
    """
    Build and return a ``ReviewService`` wired to the request session.

    Used directly by the Collaboration routes (`mil.api.v1.comments`) —
    distinct from `FindingReviewActions` above, which composes Finding +
    Review + Policy for the verify/override composition points. Comments
    only need Review's own repository/service, no cross-context composition.
    """
    audit = AuditWriter(session)
    repo = ReviewRepository(session)
    return ReviewService(repo, audit)


class FindingReviewActions:
    """
    Composition-root wrapper for the Finding verify/override HTTP actions.

    Bound to the request's session, this composes the Finding, Review, and
    Policy bounded contexts' existing repositories/services for the two HTTP
    composition points (``POST /v1/findings/{id}/verify``,
    ``POST /v1/findings/{id}/override``) — mirroring ``FindingTrigger``/
    ``DocumentIngestionTrigger`` above. It exists so
    ``mil.api.v1.findings`` depends on a type re-exported from this module
    rather than importing ``mil.review``/``mil.policy`` directly.

    ``mil.review.service.ReviewService.approve_finding``/``override_finding``
    perform the actual state transition and audit recording (see
    ``mil.review.service`` — a synchronous ``AuditWriter`` call in the same
    transaction, never the outbox); this class only resolves the Finding and
    its Review Session and reports the Policy attribution version findings.py
    needs to build the response.
    """

    def __init__(self, *, session: Session) -> None:
        self._findings = FindingRepository(session)
        self._reviews = ReviewRepository(session)
        self._policy = PolicyRepository(session)
        self._review_service = ReviewService(self._reviews, AuditWriter(session))

    def get_finding_or_404(self, finding_id: UUID) -> Finding:
        finding = self._findings.get_by_id(finding_id)
        if finding is None:
            raise NotFoundError("Finding", finding_id)
        return finding

    def get_review_session_or_404(self, finding_id: UUID) -> ReviewSession:
        session = self._reviews.get_session_for_finding(finding_id)
        if session is None:
            raise NotFoundError("ReviewSession", finding_id)
        return session

    def get_review_status(self, finding_id: UUID) -> str | None:
        """Return the Review Session status for a Finding, or ``None`` if none exists yet."""
        session = self._reviews.get_session_for_finding(finding_id)
        return session.status if session is not None else None

    def get_review_session(self, finding_id: UUID) -> ReviewSession | None:
        """Return the Review Session for a Finding, or ``None`` if none exists yet."""
        return self._reviews.get_session_for_finding(finding_id)

    def policy_version_for(self, finding_id: UUID) -> str | None:
        """Return the most recent Policy evaluation's version for a Finding, if any."""
        results = self._policy.get_for_finding(finding_id)
        if not results:
            return None
        return max(results, key=lambda r: r.created_at).policy_version

    def _authorize_resolution(self, user: AuthenticatedUser, session: ReviewSession) -> None:
        """
        Enforce the escalation-ownership rule when resolving (verify,
        override, or reject) a session currently in ``ESCALATED`` status.

        Per the approved design: a session escalated to a specific person
        (``escalated_to_user_id`` set) may only be resolved by that person;
        otherwise it may be resolved by any holder of ``VERIFY_FINDING``/
        ``OVERRIDE_FINDING`` whose roles include ``escalated_to_role``. A
        session that is *not* currently escalated has no extra restriction
        beyond the base ``VERIFY_FINDING``/``OVERRIDE_FINDING`` permission
        check the caller already performed.
        """
        if session.status != ESCALATED:
            return

        if session.escalated_to_user_id is not None:
            if user.user_id != session.escalated_to_user_id:
                raise AuthorizationError(
                    "This finding was escalated to a specific reviewer; only they may resolve it."
                )
            return

        if session.escalated_to_role is not None and session.escalated_to_role not in user.roles:
            raise AuthorizationError(
                f"This finding was escalated to the {session.escalated_to_role} role."
            )

    def _ensure_in_review(self, session: ReviewSession, user: AuthenticatedUser) -> None:
        """
        Auto-assign the acting user as reviewer if the session is still
        ``PENDING_REVIEW`` (real, pre-existing gap fixed here): the Review
        state machine only permits ``approve``/``reject``/``override`` from
        ``IN_REVIEW``, never directly from ``PENDING_REVIEW``
        (``ReviewSession._VALID_TRANSITIONS``) — and nothing in this HTTP
        layer ever called the domain's own ``assign_reviewer`` before this
        fix, so verify/override could never succeed on a fresh finding
        (confirmed live: a brand-new session's first verify attempt raised
        ``InvalidStateTransitionError`` — ``PENDING_REVIEW`` -> ``APPROVED``
        is not a valid edge). The first person to act on a pending finding
        becoming its assigned reviewer matches how underwriting queues work
        in practice; escalating is unaffected (``PENDING_REVIEW ->
        ESCALATED`` is already a direct, valid edge).
        """
        if session.status == PENDING_REVIEW:
            self._review_service.assign_reviewer(
                session, reviewer_user_id=user.user_id, assigned_by_user_id=user.user_id
            )

    def verify(self, user: AuthenticatedUser, finding_id: UUID) -> ReviewSession:
        """Approve the finding under review (spec 002 FR-033-034, FR-052)."""
        require_permission(user, Permission.VERIFY_FINDING)
        session = self.get_review_session_or_404(finding_id)
        self._authorize_resolution(user, session)
        self._ensure_in_review(session, user)
        return self._review_service.approve_finding(session, actor_user_id=user.user_id)

    def override(
        self,
        user: AuthenticatedUser,
        finding_id: UUID,
        *,
        reason: str,
        previous_value: str,
        new_value: str,
    ) -> ReviewSession:
        """Override the finding under review (spec 002 FR-033-034, FR-052-053)."""
        require_permission(user, Permission.OVERRIDE_FINDING)
        session = self.get_review_session_or_404(finding_id)
        self._authorize_resolution(user, session)
        self._ensure_in_review(session, user)
        return self._review_service.override_finding(
            session,
            actor_user_id=user.user_id,
            reason=reason,
            previous_value=previous_value,
            new_value=new_value,
        )

    def escalate(
        self,
        user: AuthenticatedUser,
        finding_id: UUID,
        *,
        reason: str,
        target_role: str,
        target_user_id: UUID | None = None,
    ) -> ReviewSession:
        """
        Escalate the finding under review to another role's (or, when
        provided, a specific person's) queue (spec 002 FR-054).

        Unlike ``verify``/``override``, escalating never requires the
        escalation-ownership check: any holder of ``ESCALATE_FINDING`` may
        escalate a finding they currently hold, including re-escalating one
        already escalated to someone else (module docstring: ``ESCALATED ->
        ESCALATED`` is a valid transition).
        """
        require_permission(user, Permission.ESCALATE_FINDING)
        session = self.get_review_session_or_404(finding_id)
        return self._review_service.escalate_finding(
            session,
            actor_user_id=user.user_id,
            reason=reason,
            target_role=target_role,
            target_user_id=target_user_id,
        )


def get_finding_review_actions(session: DbSession) -> FindingReviewActions:
    """Build and return ``FindingReviewActions`` wired to the request session."""
    return FindingReviewActions(session=session)


AppService = Annotated[ApplicationService, Depends(get_application_service)]
DocService = Annotated[DocumentService, Depends(get_document_service)]
DocIngestionTriggerDep = Annotated[
    DocumentIngestionTrigger, Depends(get_document_ingestion_trigger)
]
FindingTriggerDep = Annotated[FindingTrigger, Depends(get_finding_trigger)]
CopilotServiceDep = Annotated[CopilotService, Depends(get_copilot_service)]
EvidenceServiceDep = Annotated[EvidenceService, Depends(get_evidence_service)]
FindingServiceDep = Annotated[FindingService, Depends(get_finding_service)]
AuditRepositoryDep = Annotated[AuditRepository, Depends(get_audit_repository)]
StorageProviderDep = Annotated[StorageProvider, Depends(get_storage_provider)]
FindingReviewActionsDep = Annotated[FindingReviewActions, Depends(get_finding_review_actions)]
IdentityServiceDep = Annotated[IdentityService, Depends(get_identity_service)]
PolicyServiceDep = Annotated[PolicyService, Depends(get_policy_service)]
ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]
AssignmentServiceDep = Annotated[AssignmentService, Depends(get_assignment_service)]
RmWorkspaceDep = Annotated[RmWorkspace, Depends(get_rm_workspace)]
IntegrationWorkspaceDep = Annotated[IntegrationWorkspace, Depends(get_integration_workspace)]
SearchWorkspaceDep = Annotated[SearchWorkspace, Depends(get_search_workspace)]
NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
NotificationWorkspaceDep = Annotated[NotificationWorkspace, Depends(get_notification_workspace)]
BorrowerIdentityWorkspaceDep = Annotated[
    BorrowerIdentityWorkspace, Depends(get_borrower_identity_workspace)
]
CrossApplicationIntelligenceWorkspaceDep = Annotated[
    CrossApplicationIntelligenceWorkspace, Depends(get_cross_application_intelligence_workspace)
]
OperationalWorkspaceDep = Annotated[OperationalWorkspace, Depends(get_operational_workspace)]
BusinessAnalyticsWorkspaceDep = Annotated[
    BusinessAnalyticsWorkspace, Depends(get_business_analytics_workspace)
]
PortalWorkspaceDep = Annotated[PortalWorkspace, Depends(get_portal_workspace)]
ComplianceWorkspaceDep = Annotated[ComplianceWorkspace, Depends(get_compliance_workspace)]
