"""Unit tests for workers.bootstrap — worker startup and per-job execution."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mil.kernel.context import get_request_context
from mil.kernel.job_queue import InProcessJobQueue, Job, JobQueue
from mil.kernel.observability import get_log_context
from workers.bootstrap import (
    WorkerCircuitOpenError,
    WorkerContext,
    build_worker_context,
    process_next,
    run_forever,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(
    correlation_id: str = "corr-1",
    *,
    application_id: str = "",
    tenant_id: str = "",
) -> Job:
    payload = {"correlation_id": correlation_id, "step_name": "OCR"}
    if application_id:
        payload["application_id"] = application_id
    if tenant_id:
        payload["tenant_id"] = tenant_id
    return Job(
        job_type="workflow_step",
        idempotency_key=f"run:{correlation_id}:OCR",
        payload=payload,
    )


def _make_context(queue: JobQueue | None = None) -> tuple[WorkerContext, MagicMock]:
    session = MagicMock()
    session_factory = MagicMock(return_value=session)
    ctx = WorkerContext(
        container=MagicMock(),
        session_factory=session_factory,
        job_queue=queue if queue is not None else InProcessJobQueue(),
    )
    return ctx, session


# ---------------------------------------------------------------------------
# build_worker_context
# ---------------------------------------------------------------------------


class TestBuildWorkerContext:
    def test_resolves_job_queue_from_container(self) -> None:
        queue = InProcessJobQueue()
        container = MagicMock()
        container.resolve.return_value = queue
        ctx = build_worker_context(
            settings=MagicMock(mil_log_level="INFO"),
            container=container,
            session_factory=MagicMock(),
        )
        assert ctx.job_queue is queue
        container.resolve.assert_called_once_with(JobQueue)

    def test_uses_injected_session_factory(self) -> None:
        factory = MagicMock()
        container = MagicMock()
        container.resolve.return_value = InProcessJobQueue()
        ctx = build_worker_context(
            settings=MagicMock(mil_log_level="INFO"),
            container=container,
            session_factory=factory,
        )
        assert ctx.session_factory is factory

    def test_uses_injected_container(self) -> None:
        container = MagicMock()
        container.resolve.return_value = InProcessJobQueue()
        ctx = build_worker_context(
            settings=MagicMock(mil_log_level="INFO"),
            container=container,
            session_factory=MagicMock(),
        )
        assert ctx.container is container


# ---------------------------------------------------------------------------
# process_next — empty queue
# ---------------------------------------------------------------------------


class TestProcessNextEmpty:
    def test_returns_false_when_queue_empty(self) -> None:
        ctx, _ = _make_context()
        handler = MagicMock()
        assert process_next(ctx, handler) is False

    def test_handler_not_called_when_queue_empty(self) -> None:
        ctx, _ = _make_context()
        handler = MagicMock()
        process_next(ctx, handler)
        handler.assert_not_called()


# ---------------------------------------------------------------------------
# process_next — success path (Unit of Work)
# ---------------------------------------------------------------------------


class TestProcessNextSuccess:
    def test_returns_true(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, _ = _make_context(queue)
        assert process_next(ctx, MagicMock()) is True

    def test_handler_invoked_with_session_and_job(self) -> None:
        queue = InProcessJobQueue()
        job = _make_job()
        queue.enqueue(job)
        ctx, session = _make_context(queue)
        handler = MagicMock()
        process_next(ctx, handler)
        handler.assert_called_once()
        called_session, called_job = handler.call_args.args
        assert called_session is session
        assert called_job.job_id == job.job_id

    def test_commits_on_success(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, session = _make_context(queue)
        process_next(ctx, MagicMock())
        session.commit.assert_called_once()

    def test_acknowledges_job_on_success(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, _ = _make_context(queue)
        process_next(ctx, MagicMock())
        assert queue.pending_count() == 0
        assert queue.processing_count() == 0

    def test_closes_session(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, session = _make_context(queue)
        process_next(ctx, MagicMock())
        session.close.assert_called_once()

    def test_correlation_id_bound_during_handler(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job(correlation_id="corr-bound"))
        ctx, _ = _make_context(queue)
        seen: list[str] = []

        def handler(session: object, job: object) -> None:
            seen.append(get_request_context().correlation_id)

        process_next(ctx, handler)
        assert seen == ["corr-bound"]

    def test_log_context_bound_during_handler(self) -> None:
        """
        Final product polish sprint (B1): before this, workers only bound
        ``RequestContext`` (which nothing in the JSON log formatter reads) —
        ``LogContext`` was never bound, so a worker's log lines carried no
        correlation_id/application_id/tenant_id at all. This confirms the fix.
        """
        queue = InProcessJobQueue()
        queue.enqueue(
            _make_job(
                correlation_id="corr-log",
                application_id="app-1",
                tenant_id="tenant-1",
            )
        )
        ctx, _ = _make_context(queue)
        seen: list[tuple[str, str, str]] = []

        def handler(session: object, job: object) -> None:
            log_ctx = get_log_context()
            seen.append((log_ctx.correlation_id, log_ctx.application_id, log_ctx.tenant_id))

        process_next(ctx, handler)
        assert seen == [("corr-log", "app-1", "tenant-1")]

    def test_log_context_reset_after_handler(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job(correlation_id="corr-reset"))
        ctx, _ = _make_context(queue)
        process_next(ctx, MagicMock())
        assert get_log_context().correlation_id != "corr-reset"

    def test_logs_job_dequeued_and_completed(self, caplog: pytest.LogCaptureFixture) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, _ = _make_context(queue)
        with caplog.at_level("INFO", logger="workers.bootstrap"):
            process_next(ctx, MagicMock())
        messages = [record.message for record in caplog.records]
        assert "Job dequeued" in messages
        assert "Job completed" in messages


# ---------------------------------------------------------------------------
# process_next — failure path
# ---------------------------------------------------------------------------


class TestProcessNextFailure:
    def test_rolls_back_on_handler_error(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, session = _make_context(queue)

        def handler(session: object, job: object) -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            process_next(ctx, handler)
        session.rollback.assert_called_once()

    def test_does_not_commit_on_error(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, session = _make_context(queue)

        def handler(session: object, job: object) -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            process_next(ctx, handler)
        session.commit.assert_not_called()

    def test_requeues_job_on_error(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, _ = _make_context(queue)

        def handler(session: object, job: object) -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            process_next(ctx, handler)
        # Rejected with requeue (retry_count < max_retries) → back to pending.
        assert queue.pending_count() == 1

    def test_closes_session_on_error(self) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, session = _make_context(queue)

        def handler(session: object, job: object) -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            process_next(ctx, handler)
        session.close.assert_called_once()

    def test_logs_job_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, _ = _make_context(queue)

        def handler(session: object, job: object) -> None:
            raise RuntimeError("boom")

        with (
            caplog.at_level("WARNING", logger="workers.bootstrap"),
            pytest.raises(RuntimeError),
        ):
            process_next(ctx, handler)
        messages = [record.message for record in caplog.records]
        assert "Job failed; rolled back and requeued for retry" in messages


# ---------------------------------------------------------------------------
# run_forever
# ---------------------------------------------------------------------------


class _StopTest(BaseException):
    """
    Escapes ``run_forever``'s polling loop in tests. A ``BaseException``, not
    an ``Exception``, so it is deliberately *not* caught by ``run_forever``'s
    own ``except Exception`` — the same reason a real ``KeyboardInterrupt``/
    ``SystemExit`` would also correctly stop the worker rather than being
    logged-and-continued.
    """


class TestRunForever:
    def test_survives_a_handler_exception_and_keeps_polling(self) -> None:
        """
        The exact bug this fixes: previously, an unhandled exception (a bad
        payload, a missing dependency, ``ConflictError``, anything other than
        the narrow retry path) would propagate out of the bare
        ``while True: process_next(...)`` loop every worker's ``main()`` used
        to run, killing the entire process over a single job — silently
        halting every other application's processing too.
        """
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, _ = _make_context(queue)
        calls: list[int] = []

        def handler(session: object, job: object) -> None:
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("boom")
            raise _StopTest

        with pytest.raises(_StopTest):
            run_forever(
                ctx, handler, job_type="workflow_step", poll_timeout=0.0, sleep=lambda _s: None
            )

        # Handler ran 3 times: the same job, redelivered twice after
        # rollback/reject(requeue=True), never taking the process down.
        assert len(calls) == 3

    def test_logs_the_unhandled_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        queue = InProcessJobQueue()
        queue.enqueue(_make_job())
        ctx, _ = _make_context(queue)
        calls: list[int] = []

        def handler(session: object, job: object) -> None:
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("boom")
            raise _StopTest

        with caplog.at_level("ERROR"), pytest.raises(_StopTest):
            run_forever(
                ctx, handler, job_type="workflow_step", poll_timeout=0.0, sleep=lambda _s: None
            )

        assert any("Unhandled exception" in record.message for record in caplog.records)

    def test_empty_queue_does_not_raise_or_spin_forever_uncontrolled(self) -> None:
        """An empty queue is not an error — `process_next` returns `False`, not an exception."""
        ctx, _ = _make_context()
        calls = {"n": 0}

        def fake_process_next(*args: object, **kwargs: object) -> bool:
            calls["n"] += 1
            if calls["n"] >= 3:
                raise _StopTest
            return False

        import workers.bootstrap as bootstrap_module

        original = bootstrap_module.process_next
        bootstrap_module.process_next = fake_process_next  # type: ignore[assignment]
        try:
            with pytest.raises(_StopTest):
                run_forever(ctx, MagicMock(), job_type="workflow_step", poll_timeout=0.0)
        finally:
            bootstrap_module.process_next = original
        assert calls["n"] == 3

    def test_persistent_failure_backs_off_and_then_gives_up(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        The runaway-log regression: when ``dequeue`` raises instantly (broker
        down) the loop must sleep with growing delays, log only one traceback,
        and stop after ``max_consecutive_failures`` instead of spinning forever.
        """
        ctx, _ = _make_context()
        ctx.job_queue = MagicMock()
        ctx.job_queue.dequeue.side_effect = ConnectionError("redis down")
        delays: list[float] = []

        with caplog.at_level("ERROR"), pytest.raises(WorkerCircuitOpenError):
            run_forever(
                ctx,
                MagicMock(),
                job_type="workflow_step",
                poll_timeout=0.0,
                sleep=delays.append,
                max_consecutive_failures=8,
            )

        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
        assert ctx.job_queue.dequeue.call_count == 8
        assert sum(1 for r in caplog.records if r.exc_info) == 1

    def test_successful_poll_resets_the_failure_streak(self) -> None:
        ctx, _ = _make_context()
        outcomes = iter([ConnectionError("x"), ConnectionError("x"), None, ConnectionError("x")])
        delays: list[float] = []

        def dequeue(**_: object) -> None:
            outcome = next(outcomes, _StopTest())
            if isinstance(outcome, BaseException):
                raise outcome

        ctx.job_queue = MagicMock()
        ctx.job_queue.dequeue.side_effect = dequeue

        with pytest.raises(_StopTest):
            run_forever(
                ctx, MagicMock(), job_type="workflow_step", poll_timeout=0.0, sleep=delays.append
            )

        assert delays == [1.0, 2.0, 1.0]
