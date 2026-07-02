"""Unit tests for mil.kernel.observability — logging, trace context, and metrics."""

from __future__ import annotations

import json
import logging
from dataclasses import FrozenInstanceError

import pytest

from mil.kernel.observability import (
    LogContext,
    MetricEmitter,
    MILJsonFormatter,
    NoOpMetricEmitter,
    StructuredLogger,
    TraceContext,
    get_log_context,
    get_logger,
    get_trace_context,
    set_log_context,
    set_trace_context,
)

# ---------------------------------------------------------------------------
# MILJsonFormatter
# ---------------------------------------------------------------------------


class TestMILJsonFormatter:
    def _make_record(
        self,
        message: str = "test message",
        level: int = logging.INFO,
        **extra: object,
    ) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_output_is_valid_json(self) -> None:
        formatter = MILJsonFormatter()
        record = self._make_record("hello")
        output = formatter.format(record)
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_mandatory_fields_present(self) -> None:
        formatter = MILJsonFormatter()
        record = self._make_record("event occurred")
        data = json.loads(formatter.format(record))
        mandatory = {
            "timestamp",
            "severity",
            "service",
            "request_id",
            "application_id",
            "user_id",
            "event_type",
            "message",
            "logger",
        }
        for field in mandatory:
            assert field in data, f"Mandatory field '{field}' missing from structured log"

    def test_severity_reflects_level(self) -> None:
        formatter = MILJsonFormatter()
        record = self._make_record("warn msg", level=logging.WARNING)
        data = json.loads(formatter.format(record))
        assert data["severity"] == "WARNING"

    def test_message_included(self) -> None:
        formatter = MILJsonFormatter()
        record = self._make_record("my custom message")
        data = json.loads(formatter.format(record))
        assert data["message"] == "my custom message"

    def test_context_fields_from_log_context(self) -> None:
        ctx = LogContext(
            service="mil-worker",
            request_id="req-abc",
            application_id="app-xyz",
            user_id="usr-001",
        )
        token = set_log_context(ctx)
        try:
            formatter = MILJsonFormatter()
            record = self._make_record("ctx test")
            data = json.loads(formatter.format(record))
            assert data["service"] == "mil-worker"
            assert data["request_id"] == "req-abc"
            assert data["application_id"] == "app-xyz"
            assert data["user_id"] == "usr-001"
        finally:
            from mil.kernel.observability import _current_log_context

            _current_log_context.reset(token)

    def test_context_includes_tenant_correlation_and_component(self) -> None:
        ctx = LogContext(
            tenant_id="tenant-001",
            correlation_id="corr-001",
            component="finding",
        )
        token = set_log_context(ctx)
        try:
            formatter = MILJsonFormatter()
            record = self._make_record("ctx test")
            data = json.loads(formatter.format(record))
            assert data["tenant_id"] == "tenant-001"
            assert data["correlation_id"] == "corr-001"
            assert data["component"] == "finding"
        finally:
            from mil.kernel.observability import _current_log_context

            _current_log_context.reset(token)

    def test_event_type_from_extra(self) -> None:
        formatter = MILJsonFormatter()
        record = self._make_record("event", event_type="finding.verified")
        data = json.loads(formatter.format(record))
        assert data["event_type"] == "finding.verified"

    def test_extra_fields_included(self) -> None:
        formatter = MILJsonFormatter()
        record = self._make_record("msg", finding_id="find-001")
        data = json.loads(formatter.format(record))
        assert data.get("finding_id") == "find-001"

    def test_timestamp_is_iso_format(self) -> None:
        formatter = MILJsonFormatter()
        record = self._make_record("ts test")
        data = json.loads(formatter.format(record))
        ts = data["timestamp"]
        # ISO 8601 UTC includes 'T' separator and '+00:00' or 'Z'
        assert "T" in ts


# ---------------------------------------------------------------------------
# LogContext and context variable
# ---------------------------------------------------------------------------


class TestLogContext:
    def test_default_log_context(self) -> None:
        ctx = LogContext()
        assert ctx.service == "mil-api"
        assert ctx.request_id == ""
        assert ctx.application_id == ""
        assert ctx.user_id == ""

    def test_set_and_get_log_context(self) -> None:
        ctx = LogContext(service="mil-test", request_id="req-001")
        token = set_log_context(ctx)
        try:
            retrieved = get_log_context()
            assert retrieved.service == "mil-test"
            assert retrieved.request_id == "req-001"
        finally:
            from mil.kernel.observability import _current_log_context

            _current_log_context.reset(token)


