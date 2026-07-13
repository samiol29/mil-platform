"""
Observability primitives for the MIL Platform.

This module provides three categories of observability infrastructure:

1. **Structured logging** — a JSON formatter and logger factory that pre-wire
   the mandatory audit fields (timestamp, severity, service, request_id,
   application_id, user_id, event_type) into every log record.  The request-
   scoped fields are injected via a context variable that middleware sets on
   each incoming request.

2. **Trace context propagation** — a lightweight ``TraceContext`` dataclass and
   a context variable for propagating trace identifiers through the async
   request lifecycle without thread-local storage.

3. **Metric emitter interface** — an abstract ``MetricEmitter`` base class and a
   no-op implementation (``NoOpMetricEmitter``) used in development and tests.
   Production deployments register a concrete OpenTelemetry-backed emitter
   through the DI container.

Mandatory log fields (Engineering Constitution, Principle VIII — Auditability):
    timestamp         ISO 8601 UTC timestamp of the log event
    severity          Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    service           Service name from settings (e.g. "mil-api")
    request_id        Unique identifier for the inbound HTTP request
    application_id    Mortgage application being processed (if applicable)
    user_id           Authenticated user performing the action (if applicable)
    event_type        Machine-readable event category (e.g. "finding.verified")

Dependency rule: this module imports only from the Python standard library.
No bounded context code should be imported here.
"""

from __future__ import annotations

import contextvars
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Reserved logging.LogRecord attributes — excluded from the structured payload
# to avoid duplicating fields that the formatter handles explicitly.
# ---------------------------------------------------------------------------

_RESERVED_LOG_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "taskName",
        # Fields we write explicitly
        "timestamp",
        "severity",
        "service",
        "request_id",
        "correlation_id",
        "application_id",
        "tenant_id",
        "user_id",
        "component",
        "event_type",
        "logger",
    }
)


# ---------------------------------------------------------------------------
# Log context — per-request structured fields
# ---------------------------------------------------------------------------


@dataclass
class LogContext:
    """
    Per-request context fields pre-wired into every structured log record.

    Set by the telemetry middleware (T023) at request ingress.  Middleware
    calls ``set_log_context`` with values extracted from the incoming request
    headers and the ``AuthenticatedUser`` context.
    """

    service: str = "mil-api"
    request_id: str = ""
    correlation_id: str = ""
    application_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    component: str = ""


_current_log_context: contextvars.ContextVar[LogContext | None] = contextvars.ContextVar(
    "current_log_context",
    default=None,
)


def set_log_context(ctx: LogContext) -> contextvars.Token[LogContext | None]:
    """
    Bind a ``LogContext`` to the current request's context variable.

    Returns the reset token so the caller can restore the previous context
    (e.g. in tests or when processing nested async tasks).
    """
    return _current_log_context.set(ctx)


def get_log_context() -> LogContext:
    """Return the log context for the current request, or a blank default."""
    ctx = _current_log_context.get()
    return ctx if ctx is not None else LogContext()


def reset_log_context(token: contextvars.Token[LogContext | None]) -> None:
    """Restore the log context to its value before the matching ``set_log_context`` call."""
    _current_log_context.reset(token)


# ---------------------------------------------------------------------------
# JSON log formatter
# ---------------------------------------------------------------------------


class MILJsonFormatter(logging.Formatter):
    """
    Logging formatter that serialises each ``LogRecord`` as a JSON object.

    The output includes all mandatory audit fields from the current
    ``LogContext``, the record's own message, and any extra fields passed to
    the logger call.
    """

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_log_context()

        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "service": ctx.service,
            "component": ctx.component,
            "request_id": ctx.request_id,
            "correlation_id": ctx.correlation_id,
            "application_id": ctx.application_id,
            "tenant_id": ctx.tenant_id,
            "user_id": ctx.user_id,
            "event_type": str(getattr(record, "event_type", "")),
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Merge caller-supplied extra fields, excluding reserved names.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_ATTRS:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Structured logger wrapper
# ---------------------------------------------------------------------------


