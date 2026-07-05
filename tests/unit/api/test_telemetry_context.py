"""
Backend Freeze Patch v1.0 — fix 4: correlation-id propagation.

Proves the pure-ASGI ``TelemetryMiddleware`` binds request/correlation IDs to
the ``LogContext`` in a way that is visible to the downstream request handler
(the defect the previous ``BaseHTTPMiddleware`` implementation had), and still
echoes the IDs on the response.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mil.api.middleware.telemetry import TelemetryMiddleware
from mil.kernel.observability import get_log_context


async def _probe(request: object) -> JSONResponse:
    ctx = get_log_context()
    return JSONResponse(
        {
            "correlation_id": ctx.correlation_id,
            "request_id": ctx.request_id,
            "component": ctx.component,
        }
    )


def _client() -> TestClient:
    app = Starlette(routes=[Route("/probe", _probe)])
    app.add_middleware(TelemetryMiddleware)
    return TestClient(app)


def test_correlation_id_visible_to_handler() -> None:
    response = _client().get("/probe", headers={"X-Correlation-ID": "corr-123"})
    body = response.json()
    # The handler saw the correlation id bound by the middleware.
    assert body["correlation_id"] == "corr-123"
    assert body["component"] == "api"
    # And it is echoed back on the response.
    assert response.headers["X-Correlation-ID"] == "corr-123"


def test_request_id_generated_and_echoed() -> None:
    response = _client().get("/probe")
    body = response.json()
    assert body["request_id"]  # a request id was generated
    # Correlation id defaults to the request id when no header is supplied.
    assert body["correlation_id"] == body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]