# ---------------------------------------------------------------------------
# StructuredLogger
# ---------------------------------------------------------------------------


class TestStructuredLogger:
    def _capture_records(self, logger_name: str) -> list[logging.LogRecord]:
        records: list[logging.LogRecord] = []

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = CapturingHandler()
        inner = logging.getLogger(logger_name)
        inner.addHandler(handler)
        inner.setLevel(logging.DEBUG)
        return records

    def test_get_logger_returns_structured_logger(self) -> None:
        logger = get_logger("mil.test.module")
        assert isinstance(logger, StructuredLogger)

    def test_bind_returns_new_instance(self) -> None:
        original = get_logger("test")
        bound = original.bind(component="evidence")
        assert bound is not original

    def test_bound_context_preserved(self) -> None:
        name = "mil.test.bind"
        records = self._capture_records(name)
        logger = get_logger(name)
        bound = logger.bind(component="finding")
        bound.info("bound test")
        assert len(records) == 1
        assert records[0].component == "finding"  # type: ignore[attr-defined]

    def test_log_levels_delegated(self) -> None:
        name = "mil.test.levels"
        records = self._capture_records(name)
        logger = get_logger(name)

        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warn msg")
        logger.error("error msg")
        logger.critical("critical msg")

        assert len(records) == 5
        assert records[0].levelno == logging.DEBUG
        assert records[4].levelno == logging.CRITICAL

    def test_event_type_passed_as_extra(self) -> None:
        name = "mil.test.event_type"
        records = self._capture_records(name)
        logger = get_logger(name)
        logger.info("test", event_type="evidence.extracted")
        assert records[0].event_type == "evidence.extracted"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TraceContext
# ---------------------------------------------------------------------------


class TestTraceContext:
    def test_default_trace_context(self) -> None:
        ctx = get_trace_context()
        assert ctx.trace_id == ""
        assert ctx.span_id == ""
        assert ctx.request_id == ""

    def test_set_and_get_trace_context(self) -> None:
        ctx = TraceContext(trace_id="abc123", span_id="def456", request_id="req-001")
        token = set_trace_context(ctx)
        try:
            retrieved = get_trace_context()
            assert retrieved.trace_id == "abc123"
            assert retrieved.span_id == "def456"
            assert retrieved.request_id == "req-001"
        finally:
            from mil.kernel.observability import _current_trace_context

            _current_trace_context.reset(token)

    def test_trace_context_is_immutable(self) -> None:
        ctx = TraceContext(trace_id="abc")
        with pytest.raises(FrozenInstanceError):
            ctx.trace_id = "xyz"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MetricEmitter interface
# ---------------------------------------------------------------------------


class TestMetricEmitterInterface:
    def test_metric_emitter_is_abstract(self) -> None:
        import inspect

        assert inspect.isabstract(MetricEmitter)

    def test_required_abstract_methods(self) -> None:
        assert "increment" in MetricEmitter.__abstractmethods__
        assert "histogram" in MetricEmitter.__abstractmethods__
        assert "gauge" in MetricEmitter.__abstractmethods__


# ---------------------------------------------------------------------------
# NoOpMetricEmitter
# ---------------------------------------------------------------------------


class TestNoOpMetricEmitter:
    def test_implements_metric_emitter(self) -> None:
        emitter = NoOpMetricEmitter()
        assert isinstance(emitter, MetricEmitter)

    def test_increment_does_not_raise(self) -> None:
        emitter = NoOpMetricEmitter()
        emitter.increment("findings.verified")
        emitter.increment("findings.verified", value=5.0, tags={"tenant": "acme"})

    def test_histogram_does_not_raise(self) -> None:
        emitter = NoOpMetricEmitter()
        emitter.histogram("api.latency_ms", 42.0)

    def test_gauge_does_not_raise(self) -> None:
        emitter = NoOpMetricEmitter()
        emitter.gauge("queue.depth", 17.0)

    def test_call_count_tracking(self) -> None:
        emitter = NoOpMetricEmitter()
        emitter.increment("my.counter")
        emitter.increment("my.counter")
        emitter.increment("other.counter")
        assert emitter.call_count("my.counter") == 2
        assert emitter.call_count("other.counter") == 1
        assert emitter.call_count("nonexistent") == 0

    def test_is_instantiable_without_arguments(self) -> None:
        emitter = NoOpMetricEmitter()
        assert emitter is not None
