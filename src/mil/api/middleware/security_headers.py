"""
Security headers middleware — US2 Sprint 8 (Production Hardening).

Adds standard defensive HTTP response headers to every response. This is a
narrow, well-understood hardening step — it does not change the
authentication architecture (still bearer-token based, see
``mil.api.deps``) and does not add any new trust boundary.

Headers applied:

- ``X-Content-Type-Options: nosniff`` — stop browsers from MIME-sniffing
  responses into an executable content type.
- ``X-Frame-Options: DENY`` — the API is not meant to be framed.
- ``Referrer-Policy: no-referrer`` — do not leak request URLs (which may
  contain identifiers) via the Referer header on outbound links.
- ``Cache-Control: no-store`` — API responses carry sensitive mortgage
  data (Engineering Constitution Principle V); never let an intermediary
  or browser cache them.
- ``Strict-Transport-Security`` — only set when the request arrived over
  HTTPS, so local HTTP development is unaffected.

Dependency rule: imports only from Starlette/FastAPI and the Python
standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defence-in-depth HTTP response headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
