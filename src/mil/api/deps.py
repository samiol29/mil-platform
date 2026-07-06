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
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from mil.application.repository import ApplicationRepository
from mil.application.service import ApplicationService
from mil.audit.repository import AuditRepository
from mil.audit.writer import AuditWriter
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
from mil.kernel.config import Settings
from mil.kernel.errors import AuthenticationError, AuthorizationError, NotFoundError
from mil.kernel.providers.storage import StorageProvider
from mil.kernel.security import AuthenticatedUser, Permission, require_permission
from mil.kernel.types import UserId
from mil.policy.repository import PolicyRepository
from mil.review.models import ESCALATED, PENDING_REVIEW
from mil.review.repository import ReviewRepository
from mil.review.service import ReviewService

if TYPE_CHECKING:
    from collections.abc import Generator

    from mil.application.models import MortgageApplication
    from mil.document.models import Document
    from mil.finding.models import Finding
    from mil.identity.provider import TokenClaims
    from mil.kernel.container import Container
    from mil.orchestrator.models import WorkflowRun
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
