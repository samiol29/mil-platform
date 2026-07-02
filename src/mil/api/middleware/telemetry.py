"""
Telemetry middleware — request correlation and basic HTTP metrics
(US2 Sprint 8 — Production Hardening).

Wraps every inbound request:

- Assigns (or propagates from ``X-Request-ID`` / ``X-Correlation-ID``
  headers) a request_id and correlation_id, binding them to the structured
  ``LogContext`` for the duration of the request so every log line emitted
  while handling it carries both (Engineering Constitution Principle VIII;
  Sprint 8 logging requirements: correlation_id, request_id, component,
  severity on every log record).
- Records basic HTTP metrics — total requests, response time, and a
  dedicated Copilot request counter — via the ``MetricEmitter`` registered
  in the DI container. This is the platform's existing metrics
  abstraction, not a tracing pipeline; no spans are created here.

If the DI container is not yet available on ``app.state`` (e.g. a
``TestClient`` built without triggering the ASGI lifespan), metrics are
silently skipped — request correlation still works regardless, since it
depends only on the module-level ``LogContext`` context variable.

Dependency rule: imports only from ``mil.kernel`` and Starlette/FastAPI.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from mil.kernel.metrics import MetricName
from mil.kernel.observability import LogContext, reset_log_context, set_log_context

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response

_REQUEST_ID_HEADER = "X-Request-ID"
_CORRELATION_ID_HEADER = "X-Correlation-ID"


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Binds request correlation IDs to the log context and records basic HTTP metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        correlation_id = request.headers.get(_CORRELATION_ID_HEADER) or request_id

        token = set_log_context(
            LogContext(request_id=request_id, correlation_id=correlation_id, component="api")
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._record_metrics(request, elapsed_ms)
            reset_log_context(token)

        response.headers[_REQUEST_ID_HEADER] = request_id
        response.headers[_CORRELATION_ID_HEADER] = correlation_id
        return response

    @staticmethod
    def _record_metrics(request: Request, elapsed_ms: float) -> None:
        from mil.kernel.container import Container
        from mil.kernel.observability import MetricEmitter

        container = getattr(request.app.state, "container", None)
        if not isinstance(container, Container) or not container.is_registered(MetricEmitter):
            return

        metrics = container.resolve(MetricEmitter)  # type: ignore[type-abstract]
        metrics.increment(MetricName.HTTP_REQUESTS_TOTAL)
        metrics.histogram(MetricName.HTTP_REQUEST_DURATION_MS, elapsed_ms)
        if "/copilot" in request.url.path:
            metrics.increment(MetricName.COPILOT_REQUESTS_TOTAL)
