"""
JobQueue abstraction for the MIL Platform.

The ``JobQueue`` interface is the platform-level primitive for dispatching and
processing asynchronous work units.  The Intelligence Orchestrator enqueues
jobs; background worker processes dequeue and execute them.

The concrete backing implementation (in-process, Redis, AMQP, etc.) is
registered in the dependency injection container at startup.  All platform
code resolves ``JobQueue`` from the container — no direct dependency on a
concrete broker exists in the domain layer.

This module provides:

- ``Job`` — an immutable frozen descriptor with idempotency guarantees.
- ``JobQueue`` — abstract interface for enqueue/dequeue/acknowledge cycles.
- ``InProcessJobQueue`` — synchronous, in-memory implementation for
  development and testing.
- ``RedisJobQueue`` — the real, process-safe implementation. The API process
  and every worker process construct their own client against the same Redis
  instance, so a job enqueued by one process is visible to every other
  (ADR-007 / ADR-008: the plan's production topology is multi-process — API
  process + worker processes + broker — and ``InProcessJobQueue`` cannot
  deliver work across that boundary; it is a development/test convenience
  only, never a correctness mechanism, per ADR-007 §"Interaction with the
  in-process implementations" and ADR-008 §"Interaction with the in-process
  implementations").

Idempotency: both implementations deduplicate enqueue calls by
``idempotency_key``.  A job with the same key is silently skipped if an
identical key is already pending or processing.  Upon acknowledgement the
key is released so the same logical job can be re-enqueued in future
(e.g. after a periodic delay or a new trigger). Per ADR-008, this dedup is a
convenience, not the platform's durable idempotency guarantee — that is the
database unique constraint enforced by each worker's repository layer.

Dependency rule: this module imports only from the Python standard library
and the ``redis`` client library (for ``RedisJobQueue``). No bounded context
code should be imported here.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis

# ---------------------------------------------------------------------------
# Job descriptor
# ---------------------------------------------------------------------------


def _new_job_id() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclasses.dataclass(frozen=True, eq=False)
class Job:
    """
    An immutable unit of asynchronous work.

    ``job_id`` uniquely identifies this particular job instance.
    ``idempotency_key`` is a stable, caller-supplied key that prevents the
    same logical work unit from being enqueued multiple times (e.g. the same
    document being ingested twice due to a retry at the HTTP layer).

    ``payload`` is a free-form dict of JSON-safe values that carry the data
    the worker needs to execute the job.  The platform does not interpret the
    payload; it is opaque to the queue layer.

    Two ``Job`` instances are considered equal if and only if they share the
    same ``job_id``.  Hash is also derived from ``job_id`` so that jobs can
    be placed in sets and used as dict keys.
    """

    job_id: str = dataclasses.field(default_factory=_new_job_id)
    job_type: str = ""
    idempotency_key: str = ""
    payload: dict[str, object] = dataclasses.field(default_factory=dict)
    created_at: datetime = dataclasses.field(default_factory=_now_utc)
    max_retries: int = 3
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id cannot be empty")
        if not self.job_type:
            raise ValueError("job_type cannot be empty")
        if not self.idempotency_key:
            raise ValueError("idempotency_key cannot be empty")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Job):
            return NotImplemented
        return self.job_id == other.job_id

    def __hash__(self) -> int:
        return hash(self.job_id)


# ---------------------------------------------------------------------------
# Abstract JobQueue interface
# ---------------------------------------------------------------------------


class JobQueue:
    """
    Abstract interface for the platform job queue.

    Workers call ``dequeue`` to claim the next available job, process it,
    then call ``acknowledge`` on success or ``reject`` on failure.

    Subclasses MUST override all methods.  This base class raises
    ``NotImplementedError`` for all operations so that missing overrides are
    caught at runtime during development.

    Design note: this is a concrete class with ``NotImplementedError``, not an
    ABC.  Using ABC would force mypy to reject ``register_singleton(JobQueue,
    InProcessJobQueue)`` in the container without a ``type: ignore`` comment on
    every callsite.  ``NotImplementedError`` achieves the same safety guarantee
    (missing overrides fail loudly) while keeping container registration clean.
    """

    def enqueue(self, job: Job) -> None:
        """
        Submit a job for asynchronous processing.

        Implementations MUST deduplicate by ``idempotency_key``: if a job
        with the same key is already pending or processing, the new job is
        silently dropped.
        """
        raise NotImplementedError

    def dequeue(self, timeout: float = 0.0, *, job_type: str | None = None) -> Job | None:
        """
        Claim the next available job for processing.

        Returns ``None`` if the queue is empty (for in-process implementations)
        or if the timeout elapses (for broker-backed implementations).

        The returned job transitions to a "processing" state and will not be
        returned by subsequent ``dequeue`` calls until it is acknowledged or
        rejected.

        Args:
            timeout:  Seconds to wait for a job.  ``0.0`` returns immediately.
            job_type: Restrict to jobs of this ``Job.job_type`` (a worker
                      passes its own step name, e.g. ``"OCR"``). ``None``
                      matches any job type. Every real worker process MUST
                      pass its own type here: multiple distinct worker types
                      (OCR, EXTRACTION, FINDING, POLICY, REVIEW) share one
                      physical queue, and without this filter any worker
                      could dequeue and mishandle a job meant for another
                      step (this is not a hypothetical — it reproduced
                      immediately the first time two real worker processes
                      polled the same Redis-backed queue).
        """
        raise NotImplementedError

    def acknowledge(self, job_id: str) -> None:
        """
        Mark a job as successfully completed.

        Releases the idempotency key so the same logical job can be
        re-enqueued in future.  Acknowledging an unknown ``job_id`` is a
        no-op.
        """
        raise NotImplementedError

    def reject(self, job_id: str, requeue: bool = True) -> None:
        """
        Mark a job as failed.

        If ``requeue`` is ``True`` and ``job.retry_count < job.max_retries``,
        the job is re-enqueued with an incremented ``retry_count``.  If retries
        are exhausted or ``requeue`` is ``False``, the job is discarded and
        its idempotency key is released.

        Rejecting an unknown ``job_id`` is a no-op.
        """
        raise NotImplementedError

    def pending_count(self) -> int:
        """Return the number of jobs waiting to be dequeued."""
        raise NotImplementedError

    def processing_count(self) -> int:
        """Return the number of jobs currently claimed by workers."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# In-process implementation
