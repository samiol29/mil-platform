"""
FastAPI exception handlers for the MIL Platform API.

Maps every ``MILError`` subclass to an appropriate HTTP status code and
returns a consistent ``APIErrorResponse`` JSON payload.  All other uncaught
exceptions produce a generic 500 response so that internal details are never
leaked to API clients.

Registered once in ``create_app()`` via ``register_error_handlers(app)``.

Dependency rule: imports only from ``mil.kernel.errors``, FastAPI, and the
Python standard library.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request  # noqa: TC002
from fastapi.responses import JSONResponse

from mil.kernel.errors import (
    APIErrorDetail,
    APIErrorResponse,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    InvalidStateTransitionError,
    MILError,
    NotFoundError,
    ValidationError,
)

log = logging.getLogger(__name__)

# An INTERNAL_ERROR code is not yet in ErrorCode; use a stable string literal.
_CODE_INTERNAL_ERROR = "INTERNAL_ERROR"


def _field_details(exc: MILError) -> list[APIErrorDetail]:
    """Extract a field-level detail list from a MIL exception, if available."""
    field = exc.details.get("field")
    if field is not None:
        return [APIErrorDetail(field=str(field), message=exc.message)]
    return []


def register_error_handlers(app: FastAPI) -> None:
    """Register all MIL exception → HTTP response mappings on ``app``."""

    @app.exception_handler(AuthenticationError)
    async def _handle_authentication(_request: Request, exc: AuthenticationError) -> JSONResponse:
        # spec 005-enterprise-platform §12, Wave 4 — found during the
        # Customer Portal module's implementation: AuthenticationError had
        # no dedicated handler here (only `get_current_user`'s own manual
        # try/except converted it to a 401 internally), so any other code
        # path raising it directly — e.g. ``PortalAccount.activate()``
        # rejecting a bad token — fell through to the generic MILError
        # handler and returned a misleading 500. A real, pre-existing gap,
        # fixed here rather than worked around in the portal route.
        return JSONResponse(
            status_code=401,
            content=APIErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(AuthorizationError)
    async def _handle_authorization(_request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=APIErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(NotFoundError)
    async def _handle_not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=APIErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(ValidationError)
    async def _handle_validation(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=APIErrorResponse(
                code=exc.code,
                message=exc.message,
                details=_field_details(exc),
            ).model_dump(),
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def _handle_state_transition(
        _request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=APIErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(ConflictError)
    async def _handle_conflict(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=APIErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(DomainError)
    async def _handle_domain(_request: Request, exc: DomainError) -> JSONResponse:
        # Catch-all for any DomainError subclass not handled above.
        return JSONResponse(
            status_code=422,
            content=APIErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(MILError)
    async def _handle_mil(_request: Request, exc: MILError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=APIErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled exception in request handler", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=APIErrorResponse(
                code=_CODE_INTERNAL_ERROR,
                message="An unexpected error occurred.",
            ).model_dump(),
        )
