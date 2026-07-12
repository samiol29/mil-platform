"""
Integration tests for ``RedisJobQueue`` against a real Redis instance.

This is the test that actually proves the fix: two independent ``redis.Redis``
client connections (mirroring two separate OS processes — an API process and
a worker process) must observe the same enqueued job through the shared Redis
container, unlike ``InProcessJobQueue`` where two processes never share state.

Uses an ephemeral ``testcontainers`` Redis container (isolated per test
session) rather than the docker-compose Redis instance, so this test never
touches shared development state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mil.kernel.job_queue import Job, RedisJobQueue

if TYPE_CHECKING:
    from collections.abc import Iterator

    import redis


@pytest.fixture(scope="module")
def redis_container() -> Iterator[object]:
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture
def redis_client(redis_container: object) -> Iterator[redis.Redis]:
    client = redis_container.get_client()  # type: ignore[attr-defined]
    yield client
    client.flushdb()
    client.close()


def _job(
    idempotency_key: str,
    *,
    job_type: str = "workflow_step",
    payload: dict[str, object] | None = None,
) -> Job:
    return Job(job_type=job_type, idempotency_key=idempotency_key, payload=payload or {})


class TestCrossConnectionVisibility:
    """
    The core correctness property: a job enqueued through one client
    connection is dequeued through a second, independent client connection —
    proving the queue's state lives in Redis, not in either client's process.
    """

    def test_job_enqueued_on_one_connection_is_dequeued_on_another(
        self, redis_client: redis.Redis, redis_container: object
    ) -> None:
        import redis as redis_lib

        producer = RedisJobQueue(redis_client, key_prefix="test:cross-conn")
        # A second, independent connection — standing in for a separate OS
        # process (e.g. the API process vs. a worker process).
        host = redis_container.get_container_host_ip()  # type: ignore[attr-defined]
        port = redis_container.get_exposed_port(6379)  # type: ignore[attr-defined]
        second_connection = redis_lib.Redis(host=host, port=int(port), decode_responses=True)
        consumer = RedisJobQueue(second_connection, key_prefix="test:cross-conn")

        producer.enqueue(_job("doc-ingestion:doc-1", payload={"document_id": "doc-1"}))

        job = consumer.dequeue()
        assert job is not None
        assert job.payload["document_id"] == "doc-1"

        second_connection.close()


class TestEnqueueDequeueCycle:
    def test_dequeue_empty_queue_returns_none(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:empty")
        assert queue.dequeue() is None

    def test_fifo_ordering(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:fifo")
        queue.enqueue(_job("k1", payload={"n": 1}))
        queue.enqueue(_job("k2", payload={"n": 2}))
        queue.enqueue(_job("k3", payload={"n": 3}))

        assert queue.dequeue().payload["n"] == 1  # type: ignore[union-attr]
        assert queue.dequeue().payload["n"] == 2  # type: ignore[union-attr]
        assert queue.dequeue().payload["n"] == 3  # type: ignore[union-attr]

    def test_blocking_dequeue_returns_job_pushed_after_call(
        self, redis_client: redis.Redis
    ) -> None:
        """
        A real worker always dequeues with its own explicit ``job_type`` (see
        ``TestJobTypeRouting`` below), so ``BLPOP`` has a concrete, known key
        to watch even before anything has ever been enqueued under it. This
        test therefore passes ``job_type`` explicitly too — ``job_type=None``
        cannot block-wait for a type that has never been enqueued before,
        since there is no key name to discover until the enqueue happens
        (a real worker never hits this: it never dequeues an unknown type).
        """
        import threading
        import time

        queue = RedisJobQueue(redis_client, key_prefix="test:blocking")
        producer = RedisJobQueue(redis_client, key_prefix="test:blocking")

        def _delayed_enqueue() -> None:
            time.sleep(0.3)
            producer.enqueue(_job("delayed-job", job_type="OCR"))

        threading.Thread(target=_delayed_enqueue).start()
        job = queue.dequeue(timeout=2.0, job_type="OCR")
        assert job is not None
        assert job.idempotency_key == "delayed-job"

    def test_pending_and_processing_counts(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:counts")
        queue.enqueue(_job("k1"))
        queue.enqueue(_job("k2"))
        assert queue.pending_count() == 2
        assert queue.processing_count() == 0

        queue.dequeue()
        assert queue.pending_count() == 1
        assert queue.processing_count() == 1


class TestJobTypeRouting:
    """
    Multiple distinct worker types (OCR, EXTRACTION, FINDING, POLICY, REVIEW)
    share one physical Redis instance. Without type-partitioned pending lists,
    a worker for one step could dequeue and mishandle a job meant for another
    — this is exactly what reproduced the first time two real worker
    processes (document_pipeline and extraction_pipeline) polled an earlier,
    unpartitioned version of this queue against the same Redis instance.
    """

    def test_dequeue_with_job_type_only_returns_matching_type(
        self, redis_client: redis.Redis
    ) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:routing")
        queue.enqueue(_job("ocr-job", job_type="OCR"))
        queue.enqueue(_job("extraction-job", job_type="EXTRACTION"))

        job = queue.dequeue(job_type="EXTRACTION")
        assert job is not None
        assert job.idempotency_key == "extraction-job"

    def test_dequeue_with_job_type_returns_none_when_no_match(
        self, redis_client: redis.Redis
    ) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:routing-empty")
        queue.enqueue(_job("ocr-job", job_type="OCR"))
        assert queue.dequeue(job_type="EXTRACTION") is None

    def test_blocking_dequeue_with_job_type_ignores_other_types(
        self, redis_client: redis.Redis
    ) -> None:
        """
        The exact scenario that reproduced against real workers: an OCR job
        is enqueued while an EXTRACTION-only consumer is blocked waiting —
        it must NOT receive the OCR job.
        """
        queue = RedisJobQueue(redis_client, key_prefix="test:routing-blocking")
        queue.enqueue(_job("ocr-job", job_type="OCR"))

        # A short blocking wait scoped to EXTRACTION must time out with the
        # OCR job left untouched, still available to an OCR-scoped dequeue.
        assert queue.dequeue(timeout=0.5, job_type="EXTRACTION") is None
        assert queue.dequeue(job_type="OCR") is not None

    def test_dequeue_without_job_type_matches_any_known_type(
        self, redis_client: redis.Redis
    ) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:routing-any")
        queue.enqueue(_job("policy-job", job_type="POLICY"))
        job = queue.dequeue()
        assert job is not None
        assert job.idempotency_key == "policy-job"


class TestIdempotency:
    def test_duplicate_idempotency_key_is_dropped(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:idem")
        queue.enqueue(_job("same-key", payload={"attempt": 1}))
        queue.enqueue(_job("same-key", payload={"attempt": 2}))
        assert queue.pending_count() == 1
        job = queue.dequeue()
        assert job is not None
        assert job.payload["attempt"] == 1

    def test_idempotency_key_released_on_acknowledge(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:idem-ack")
        queue.enqueue(_job("reusable-key"))
        job = queue.dequeue()
        assert job is not None
        queue.acknowledge(job.job_id)

        # Key released — a fresh enqueue with the same key is accepted, not dropped.
        queue.enqueue(_job("reusable-key"))
        assert queue.pending_count() == 1


class TestAcknowledgeAndReject:
    def test_acknowledge_removes_from_processing(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:ack")
        queue.enqueue(_job("k1"))
        job = queue.dequeue()
        assert job is not None
        queue.acknowledge(job.job_id)
        assert queue.processing_count() == 0

    def test_reject_with_retries_remaining_requeues_at_head(
        self, redis_client: redis.Redis
    ) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reject-retry")
        queue.enqueue(_job("failing-job"))
        queue.enqueue(_job("other-job"))
        job = queue.dequeue()  # claims "failing-job"
        assert job is not None
        queue.reject(job.job_id, requeue=True)

        # The retried job is dequeued next (priority), ahead of "other-job".
        retried = queue.dequeue()
        assert retried is not None
        assert retried.idempotency_key == "failing-job"
        assert retried.retry_count == 1

    def test_reject_without_requeue_drops_and_releases_key(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reject-drop")
        queue.enqueue(_job("dropped-job"))
        job = queue.dequeue()
        assert job is not None
        queue.reject(job.job_id, requeue=False)

        assert queue.pending_count() == 0
        assert queue.processing_count() == 0
        # Key released — re-enqueuing the same logical job succeeds.
        queue.enqueue(_job("dropped-job"))
        assert queue.pending_count() == 1

    def test_reject_at_max_retries_does_not_requeue(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reject-exhausted")
        exhausted_job = Job(
            job_type="workflow_step",
            idempotency_key="exhausted",
            max_retries=1,
            retry_count=1,
        )
        queue.enqueue(exhausted_job)
        job = queue.dequeue()
        assert job is not None
        queue.reject(job.job_id, requeue=True)
        assert queue.pending_count() == 0

    def test_reject_at_max_retries_moves_to_dead_letter(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reject-dead-letter")
        exhausted_job = Job(
            job_type="workflow_step", idempotency_key="exhausted-dl", max_retries=1, retry_count=1
        )
        queue.enqueue(exhausted_job)
        job = queue.dequeue()
        assert job is not None
        queue.reject(job.job_id, requeue=True)
        assert queue.dead_letter_count() == 1


class TestReclaimStale:
    def test_stale_claimed_job_with_retries_is_redelivered(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reclaim-retry")
        queue.enqueue(_job("stuck-job"))
        job = queue.dequeue()  # simulates a worker claiming it, then crashing
        assert job is not None
        assert queue.processing_count() == 1

        reclaimed = queue.reclaim_stale(visibility_timeout_seconds=0.0)

        assert reclaimed == 1
        assert queue.processing_count() == 0
        redelivered = queue.dequeue()
        assert redelivered is not None
        assert redelivered.idempotency_key == "stuck-job"
        assert redelivered.retry_count == 1

    def test_stale_claimed_job_at_max_retries_goes_to_dead_letter(
        self, redis_client: redis.Redis
    ) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reclaim-dead-letter")
        exhausted_job = Job(
            job_type="workflow_step",
            idempotency_key="stuck-exhausted",
            max_retries=0,
            retry_count=0,
        )
        queue.enqueue(exhausted_job)
        job = queue.dequeue()
        assert job is not None

        reclaimed = queue.reclaim_stale(visibility_timeout_seconds=0.0)

        assert reclaimed == 1
        assert queue.processing_count() == 0
        assert queue.dead_letter_count() == 1

    def test_recently_claimed_job_is_not_reclaimed(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reclaim-recent")
        queue.enqueue(_job("fresh-job"))
        queue.dequeue()

        reclaimed = queue.reclaim_stale(visibility_timeout_seconds=3600.0)

        assert reclaimed == 0
        assert queue.processing_count() == 1

    def test_reclaim_with_no_processing_jobs_is_a_noop(self, redis_client: redis.Redis) -> None:
        queue = RedisJobQueue(redis_client, key_prefix="test:reclaim-empty")
        assert queue.reclaim_stale(visibility_timeout_seconds=0.0) == 0