# ---------------------------------------------------------------------------


class InProcessJobQueue(JobQueue):
    """
    Synchronous, in-memory ``JobQueue`` implementation.

    Jobs are stored in a ``deque``; dequeue is FIFO.  Retried jobs are
    placed at the head of the queue so they are attempted before new work.

    Idempotency is enforced via an internal ``set`` of active idempotency
    keys.  A key is "active" from the moment a job is enqueued until the
    moment it is acknowledged (success) or exhausts its retries (failure).
    During this window, calling ``enqueue`` with the same key is a no-op.

    Thread-safety: not guaranteed.  Intended for single-threaded test suites
    and local development.  Production deployments should register a
    broker-backed implementation.
    """

    def __init__(self) -> None:
        self._pending: deque[Job] = deque()
        self._processing: dict[str, Job] = {}
        self._active_idempotency_keys: set[str] = set()

    def enqueue(self, job: Job) -> None:
        if job.idempotency_key in self._active_idempotency_keys:
            return
        self._active_idempotency_keys.add(job.idempotency_key)
        self._pending.append(job)

    def dequeue(self, timeout: float = 0.0, *, job_type: str | None = None) -> Job | None:
        job: Job | None
        if job_type is None:
            if not self._pending:
                return None
            job = self._pending.popleft()
        else:
            # Linear scan for the first matching type, preserving the
            # relative order of every other job left in the deque.
            job = next((j for j in self._pending if j.job_type == job_type), None)
            if job is None:
                return None
            self._pending.remove(job)
        self._processing[job.job_id] = job
        return job

    def acknowledge(self, job_id: str) -> None:
        job = self._processing.pop(job_id, None)
        if job is not None:
            self._active_idempotency_keys.discard(job.idempotency_key)

    def reject(self, job_id: str, requeue: bool = True) -> None:
        job = self._processing.pop(job_id, None)
        if job is None:
            return
        if requeue and job.retry_count < job.max_retries:
            # Job is frozen, so create a new instance with the incremented counter.
            retry_job = dataclasses.replace(job, retry_count=job.retry_count + 1)
            self._pending.appendleft(retry_job)
        else:
            self._active_idempotency_keys.discard(job.idempotency_key)

    def pending_count(self) -> int:
        return len(self._pending)

    def processing_count(self) -> int:
        return len(self._processing)

    def clear(self) -> None:
        """Discard all pending and processing jobs. Useful between test cases."""
        self._pending.clear()
        self._processing.clear()
        self._active_idempotency_keys.clear()


