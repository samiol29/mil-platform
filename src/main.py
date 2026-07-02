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
from mil.api.v1.applications import router as applications_router
from mil.api.v1.auth import router as auth_router
from mil.api.v1.copilot import application_copilot_router
from mil.api.v1.copilot import router as copilot_router
from mil.api.v1.documents import router as documents_router
from mil.api.v1.ops import router as ops_router
from mil.identity.provider import DevBearerIdentityProvider, IdentityProvider
from mil.kernel.config import Settings, get_settings
from mil.kernel.container import Container, ProductionReadinessError, build_container
from mil.kernel.observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Startup:
        - Load settings from environment (fails fast on invalid
          configuration — see ``Settings`` validators).
        - Configure structured JSON logging.
        - Build the DI container, which registers and validates all
          required providers (fails fast via ``ProviderRegistry.validate()``
          if any required provider is missing — see
          ``mil.kernel.container.build_container``).
        - Create the synchronous SQLAlchemy session factory.
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
    container = build_container(settings)
    _register_identity_provider(container, settings)
    engine = create_engine(settings.database_sync_url)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

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
    app.include_router(copilot_router)
    app.include_router(application_copilot_router)

    return app


app: FastAPI = create_app()