class StructuredLogger:
    """
    A thin wrapper around ``logging.Logger`` that enforces structured output.

    Callers use ``bind(**context)`` to attach persistent key-value pairs to a
    logger instance.  Bound fields are merged into the ``extra`` dict on every
    log call, in addition to the request-scoped ``LogContext`` fields.

    Example::

        logger = get_logger(__name__)
        bound = logger.bind(application_id=str(app_id), component="finding")
        bound.info("Finding generated", event_type="finding.generated")
    """

    def __init__(self, logger: logging.Logger, **bound_context: object) -> None:
        self._logger = logger
        self._bound: dict[str, object] = dict(bound_context)

    def bind(self, **context: object) -> StructuredLogger:
        """Return a new ``StructuredLogger`` with additional bound context fields."""
        return StructuredLogger(self._logger, **{**self._bound, **context})

    def _extra(self, event_type: str, **kwargs: object) -> dict[str, object]:
        return {"event_type": event_type, **self._bound, **kwargs}

    def debug(self, message: str, event_type: str = "", **extra: object) -> None:
        self._logger.debug(message, extra=self._extra(event_type, **extra))

    def info(self, message: str, event_type: str = "", **extra: object) -> None:
        self._logger.info(message, extra=self._extra(event_type, **extra))

    def warning(self, message: str, event_type: str = "", **extra: object) -> None:
        self._logger.warning(message, extra=self._extra(event_type, **extra))

    def error(self, message: str, event_type: str = "", **extra: object) -> None:
        self._logger.error(message, extra=self._extra(event_type, **extra))

    def critical(self, message: str, event_type: str = "", **extra: object) -> None:
        self._logger.critical(message, extra=self._extra(event_type, **extra))

    def warning_with_traceback(self, message: str, event_type: str = "", **extra: object) -> None:
        """Log at WARNING with the current exception's traceback attached. See ``exception()``."""
        self._logger.warning(message, exc_info=True, extra=self._extra(event_type, **extra))

    def exception(self, message: str, event_type: str = "", **extra: object) -> None:
        """
        Log at ERROR with the current exception's traceback attached.

        Mirrors ``logging.Logger.exception`` (call only from an active
        ``except`` block). Distinct from ``error(...)`` — the other methods
        on this class forward arbitrary ``**extra`` straight into the JSON
        payload as custom fields, so a bare ``exc_info=True`` passed as an
        extra kwarg would only ever become a (useless) ``"exc_info": true``
        field rather than actually attaching the traceback ``logging``
        captures internally.
        """
        self._logger.error(message, exc_info=True, extra=self._extra(event_type, **extra))


def get_logger(name: str, **bound_context: object) -> StructuredLogger:
    """
    Return a ``StructuredLogger`` for the given module name.

    Pass keyword arguments to pre-bind context fields (e.g. ``component``,
    ``bounded_context``) that will appear in every log record emitted by this
    logger instance.

    Example::

        logger = get_logger(__name__, bounded_context="evidence")
    """
    return StructuredLogger(logging.getLogger(name), **bound_context)


def configure_logging(log_level: str = "INFO", service_name: str = "mil-api") -> None:
    """
    Configure the root logger to emit structured JSON and set the log context service.

    Call once at application startup (in ``lifespan`` or ``main``).  Tests may
    skip this and rely on the default ``LogContext`` populated with empty strings.
    """
    formatter = MILJsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    default_ctx = LogContext(service=service_name)
    _current_log_context.set(default_ctx)


# ---------------------------------------------------------------------------
# Trace context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TraceContext:
    """
    Propagated trace identifiers for a request.

    Populated by the telemetry middleware (T023) from the active OpenTelemetry
    span.  Available to service-layer code via ``get_trace_context()``.

    Attributes:
        trace_id: 32-character hex representation of the W3C trace ID.
        span_id:  16-character hex representation of the current span ID.
        request_id: Platform-generated request correlation ID (UUID).
    """

    trace_id: str = ""
    span_id: str = ""
    request_id: str = ""


_current_trace_context: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "current_trace_context",
    default=None,
)


def set_trace_context(ctx: TraceContext) -> contextvars.Token[TraceContext | None]:
    """Bind a ``TraceContext`` to the current execution context."""
    return _current_trace_context.set(ctx)


def get_trace_context() -> TraceContext:
    """Return the trace context for the current request, or a blank default."""
    ctx = _current_trace_context.get()
    return ctx if ctx is not None else TraceContext()


def trace_context_from_otel() -> TraceContext:
    """
    Build a ``TraceContext`` from the currently active OpenTelemetry span.

    Returns an empty ``TraceContext`` when no span is active (e.g. in tests).
    This function isolates the OpenTelemetry import so the rest of the module
    has no hard dependency on the OTel SDK at import time.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx is not None and ctx.is_valid:
            return TraceContext(
                trace_id=format(ctx.trace_id, "032x"),
                span_id=format(ctx.span_id, "016x"),
            )
    except ImportError:
        pass
    return TraceContext()


# ---------------------------------------------------------------------------
# Metric emitter
# ---------------------------------------------------------------------------


class MetricEmitter(ABC):
    """
    Abstract interface for emitting platform metrics.

    The platform uses this interface in service-layer code so that the concrete
    metrics backend (OpenTelemetry, StatsD, CloudWatch, etc.) remains a
    deployment configuration choice, not a compile-time dependency.

    A concrete implementation is registered in the DI container at startup.
    Service code resolves it via ``container.resolve(MetricEmitter)``.
    """

    @abstractmethod
    def increment(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric by ``value``."""

    @abstractmethod
    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram observation (e.g. latency in milliseconds)."""

    @abstractmethod
    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric to ``value``."""


@dataclass
class NoOpMetricEmitter(MetricEmitter):
    """
    No-operation ``MetricEmitter`` for development and test environments.

    Registered by default in ``build_container`` when no metrics backend is
    configured.  Accepts all calls and discards them silently.
    """

    _call_counts: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def increment(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        self._call_counts[name] = self._call_counts.get(name, 0) + 1

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        pass

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        pass

    def call_count(self, name: str) -> int:
        """Return how many times ``increment`` was called with ``name``. Useful in tests."""
        return self._call_counts.get(name, 0)