# ---------------------------------------------------------------------------
# Redis-backed implementation (process-safe)
# ---------------------------------------------------------------------------


class RedisJobQueue(JobQueue):
    """
    Process-safe ``JobQueue`` backed by Redis.

    This is the platform's real queue: the API process and every worker
    process construct their own ``RedisJobQueue`` around a client pointed at
    the same Redis instance, so a job enqueued by one process is durably
    visible to every other. This is the missing piece that made
    ``InProcessJobQueue`` unable to deliver work from the API process to a
    separately-launched worker process — each held its own private,
    in-memory queue with no shared backing store.

    Storage (all keys namespaced under ``key_prefix``, default
    ``"mil:jobqueue"``):

    - ``{prefix}:pending:{job_type}`` — one Redis LIST per job type. Multiple
      distinct worker types (OCR, EXTRACTION, FINDING, POLICY, REVIEW) share
      this one Redis instance but MUST NOT share a single physical list: a
      worker only knows how to execute jobs for its own step, so it must only
      ever dequeue from its own type's list (this is not a hypothetical — it
      reproduced immediately the first time two real worker processes polled
      an earlier, unpartitioned version of this queue: the Extraction worker
      dequeued an OCR job and crashed trying to process it as one).
      Fresh jobs are pushed with ``RPUSH`` (tail); dequeue pops with
      ``LPOP``/``BLPOP`` (head) — FIFO, mirroring ``InProcessJobQueue``'s
      ``deque.append`` + ``popleft``. A retried job is pushed with ``LPUSH``
      (head) so it is the very next job dequeued for that type — mirroring
      ``InProcessJobQueue.reject``'s ``appendleft`` priority.
    - ``{prefix}:job_types``   — a Redis SET recording every job type ever
      enqueued, so a type-agnostic ``dequeue(job_type=None)`` (or
      ``pending_count()``) knows which per-type lists to check. Real workers
      always pass their own ``job_type``; the type-agnostic path exists for
      callers (and tests) that do not care which step a job belongs to.
    - ``{prefix}:processing``  — a Redis HASH mapping ``job_id`` to the
      serialized job currently claimed by a worker (shared across types —
      ``job_id`` is already globally unique), so ``acknowledge`` / ``reject``
      can look up the full ``Job`` (needed to release its idempotency key or
      compute its retry, and to know which per-type list to requeue onto)
      from only a ``job_id``.
    - ``{prefix}:idempotency`` — a Redis SET of idempotency keys currently
      active (pending or processing), shared across types. ``enqueue`` uses
      ``SADD``'s return value (0 if already a member) to perform an atomic
      check-and-set-then-push, so two processes racing to enqueue the same
      logical job cannot both succeed.

    Known limitations (documented, not hidden):

    - A worker crash between dequeuing a job (moved into ``processing``) and
      acknowledging/rejecting it leaves that job parked in ``processing`` with
      no automatic reaper to requeue it. Per ADR-008, the platform's durable
      correctness guarantee is the database unique constraint at each
      worker's repository layer, not queue-level exactly-once bookkeeping — a
      stuck job here is an operational liveness concern (visible via
      ``processing_count()``), not a correctness one. A stale-job reaper is a
      reasonable future addition, out of scope for making the existing
      architecture function.
    - A blocking ``dequeue(timeout=..., job_type=None)`` cannot wait for a job
      type that has never been enqueued in this Redis keyspace before: with no
      job of that type ever seen, there is no per-type list key yet for
      ``BLPOP`` to watch. This never affects a real worker, which always
      dequeues with its own explicit ``job_type`` (a concrete key it can watch
      whether or not anything has been enqueued under it yet); it only
      matters for the type-agnostic convenience path.

    Args:
        client:     A constructed ``redis.Redis`` client (tests inject one
                    pointed at a real or fake Redis instance).
        key_prefix: Namespace prefix for all keys this instance uses.
    """

    def __init__(self, client: redis.Redis, *, key_prefix: str = "mil:jobqueue") -> None:
        self._redis = client
        self._prefix = key_prefix

    def _key(self, suffix: str) -> str:
        return f"{self._prefix}:{suffix}"

    def _pending_key(self, job_type: str) -> str:
        return self._key(f"pending:{job_type}")

    def _known_job_types(self) -> list[str]:
        return [self._as_str(t) for t in self._redis.smembers(self._key("job_types"))]

    @staticmethod
    def _serialize(job: Job) -> str:
        return json.dumps(
            {
                "job_id": job.job_id,
                "job_type": job.job_type,
                "idempotency_key": job.idempotency_key,
                "payload": job.payload,
                "created_at": job.created_at.isoformat(),
                "max_retries": job.max_retries,
                "retry_count": job.retry_count,
            }
        )

    @staticmethod
    def _as_str(raw: bytes | str | list[bytes | str]) -> str:
        """Decode a Redis reply to ``str``. A no-op when ``decode_responses=True``."""
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        if isinstance(raw, list):
            # Never happens for single-key BLPOP/LPOP/HGET replies; the redis-py
            # stubs type this defensively for multi-key blocking variants.
            raise TypeError(f"Expected a scalar Redis reply, got a list: {raw!r}")
        return raw

    @classmethod
    def _deserialize(cls, raw: bytes | str) -> Job:
        data = json.loads(cls._as_str(raw))
        return Job(
            job_id=data["job_id"],
            job_type=data["job_type"],
            idempotency_key=data["idempotency_key"],
            payload=data["payload"],
            created_at=datetime.fromisoformat(data["created_at"]),
            max_retries=data["max_retries"],
            retry_count=data["retry_count"],
        )

    def enqueue(self, job: Job) -> None:
        # SADD returns the number of members actually added (0 if the key was
        # already a member) — an atomic check-and-set, so a duplicate enqueue
        # from a concurrent process is dropped without a separate read+write
        # race window.
        added = self._redis.sadd(self._key("idempotency"), job.idempotency_key)
        if added == 0:
            return
        self._redis.sadd(self._key("job_types"), job.job_type)
        self._redis.rpush(self._pending_key(job.job_type), self._serialize(job))

    def dequeue(self, timeout: float = 0.0, *, job_type: str | None = None) -> Job | None:
        # Resolve to the concrete pending-list key(s) to poll: exactly one
        # when a worker specifies its own job_type, or every type ever
        # enqueued when it does not care (job_type=None).
        types = [job_type] if job_type is not None else self._known_job_types()
        pending_keys = [self._pending_key(t) for t in types]
        if not pending_keys:
            return None  # no job type has ever been enqueued — nothing to wait on

        if timeout <= 0.0:
            raw = None
            for key in pending_keys:
                raw = self._redis.lpop(key)
                if raw is not None:
                    break
        else:
            # BLPOP accepts multiple keys atomically — checked in list order,
            # blocking until any one of them has an item or timeout elapses.
            popped = self._redis.blpop(pending_keys, timeout=timeout)
            raw = popped[1] if popped is not None else None
        if raw is None:
            return None
        raw = self._as_str(raw)
        job = self._deserialize(raw)
        self._redis.hset(self._key("processing"), job.job_id, raw)
        return job

    def acknowledge(self, job_id: str) -> None:
        raw = self._redis.hget(self._key("processing"), job_id)
        if raw is None:
            return
        self._redis.hdel(self._key("processing"), job_id)
        job = self._deserialize(raw)
        self._redis.srem(self._key("idempotency"), job.idempotency_key)

    def reject(self, job_id: str, requeue: bool = True) -> None:
        raw = self._redis.hget(self._key("processing"), job_id)
        if raw is None:
            return
        self._redis.hdel(self._key("processing"), job_id)
        job = self._deserialize(raw)
        if requeue and job.retry_count < job.max_retries:
            retry_job = dataclasses.replace(job, retry_count=job.retry_count + 1)
            self._redis.lpush(self._pending_key(job.job_type), self._serialize(retry_job))
        else:
            self._redis.srem(self._key("idempotency"), job.idempotency_key)

    def pending_count(self) -> int:
        return sum(int(self._redis.llen(self._pending_key(t))) for t in self._known_job_types())

    def processing_count(self) -> int:
        return int(self._redis.hlen(self._key("processing")))
