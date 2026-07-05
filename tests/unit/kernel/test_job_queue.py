"""Unit tests for mil.kernel.job_queue — Job, JobQueue interface, and InProcessJobQueue."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mil.kernel.job_queue import InProcessJobQueue, Job, JobQueue

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_job(
    job_type: str = "ocr",
    idempotency_key: str | None = None,
    max_retries: int = 3,
    retry_count: int = 0,
) -> Job:
    import uuid

    key = idempotency_key if idempotency_key is not None else str(uuid.uuid4())
    return Job(
        job_type=job_type,
        idempotency_key=key,
        payload={"document_id": "doc-001"},
        max_retries=max_retries,
        retry_count=retry_count,
    )


# ---------------------------------------------------------------------------
# Job — construction and validation
# ---------------------------------------------------------------------------


class TestJobConstruction:
    def test_job_id_auto_generated(self) -> None:
        job = make_job()
        assert isinstance(job.job_id, str)
        assert len(job.job_id) == 36

    def test_created_at_is_utc_datetime(self) -> None:
        before = datetime.now(UTC)
        job = make_job()
        after = datetime.now(UTC)
        assert isinstance(job.created_at, datetime)
        assert before <= job.created_at <= after

    def test_empty_job_id_raises(self) -> None:
        with pytest.raises(ValueError, match="job_id"):
            Job(job_id="", job_type="ocr", idempotency_key="key-001")

    def test_empty_job_type_raises(self) -> None:
        with pytest.raises(ValueError, match="job_type"):
            Job(job_id="id-001", job_type="", idempotency_key="key-001")

    def test_empty_idempotency_key_raises(self) -> None:
        with pytest.raises(ValueError, match="idempotency_key"):
            Job(job_id="id-001", job_type="ocr", idempotency_key="")

    def test_negative_max_retries_raises(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            Job(job_id="id-001", job_type="ocr", idempotency_key="key", max_retries=-1)

    def test_negative_retry_count_raises(self) -> None:
        with pytest.raises(ValueError, match="retry_count"):
            Job(job_id="id-001", job_type="ocr", idempotency_key="key", retry_count=-1)

    def test_payload_defaults_to_empty_dict(self) -> None:
        job = Job(job_id="id-001", job_type="ocr", idempotency_key="key-001")
        assert job.payload == {}

    def test_max_retries_defaults_to_three(self) -> None:
        job = make_job()
        assert job.max_retries == 3

    def test_retry_count_defaults_to_zero(self) -> None:
        job = make_job()
        assert job.retry_count == 0


# ---------------------------------------------------------------------------
# Job — equality and hashing
# ---------------------------------------------------------------------------


class TestJobEquality:
    def test_same_job_id_is_equal(self) -> None:
        a = Job(job_id="same-id", job_type="ocr", idempotency_key="key-a")
        b = Job(job_id="same-id", job_type="extraction", idempotency_key="key-b")
        assert a == b

    def test_different_job_ids_not_equal(self) -> None:
        a = make_job()
        b = make_job()
        assert a != b

    def test_equal_jobs_same_hash(self) -> None:
        a = Job(job_id="shared-id", job_type="ocr", idempotency_key="key-a")
        b = Job(job_id="shared-id", job_type="ocr", idempotency_key="key-b")
        assert hash(a) == hash(b)

    def test_jobs_usable_in_set(self) -> None:
        a = Job(job_id="id-001", job_type="ocr", idempotency_key="key-a")
        b = Job(job_id="id-002", job_type="ocr", idempotency_key="key-b")
        s = {a, b}
        assert len(s) == 2

    def test_job_not_equal_to_non_job(self) -> None:
        job = make_job()
        assert job != "not-a-job"
        assert job != 42


# ---------------------------------------------------------------------------
# JobQueue interface contract
# ---------------------------------------------------------------------------


class TestJobQueueInterface:
    def test_in_process_is_job_queue(self) -> None:
        queue = InProcessJobQueue()
        assert isinstance(queue, JobQueue)

    def test_base_enqueue_raises(self) -> None:
        q = JobQueue()
        with pytest.raises(NotImplementedError):
            q.enqueue(make_job())

    def test_base_dequeue_raises(self) -> None:
        q = JobQueue()
        with pytest.raises(NotImplementedError):
            q.dequeue()

    def test_base_acknowledge_raises(self) -> None:
        q = JobQueue()
        with pytest.raises(NotImplementedError):
            q.acknowledge("job-id")

    def test_base_reject_raises(self) -> None:
        q = JobQueue()
        with pytest.raises(NotImplementedError):
            q.reject("job-id")

    def test_base_pending_count_raises(self) -> None:
        q = JobQueue()
        with pytest.raises(NotImplementedError):
            q.pending_count()

    def test_base_processing_count_raises(self) -> None:
        q = JobQueue()
        with pytest.raises(NotImplementedError):
            q.processing_count()


# ---------------------------------------------------------------------------
# InProcessJobQueue — enqueue and dequeue
# ---------------------------------------------------------------------------


class TestInProcessJobQueueEnqueueDequeue:
    def test_enqueue_increases_pending_count(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job())
        assert q.pending_count() == 1

    def test_dequeue_returns_enqueued_job(self) -> None:
        q = InProcessJobQueue()
        job = make_job()
        q.enqueue(job)
        result = q.dequeue()
        assert result is job

    def test_dequeue_empty_queue_returns_none(self) -> None:
        q = InProcessJobQueue()
        assert q.dequeue() is None

    def test_dequeue_is_fifo(self) -> None:
        q = InProcessJobQueue()
        j1 = make_job(idempotency_key="key-1")
        j2 = make_job(idempotency_key="key-2")
        j3 = make_job(idempotency_key="key-3")
        q.enqueue(j1)
        q.enqueue(j2)
        q.enqueue(j3)
        assert q.dequeue() is j1
        assert q.dequeue() is j2
        assert q.dequeue() is j3

    def test_dequeued_job_moves_to_processing(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job())
        assert q.pending_count() == 1
        q.dequeue()
        assert q.pending_count() == 0
        assert q.processing_count() == 1

    def test_pending_count_decreases_after_dequeue(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="k1"))
        q.enqueue(make_job(idempotency_key="k2"))
        q.dequeue()
        assert q.pending_count() == 1


# ---------------------------------------------------------------------------
# InProcessJobQueue — job_type routing
#
# Multiple distinct worker types (OCR, EXTRACTION, FINDING, POLICY, REVIEW)
# share one physical queue. Without type filtering, a worker could dequeue and
# mishandle a job meant for a different step — this reproduced immediately
# against a real Redis-backed queue with two concurrent worker processes.
# ---------------------------------------------------------------------------


class TestInProcessJobQueueJobTypeRouting:
    def test_dequeue_with_job_type_only_returns_matching_type(self) -> None:
        q = InProcessJobQueue()
        ocr_job = make_job(job_type="OCR", idempotency_key="k1")
        extraction_job = make_job(job_type="EXTRACTION", idempotency_key="k2")
        q.enqueue(ocr_job)
        q.enqueue(extraction_job)

        result = q.dequeue(job_type="EXTRACTION")
        assert result is extraction_job

    def test_dequeue_with_job_type_skips_non_matching_preserving_order(self) -> None:
        q = InProcessJobQueue()
        ocr_job = make_job(job_type="OCR", idempotency_key="k1")
        extraction_job_1 = make_job(job_type="EXTRACTION", idempotency_key="k2")
        extraction_job_2 = make_job(job_type="EXTRACTION", idempotency_key="k3")
        q.enqueue(ocr_job)
        q.enqueue(extraction_job_1)
        q.enqueue(extraction_job_2)

        assert q.dequeue(job_type="EXTRACTION") is extraction_job_1
        assert q.dequeue(job_type="EXTRACTION") is extraction_job_2
        # The non-matching job was never disturbed and is still dequeuable.
        assert q.dequeue(job_type="OCR") is ocr_job

    def test_dequeue_with_job_type_returns_none_when_no_match(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(job_type="OCR"))
        assert q.dequeue(job_type="EXTRACTION") is None

    def test_dequeue_without_job_type_matches_any(self) -> None:
        q = InProcessJobQueue()
        job = make_job(job_type="POLICY")
        q.enqueue(job)
        assert q.dequeue() is job


# ---------------------------------------------------------------------------
# InProcessJobQueue — idempotency
# ---------------------------------------------------------------------------


class TestInProcessJobQueueIdempotency:
    def test_duplicate_idempotency_key_rejected(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="dup-key"))
        q.enqueue(make_job(idempotency_key="dup-key"))
        assert q.pending_count() == 1

    def test_different_idempotency_keys_both_accepted(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="key-a"))
        q.enqueue(make_job(idempotency_key="key-b"))
        assert q.pending_count() == 2

    def test_key_released_after_acknowledge(self) -> None:
        q = InProcessJobQueue()
        job = make_job(idempotency_key="reuse-key")
        q.enqueue(job)
        dequeued = q.dequeue()
        assert dequeued is not None
        q.acknowledge(dequeued.job_id)

        # Same key should now be accepted again.
        q.enqueue(make_job(idempotency_key="reuse-key"))
        assert q.pending_count() == 1

    def test_key_not_released_during_processing(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="active-key"))
        q.dequeue()  # job is now in processing

        q.enqueue(make_job(idempotency_key="active-key"))
        assert q.pending_count() == 0  # duplicate rejected while in processing


# ---------------------------------------------------------------------------
# InProcessJobQueue — acknowledge
# ---------------------------------------------------------------------------


class TestInProcessJobQueueAcknowledge:
    def test_acknowledge_removes_from_processing(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job())
        job = q.dequeue()
        assert job is not None
        q.acknowledge(job.job_id)
        assert q.processing_count() == 0

    def test_acknowledge_unknown_id_is_noop(self) -> None:
        q = InProcessJobQueue()
        q.acknowledge("nonexistent-id")  # should not raise

    def test_acknowledge_releases_idempotency_key(self) -> None:
        q = InProcessJobQueue()
        job = make_job(idempotency_key="my-key")
        q.enqueue(job)
        dequeued = q.dequeue()
        assert dequeued is not None
        q.acknowledge(dequeued.job_id)

        # Key should be released; re-enqueue with same key allowed.
        q.enqueue(make_job(idempotency_key="my-key"))
        assert q.pending_count() == 1


# ---------------------------------------------------------------------------
# InProcessJobQueue — reject and retry
# ---------------------------------------------------------------------------


class TestInProcessJobQueueReject:
    def test_reject_with_requeue_re_enqueues_job(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(max_retries=3))
        job = q.dequeue()
        assert job is not None
        q.reject(job.job_id, requeue=True)
        assert q.pending_count() == 1

    def test_rejected_job_increments_retry_count(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(max_retries=3, retry_count=0))
        job = q.dequeue()
        assert job is not None
        q.reject(job.job_id, requeue=True)
        retry_job = q.dequeue()
        assert retry_job is not None
        assert retry_job.retry_count == 1

    def test_reject_without_requeue_discards_job(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job())
        job = q.dequeue()
        assert job is not None
        q.reject(job.job_id, requeue=False)
        assert q.pending_count() == 0
        assert q.processing_count() == 0

    def test_reject_exhausted_retries_discards_job(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(max_retries=2, retry_count=2))
        job = q.dequeue()
        assert job is not None
        q.reject(job.job_id, requeue=True)
        # No pending — retries exhausted
        assert q.pending_count() == 0

    def test_reject_releases_key_on_exhaustion(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="retry-key", max_retries=1, retry_count=1))
        job = q.dequeue()
        assert job is not None
        q.reject(job.job_id, requeue=True)
        # Key released; same key re-enqueueable
        q.enqueue(make_job(idempotency_key="retry-key"))
        assert q.pending_count() == 1

    def test_reject_unknown_id_is_noop(self) -> None:
        q = InProcessJobQueue()
        q.reject("nonexistent-id")  # should not raise

    def test_retried_job_placed_at_head_of_queue(self) -> None:
        q = InProcessJobQueue()
        j1 = make_job(idempotency_key="j1", max_retries=3)
        j2 = make_job(idempotency_key="j2")
        q.enqueue(j1)
        q.enqueue(j2)
        first = q.dequeue()
        assert first is j1
        q.reject(j1.job_id, requeue=True)

        # j1 should be next (placed at head), not j2.
        next_job = q.dequeue()
        assert next_job is not None
        assert next_job.idempotency_key == j1.idempotency_key

    def test_reject_default_requeues(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(max_retries=3))
        job = q.dequeue()
        assert job is not None
        q.reject(job.job_id)  # default requeue=True
        assert q.pending_count() == 1


# ---------------------------------------------------------------------------
# InProcessJobQueue — counts
# ---------------------------------------------------------------------------


class TestInProcessJobQueueCounts:
    def test_initial_counts_are_zero(self) -> None:
        q = InProcessJobQueue()
        assert q.pending_count() == 0
        assert q.processing_count() == 0

    def test_enqueue_increments_pending(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="k1"))
        q.enqueue(make_job(idempotency_key="k2"))
        assert q.pending_count() == 2

    def test_dequeue_moves_pending_to_processing(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="k1"))
        q.enqueue(make_job(idempotency_key="k2"))
        q.dequeue()
        assert q.pending_count() == 1
        assert q.processing_count() == 1


# ---------------------------------------------------------------------------
# InProcessJobQueue — clear
# ---------------------------------------------------------------------------


class TestInProcessJobQueueClear:
    def test_clear_resets_all_state(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="k1"))
        q.dequeue()
        q.enqueue(make_job(idempotency_key="k2"))
        q.clear()
        assert q.pending_count() == 0
        assert q.processing_count() == 0

    def test_after_clear_idempotency_keys_released(self) -> None:
        q = InProcessJobQueue()
        q.enqueue(make_job(idempotency_key="reuse"))
        q.clear()
        q.enqueue(make_job(idempotency_key="reuse"))
        assert q.pending_count() == 1
