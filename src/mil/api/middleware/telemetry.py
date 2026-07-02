"""
Telemetry middleware — request correlation and basic HTTP metrics
(US2 Sprint 8 — Production Hardening; Backend Freeze Patch v1.0).

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

Why pure ASGI (not ``BaseHTTPMiddleware``): Starlette runs a
``BaseHTTPMiddleware.dispatch`` in a *separate* task from the endpoint, so a
``contextvars`` value set there does not propagate into the route handler or
the service calls it makes — the request_id/correlation_id would be bound but
absent from the very logs they exist to correlate. A pure ASGI middleware sets
the context in the *same* task that then awaits the downstream app, so the
``LogContext`` is visible to the handler (and, because Starlette copies the
context when dispatching sync endpoints to the threadpool, to sync handlers
too). The logging fields and behaviour are otherwise unchanged from Sprint 8
(Backend Freeze Patch v1.0, fix 4).

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

from starlette.datastructures import Headers, MutableHeaders

from mil.kernel.metrics import MetricName
from mil.kernel.observability import LogContext, reset_log_context, set_log_context

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_HEADER = "X-Request-ID"
_CORRELATION_ID_HEADER = "X-Correlation-ID"


class TelemetryMiddleware:
    """
    Pure-ASGI middleware that binds request correlation IDs to the log context
    (visible to downstream handlers) and records basic HTTP metrics.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        correlation_id = headers.get(_CORRELATION_ID_HEADER) or request_id

        # Bound in this task, before awaiting the app, so the endpoint and the
        # services it calls see the same request_id/correlation_id.
        token = set_log_context(
            LogContext(request_id=request_id, correlation_id=correlation_id, component="api")
        )

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[_REQUEST_ID_HEADER] = request_id
                response_headers[_CORRELATION_ID_HEADER] = correlation_id
            await send(message)

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._record_metrics(scope, elapsed_ms)
            reset_log_context(token)

    @staticmethod
    def _record_metrics(scope: Scope, elapsed_ms: float) -> None:
        from mil.kernel.container import Container
        from mil.kernel.observability import MetricEmitter

        app = scope.get("app")
        container = getattr(getattr(app, "state", None), "container", None)
        if not isinstance(container, Container) or not container.is_registered(MetricEmitter):
            return

        metrics = container.resolve(MetricEmitter)  # type: ignore[type-abstract]
        metrics.increment(MetricName.HTTP_REQUESTS_TOTAL)
        metrics.histogram(MetricName.HTTP_REQUEST_DURATION_MS, elapsed_ms)
        if "/copilot" in scope.get("path", ""):
            metrics.increment(MetricName.COPILOT_REQUESTS_TOTAL)
