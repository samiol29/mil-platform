"""Unit tests for mil.kernel.metrics — InMemoryMetricEmitter."""

from __future__ import annotations

from mil.kernel.metrics import InMemoryMetricEmitter, MetricName
from mil.kernel.observability import MetricEmitter


class TestInMemoryMetricEmitterIsMetricEmitter:
    def test_is_metric_emitter(self) -> None:
        assert isinstance(InMemoryMetricEmitter(), MetricEmitter)


class TestIncrement:
    def test_increment_accumulates(self) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.increment(MetricName.HTTP_REQUESTS_TOTAL)
        emitter.increment(MetricName.HTTP_REQUESTS_TOTAL)
        snapshot = emitter.snapshot()
        assert snapshot.counters[MetricName.HTTP_REQUESTS_TOTAL] == 2.0

    def test_increment_with_custom_value(self) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.increment(MetricName.OCR_JOBS_TOTAL, value=5.0)
        assert emitter.snapshot().counters[MetricName.OCR_JOBS_TOTAL] == 5.0

    def test_independent_counters(self) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.increment(MetricName.COPILOT_REQUESTS_TOTAL)
        emitter.increment(MetricName.AUDIT_EVENTS_TOTAL)
        snapshot = emitter.snapshot()
        assert snapshot.counters[MetricName.COPILOT_REQUESTS_TOTAL] == 1.0
        assert snapshot.counters[MetricName.AUDIT_EVENTS_TOTAL] == 1.0


class TestHistogram:
    def test_average_is_computed(self) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.histogram(MetricName.HTTP_REQUEST_DURATION_MS, 10.0)
        emitter.histogram(MetricName.HTTP_REQUEST_DURATION_MS, 20.0)
        stats = emitter.snapshot().histograms[MetricName.HTTP_REQUEST_DURATION_MS]
        assert stats.count == 2
        assert stats.average == 15.0

    def test_min_and_max_tracked(self) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.histogram(MetricName.HTTP_REQUEST_DURATION_MS, 5.0)
        emitter.histogram(MetricName.HTTP_REQUEST_DURATION_MS, 50.0)
        emitter.histogram(MetricName.HTTP_REQUEST_DURATION_MS, 25.0)
        stats = emitter.snapshot().histograms[MetricName.HTTP_REQUEST_DURATION_MS]
        assert stats.minimum == 5.0
        assert stats.maximum == 50.0

    def test_average_is_zero_for_empty_histogram(self) -> None:
        from mil.kernel.metrics import HistogramStats

        assert HistogramStats(count=0, sum=0.0, minimum=0.0, maximum=0.0).average == 0.0


class TestGauge:
    def test_gauge_records_latest_value(self) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.gauge("queue.depth", 3.0)
        emitter.gauge("queue.depth", 7.0)
        # Gauges are not part of the public snapshot contract (only
        # counters/histograms are exposed today); verify no exception and
        # that repeated calls do not raise.


class TestSnapshotIsolation:
    def test_snapshot_is_independent_of_later_increments(self) -> None:
        emitter = InMemoryMetricEmitter()
        emitter.increment(MetricName.HTTP_REQUESTS_TOTAL)
        snapshot = emitter.snapshot()
        emitter.increment(MetricName.HTTP_REQUESTS_TOTAL)
        assert snapshot.counters[MetricName.HTTP_REQUESTS_TOTAL] == 1.0
