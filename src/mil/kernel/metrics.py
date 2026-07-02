"""
Platform metrics — US2 Sprint 8 (Production Hardening).

Provides a concrete, in-process ``MetricEmitter`` implementation
(``InMemoryMetricEmitter``) and the named metric constants the platform uses
for basic operational visibility: requests served, Copilot requests, OCR
jobs, workflow executions, provider failures, and audit events, plus average
HTTP response time.

This module deliberately does **not** implement distributed tracing. It is a
simple, in-process counter/histogram store suitable for a single-process
deployment or as the default backend behind a ``/v1/metrics`` endpoint.
Production deployments that need cross-process aggregation register a
different ``MetricEmitter`` implementation (e.g. StatsD, CloudWatch, an
OpenTelemetry metrics exporter) in ``build_container`` — this module's
constants and ``MetricEmitter`` contract stay the same either way.

Dependency rule: imports only from ``mil.kernel.observability`` and the
Python standard library.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from mil.kernel.observability import MetricEmitter

# ---------------------------------------------------------------------------
# Named metric constants
#
# Bounded contexts and the HTTP middleware call ``increment``/``histogram``
# with these names so that the metrics exposed at ``/v1/metrics`` have a
# single, stable vocabulary.
# ---------------------------------------------------------------------------


class MetricName:
    """Stable metric name constants — the platform's basic metrics vocabulary."""

    HTTP_REQUESTS_TOTAL = "http.requests.total"
    HTTP_REQUEST_DURATION_MS = "http.request.duration_ms"
    COPILOT_REQUESTS_TOTAL = "copilot.requests.total"
    OCR_JOBS_TOTAL = "ocr.jobs.total"
    WORKFLOW_EXECUTIONS_TOTAL = "workflow.executions.total"
    PROVIDER_FAILURES_TOTAL = "provider.failures.total"
    AUDIT_EVENTS_TOTAL = "audit.events.total"


@dataclass(frozen=True)
class HistogramStats:
    """Aggregate statistics for one histogram metric."""

    count: int
    sum: float
    minimum: float
    maximum: float

    @property
    def average(self) -> float:
        """Return the mean observation, or 0.0 if no observations were recorded."""
        return self.sum / self.count if self.count else 0.0


@dataclass(frozen=True)
class MetricsSnapshot:
    """A point-in-time read of every counter and histogram."""

    counters: dict[str, float]
    histograms: dict[str, HistogramStats]


class InMemoryMetricEmitter(MetricEmitter):
    """
    Thread-safe, in-process ``MetricEmitter``.

    Counters accumulate for the lifetime of the process. Histograms track
    count/sum/min/max only (not raw samples) so memory use stays bounded
    regardless of request volume — sufficient for "average response time"
    and similar basic aggregates without the overhead of a full metrics
    backend. Tags are accepted (for interface compatibility) but not broken
    out per-tag in this basic implementation.

    Registered by default in ``build_container``. Production deployments
    that need cross-process aggregation or per-tag breakdowns register a
    different ``MetricEmitter`` implementation instead — callers only ever
    depend on the abstract ``MetricEmitter`` interface.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._histogram_count: dict[str, int] = {}
        self._histogram_sum: dict[str, float] = {}
        self._histogram_min: dict[str, float] = {}
        self._histogram_max: dict[str, float] = {}
        self._gauges: dict[str, float] = {}

    def increment(
        self,
        name: str,
        value: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + value

    def histogram(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            self._histogram_count[name] = self._histogram_count.get(name, 0) + 1
            self._histogram_sum[name] = self._histogram_sum.get(name, 0.0) + value
            self._histogram_min[name] = min(self._histogram_min.get(name, value), value)
            self._histogram_max[name] = max(self._histogram_max.get(name, value), value)

    def gauge(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            self._gauges[name] = value

    def snapshot(self) -> MetricsSnapshot:
        """Return a consistent, point-in-time read of all recorded metrics."""
        with self._lock:
            histograms = {
                name: HistogramStats(
                    count=self._histogram_count[name],
                    sum=self._histogram_sum[name],
                    minimum=self._histogram_min[name],
                    maximum=self._histogram_max[name],
                )
                for name in self._histogram_count
            }
            counters = dict(self._counters)
        return MetricsSnapshot(counters=counters, histograms=histograms)
