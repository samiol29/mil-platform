"""
Worker process startup infrastructure.

This module provides the scaffolding a background worker needs to run:

- build the dependency-injection container,
- create a database session factory,
- resolve shared dependencies (the ``JobQueue``),
- execute a job within a per-job Unit of Work.

It deliberately contains **no worker business logic**. The actual work of a
step (OCR, extraction, evidence, findings) is supplied by an injected
``JobHandler`` in a later sprint. ``process_next`` is the execution harness that
runs that handler safely; it is infrastructure, not domain logic.

Per-job Unit of Work (ADR-008): each job runs in a single database transaction.
On success the transaction commits and the job is acknowledged; on failure it
rolls back and the job is rejected (requeued within its retry budget). Because a
crash between side-effect and acknowledgement causes redelivery, handlers must
be idempotent — which the deterministic keys and unique constraints of ADR-008
guarantee.

Correlation propagation (ADR-009): the job's ``correlation_id`` is bound to the
request context before the handler runs, so the worker's logs, audit writes, and
any emitted events all carry the same end-to-end trace id. No pipeline object
loses the correlation id.

Dependency rule: imports only from ``mil.kernel``, the persistence layer, and
the Python standard library. No bounded context business logic is imported.
``_register_all_models`` (re-exported here from
``mil.kernel.model_registration.register_all_models``, the shared
implementation) is the one sanctioned exception: it imports every bounded
context's ``models.py`` purely for the ORM side effect of registering its
tables with ``Base.metadata`` (never touching business logic), mirroring the
identical, pre-existing pattern in ``migrations/env.py``. Without it, a
process only has the tables its own direct imports happen to touch
registered, and a flush touching a foreign key into an unregistered table
raises ``sqlalchemy.exc.NoReferencedTableError`` — a real crash, reproduced
live in both a standalone worker process (``Document``'s FK to
``core.parties``) and, contrary to this module's own former assumption, the
API process too (approving/overriding a Finding flushes a ``ReviewSession``
whose FK targets ``orchestrator.workflow_runs``, a table nothing under
``main.py``'s router imports happened to register). ``main.create_app`` now
calls the same shared ``register_all_models()`` for exactly this reason —
neither process may rely on the accident of which models its own imports
happen to touch.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mil.kernel.config import get_settings
from mil.kernel.container import build_container
from mil.kernel.context import RequestContext, reset_request_context, set_request_context
from mil.kernel.job_queue import JobQueue
from mil.kernel.model_registration import register_all_models as _register_all_models
from mil.kernel.observability import (
    configure_logging,
    get_log_context,
    get_logger,
    reset_log_context,
    set_log_context,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mil.kernel.config import Settings
    from mil.kernel.container import Container
    from mil.kernel.job_queue import Job

_log = get_logger(__name__)


class JobHandler(Protocol):
    """
    Callable that executes one job within an open database session.

    The handler is the worker's business logic — supplied by the bounded
    context that owns the step (US2 Sprint 2+). The bootstrap never implements
    one; it only invokes the injected handler inside a Unit of Work.
    """

    def __call__(self, session: Session, job: Job) -> None:
        """Execute the job. Must not commit — the harness owns the transaction."""
        ...


@dataclass
class WorkerContext:
    """
    Resolved runtime dependencies for a worker process.

    Attributes:
        container:        The application DI container.
        session_factory:  Factory producing a fresh ``Session`` per job.
        job_queue:        The platform job queue (resolved from the container).
    """

    container: Container
    session_factory: sessionmaker[Session]
    job_queue: JobQueue


def build_worker_context(
    *,
    settings: Settings | None = None,
    container: Container | None = None,
    session_factory: sessionmaker[Session] | None = None,
    service_name: str = "mil-worker",
) -> WorkerContext:
    """
    Assemble a ``WorkerContext`` for a worker process.

    Mirrors the API process bootstrap in ``main.py``: configure structured
    logging, build the container from settings, create a synchronous session
    factory, and resolve the job queue.

    All collaborators are injectable so tests can supply fakes without touching
    real infrastructure. When not supplied:

    - ``settings`` defaults to ``get_settings()``,
    - ``container`` defaults to ``build_container(settings)``,
    - ``session_factory`` defaults to a factory bound to a new engine built from
      ``settings.database_sync_url`` (the engine connects lazily, not at build
      time).

    ``service_name`` (default ``"mil-worker"``) is written into every JSON log
    line's ``service`` field via ``configure_logging`` — each real worker's
    ``main()`` passes its own name (e.g. ``"mil-worker-ocr"``,
    ``"mil-worker-finding"``) so an on-call engineer can filter logs by which
    pipeline emitted them. Before this, worker processes never called
    ``configure_logging`` at all: only the API process (``main.py``) did, so
    a worker's log lines (when it logged anything) were unstructured
    plain-text, not the JSON format this platform's logging is otherwise
    built around.

    Returns:
        A fully resolved ``WorkerContext``.
    """
    _register_all_models()
    resolved_settings = settings if settings is not None else get_settings()
    configure_logging(log_level=resolved_settings.mil_log_level, service_name=service_name)
    resolved_container = container if container is not None else build_container(resolved_settings)

    if session_factory is not None:
        factory = session_factory
    else:
        engine = create_engine(resolved_settings.database_sync_url)
        factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    job_queue = resolved_container.resolve(JobQueue)
    return WorkerContext(
        container=resolved_container,
        session_factory=factory,
        job_queue=job_queue,
    )


def process_next(
    ctx: WorkerContext,
    handler: JobHandler,
    *,
    timeout: float = 0.0,
    job_type: str | None = None,
) -> bool:
    """
    Claim and process the next available job, if any, in a Unit of Work.

    Steps:
      1. Dequeue a job; return ``False`` immediately if the queue is empty.
      2. Bind the job's correlation id to the request context (ADR-009) and to
         the structured-logging context, so every log line emitted while this
         job is processed — by this function or by the pipeline-specific
         handler it calls — carries the same ``correlation_id``/
         ``application_id``/``tenant_id`` an on-call engineer would grep for.
      3. Open a session and invoke ``handler`` within it.
      4. On success: commit and acknowledge the job.
         On failure: roll back, reject (requeue within the retry budget), and
         re-raise so the caller is aware.

    Args:
        timeout:  Forwarded to ``JobQueue.dequeue``. ``0.0`` (default) returns
                  immediately if the queue is empty — used by ``run_drain`` and
                  tests. A worker's long-running ``main()`` loop passes a
                  positive value so a broker-backed queue (``RedisJobQueue``)
                  blocks efficiently between polls instead of busy-looping.
        job_type: Forwarded to ``JobQueue.dequeue``. Every real worker MUST
                  pass its own step name here — multiple distinct worker types
                  share one physical queue, and without this a worker can
                  dequeue and mishandle a job meant for a different step.

    Returns:
        ``True`` if a job was claimed and processed (the harness handled it),
        ``False`` if the queue was empty (or the timeout elapsed with no job).

    The handler must not commit; the transaction boundary belongs to this
    harness so that the business write, any workflow/step state, and any outbox
    rows commit together (ADR-007 / ADR-008).
    """
    job = ctx.job_queue.dequeue(timeout=timeout, job_type=job_type)
    if job is None:
        return False

    payload = job.payload or {}
    correlation_id = str(payload.get("correlation_id", ""))
    application_id = str(payload.get("application_id", ""))
    tenant_id = str(payload.get("tenant_id", ""))
    context = RequestContext(correlation_id=correlation_id) if correlation_id else RequestContext()
    request_token = set_request_context(context)
    # `replace(...)` preserves `service` (set once, process-wide, by
    # `configure_logging` in `build_worker_context` — e.g. "mil-worker-ocr")
    # rather than constructing a fresh `LogContext`, which would silently
    # reset `service` back to its dataclass default ("mil-api") on every
    # single job, defeating the whole point of a per-worker-type service name.
    log_token = set_log_context(
        replace(
            get_log_context(),
            correlation_id=correlation_id,
            application_id=application_id,
            tenant_id=tenant_id,
            component="worker",
        )
    )

    _log.info(
        "Job dequeued",
        event_type="worker.job.dequeued",
        job_type=job.job_type,
        job_id=str(job.job_id),
        retry_count=job.retry_count,
    )

    session = ctx.session_factory()
    try:
        handler(session, job)
        session.commit()
        ctx.job_queue.acknowledge(job.job_id)
        _log.info(
            "Job completed",
            event_type="worker.job.completed",
            job_type=job.job_type,
            job_id=str(job.job_id),
        )
    except Exception:
        session.rollback()
        ctx.job_queue.reject(job.job_id, requeue=True)
        _log.warning_with_traceback(
            "Job failed; rolled back and requeued for retry",
            event_type="worker.job.failed",
            job_type=job.job_type,
            job_id=str(job.job_id),
            retry_count=job.retry_count,
        )
        raise
    finally:
        session.close()
        reset_request_context(request_token)
        reset_log_context(log_token)

    return True


def run_forever(
    ctx: WorkerContext,
    handler: JobHandler,
    *,
    job_type: str,
    poll_timeout: float,
) -> None:
    """
    Poll for and process jobs indefinitely, surviving any single job's failure.

    Every worker's ``main()`` calls this rather than hand-rolling
    ``while True: process_next(...)``. ``process_next`` re-raises on any
    exception (by design — see its own docstring) so the per-job rollback/
    reject is visible to the caller; without a boundary here, that exception
    would propagate out of the polling loop and kill the entire worker
    process over a *single* bad job — an unhandled ``ConflictError`` (e.g. no
    active Policy Pack for a tenant), a malformed payload, or any other bug
    would silently stop that worker from processing every other application's
    jobs too, indistinguishable from the process being down. This mirrors
    ``mil.api.errors``'s own top-level ``Exception`` handler for HTTP
    requests: log it, keep serving.

    A job that fails for a genuinely retryable reason (``ProviderError`` with
    attempts remaining) is unaffected by this: it is requeued by
    ``process_next``/``reject`` before the exception reaches here, and this
    loop simply continues on to dequeue the next available job (which may be
    that same job, redelivered, once its retry is due).
    """
    while True:
        try:
            process_next(ctx, handler, timeout=poll_timeout, job_type=job_type)
        except Exception:
            _log.exception(
                f"Unhandled exception processing a {job_type} job; continuing to poll.",
                event_type="worker.job.unhandled_exception",
                job_type=job_type,
            )
