"""
MIL Platform API — application entry point.

Creates the FastAPI application, mounts all v1 routers, registers exception
handlers, and wires up the dependency injection container and database session
factory in the lifespan context.

Usage::

    # Development
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

    # Production (via container entrypoint)
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

The module-level ``app`` is the ASGI callable expected by Uvicorn and
production WSGI/ASGI servers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mil.api.errors import register_error_handlers
from mil.api.middleware.security_headers import SecurityHeadersMiddleware
from mil.api.middleware.telemetry import TelemetryMiddleware
from mil.api.v1.admin import router as admin_router
from mil.api.v1.analytics import router as analytics_router
from mil.api.v1.applications import router as applications_router
from mil.api.v1.assignments import portfolio_router as rm_portfolio_router
from mil.api.v1.assignments import router as assignments_router
from mil.api.v1.audit import router as audit_router
from mil.api.v1.auth import router as auth_router
from mil.api.v1.borrower_identity import router as borrower_identity_router
from mil.api.v1.checklist import router as checklist_router
from mil.api.v1.compliance import router as compliance_router
from mil.api.v1.comments import router as comments_router
from mil.api.v1.copilot import application_copilot_router
from mil.api.v1.copilot import router as copilot_router
from mil.api.v1.documents import router as documents_router
from mil.api.v1.evidence import router as evidence_router
from mil.api.v1.findings import router as findings_router
from mil.api.v1.integrations import application_integration_router
from mil.api.v1.integrations import router as integrations_router
from mil.api.v1.notifications import router as notifications_router
from mil.api.v1.operational import router as operational_router
from mil.api.v1.ops import router as ops_router
from mil.api.v1.portal import router as portal_router
from mil.api.v1.policy import application_policy_router
from mil.api.v1.policy import approvals_router as policy_approvals_router
from mil.api.v1.policy import router as policy_router
from mil.api.v1.search import router as search_router
from mil.identity.dev_seed import seed_development_identity
from mil.identity.provider import DevBearerIdentityProvider, IdentityProvider
from mil.kernel.config import Settings, get_settings
from mil.kernel.container import Container, ProductionReadinessError, build_container
from mil.kernel.model_registration import register_all_models
from mil.kernel.observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Startup:
        - Load settings from environment (fails fast on invalid
          configuration — see ``Settings`` validators).
        - Configure structured JSON logging.
        - Register every bounded context's ORM models on the shared
          ``Base.metadata`` (``mil.kernel.model_registration
          .register_all_models``) before any request can flush — otherwise a
          write whose foreign key targets a table nothing under this
          module's own router imports happens to touch (e.g. a
          ``ReviewSession`` flush resolving its FK into
          ``orchestrator.workflow_runs``) raises
          ``sqlalchemy.exc.NoReferencedTableError`` the first time, and only
          the first time, that specific write path is exercised — a real
          crash reproduced live, not a hypothetical. Mirrors
          ``workers.bootstrap.build_worker_context``'s identical call for
          worker processes.
        - Build the DI container, which registers and validates all
          required providers (fails fast via ``ProviderRegistry.validate()``
          if any required provider is missing — see
          ``mil.kernel.container.build_container``).
        - Create the synchronous SQLAlchemy session factory.
        - In development only, seed the built-in development user so that
          requests authenticated with ``Bearer dev`` satisfy foreign keys on
          a freshly migrated database (see
          ``mil.identity.dev_seed.seed_development_identity``). Never runs
          outside development.
        - Store settings, container, and the session factory on
          ``app.state`` for dependency access.

    Any exception raised during startup propagates out of this context
    manager, which aborts ASGI startup — the process never starts serving
    traffic with a half-initialised configuration (Sprint 8 — Production
    Hardening: startup failures must be explicit).

    Shutdown:
        - Dispose of the SQLAlchemy connection pool.
    """
    settings: Settings = get_settings()
    configure_logging(log_level=settings.mil_log_level, service_name=settings.otel_service_name)
    register_all_models()
    container = build_container(settings)
    _register_identity_provider(container, settings)
    engine = create_engine(settings.database_sync_url)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    if settings.is_development():
        seed_development_identity(factory)

    app.state.settings = settings
    app.state.container = container
    app.state.session_factory = factory

    yield

    engine.dispose()


def _register_identity_provider(container: Container, settings: Settings) -> None:
    """
    Register the request-authentication ``IdentityProvider`` in the container.

    Development registers ``DevBearerIdentityProvider`` (the existing local
    development authentication, now resolved through DI). Staging and
    production require a signature-verifying provider; none ships in this
    freeze, so a non-development process fails to start rather than accept
    unsigned tokens (Backend Freeze Patch v1.0, fix 1).
    """
    if settings.is_development():
        container.register_singleton(
            IdentityProvider,  # type: ignore[type-abstract]
            DevBearerIdentityProvider,
        )
        return

    if not container.is_registered(IdentityProvider):
        raise ProductionReadinessError(
            "No IdentityProvider is registered for a non-development environment "
            f"(MIL_ENV={settings.mil_env}). Register a signature-verifying "
            "(e.g. OIDC/JWKS) IdentityProvider before serving traffic — unsigned "
            "development tokens are refused outside development."
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Assemble and return the FastAPI application.

    Accepts an optional ``settings`` override for testing.  When omitted,
    settings are loaded from environment variables in the lifespan handler.

    Args:
        settings: Optional pre-constructed settings (used in integration tests).

    Returns:
        Configured FastAPI application with all routers and error handlers.
    """
    app = FastAPI(
        title="Mortgage Intelligence Layer (MIL)",
        version="1.0.0",
        description=(
            "API-first intelligence layer for mortgage document processing. "
            "MIL transforms source documents into structured, explainable "
            "evidence that supports human decision makers throughout the "
            "mortgage review lifecycle. MIL never approves or rejects loan "
            "applications — human reviewers retain decision authority at "
            "every stage."
        ),
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
        redoc_url="/v1/redoc",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    # Middleware executes outermost-to-innermost in reverse registration
    # order for responses; both apply to every request regardless of route.
    app.add_middleware(TelemetryMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(auth_router)
    app.include_router(ops_router)
    app.include_router(applications_router)
    app.include_router(documents_router)
    app.include_router(evidence_router)
    app.include_router(findings_router)
    app.include_router(audit_router)
    app.include_router(copilot_router)
    app.include_router(application_copilot_router)
    app.include_router(admin_router)
    app.include_router(policy_router)
    app.include_router(policy_approvals_router)
    app.include_router(application_policy_router)
    app.include_router(comments_router)
    app.include_router(assignments_router)
    app.include_router(rm_portfolio_router)
    app.include_router(integrations_router)
    app.include_router(application_integration_router)
    app.include_router(search_router)
    app.include_router(notifications_router)
    app.include_router(borrower_identity_router)
    app.include_router(operational_router)
    app.include_router(analytics_router)
    app.include_router(checklist_router)
    app.include_router(compliance_router)
    app.include_router(portal_router)

    return app


app: FastAPI = create_app()
