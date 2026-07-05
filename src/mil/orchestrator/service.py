"""
IntelligenceOrchestrator — the coordination layer for intelligence workflows.

The orchestrator is a *traffic controller*. It coordinates work; it performs
none of it. It MUST NEVER call OCR, run AI inference, evaluate policies, create
evidence, or create findings. Those responsibilities belong to the Document,
Evidence, Policy, Finding, and Review bounded contexts (Engineering
Constitution, Principle VII; ARCHITECTURE.md §"Intelligence Orchestrator").

What ``start_workflow`` does, in one transaction:

  1. Idempotency check — if a run already exists for the trigger's deterministic
     key, return it unchanged (ADR-008 replay behaviour: no duplicate run).
  2. Create a ``WorkflowRun`` with the version set pinned (ADR-009 / Principle
     XII) and the correlation id established (ADR-009 / Principle X).
  3. Plan the ordered ``WorkflowStep`` records (coordination labels only — no
     execution).
  4. Persist a ``WorkflowStarted`` domain event to the Transactional Outbox
     (ADR-007) — committed atomically with the run and steps.
  5. Enqueue the first step's ``Job`` on the ``JobQueue``.

Correlation propagation (ADR-009): the run's ``correlation_id`` is copied onto
the outbox event, the domain event, and the job payload. No pipeline object
loses the correlation id.

Determinism & idempotency: the same trigger (same ``idempotency_key``) yields
the same single run; the job's idempotency key is derived deterministically
from the run and step.

Dependency rule: imports only from ``mil.orchestrator``, ``mil.outbox``,
``mil.kernel``, and the Python standard library. No other bounded context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mil.kernel.context import generate_correlation_id
from mil.kernel.events import WorkflowStarted
from mil.kernel.job_queue import Job
from mil.kernel.types import ApplicationId, WorkflowRunId
from mil.orchestrator.models import PinnedVersions, WorkflowRun

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from mil.kernel.job_queue import JobQueue
    from mil.kernel.types import TenantId
    from mil.orchestrator.repository import WorkflowRepository
    from mil.outbox.repository import OutboxRepository


class IntelligenceOrchestrator:
    """
    Coordinates intelligence workflows. Contains no business rules.

    Construct per unit of work with repositories bound to the active session
    and the platform job queue, so that the run, its steps, and its outbox
    event all commit in one transaction (ADR-007 / ADR-008).
    """

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        outbox_repository: OutboxRepository,
        job_queue: JobQueue,
    ) -> None:
        self._runs = workflow_repository
        self._outbox = outbox_repository
        self._queue = job_queue

    def start_workflow(
        self,
        *,
        tenant_id: TenantId | UUID,
        application_id: ApplicationId | UUID,
        workflow_type: str,
        idempotency_key: str,
        step_names: Sequence[str],
        pinned_versions: PinnedVersions,
        correlation_id: str | None = None,
        max_retries: int = 3,
        job_payload_extra: dict[str, object] | None = None,
    ) -> WorkflowRun:
        """
        Start (or return the existing) workflow run for a trigger.

        The orchestrator is agnostic to what the steps *do*: ``step_names`` are
        coordination labels supplied by the caller (US2 Sprint 2+ wires the
        concrete pipeline). The orchestrator only sequences and dispatches.

        Args:
            tenant_id:        Institution the run belongs to.
            application_id:   Application the run coordinates.
            workflow_type:    Coordination label (e.g. ``"DOCUMENT_INGESTION"``).
            idempotency_key:  Deterministic key for the triggering work. A
                              repeat call with the same key returns the existing
                              run without creating a duplicate.
            step_names:       Ordered step labels to plan. Must be non-empty.
            pinned_versions:  The four attribution versions, fixed at creation.
            correlation_id:   End-to-end trace id. Generated if not supplied.
            max_retries:      Retry budget recorded on each planned step.
            job_payload_extra: Opaque, caller-supplied context merged into the
                              dispatched job's payload (e.g. ``{"document_id": …}``
                              from a ``DocumentIngested`` trigger). The orchestrator
                              forwards it without interpretation — it remains a
                              pure traffic controller. Reserved coordination keys
                              cannot be overridden.

        Returns:
            The created (or pre-existing) ``WorkflowRun``.
        """
        # 1. Idempotency: a repeat trigger returns the existing run unchanged.
        existing = self._runs.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        if not step_names:
            from mil.kernel.errors import ValidationError

            raise ValidationError("step_names must not be empty", field="step_names")

        corr = correlation_id if correlation_id else generate_correlation_id()

        # 2. Create the run with versions pinned and correlation id established.
        run = WorkflowRun.create(
            tenant_id=tenant_id,
            application_id=application_id,
            workflow_type=workflow_type,
            idempotency_key=idempotency_key,
            correlation_id=corr,
            pinned_versions=pinned_versions,
        )

        # 3. Plan the ordered steps (coordination labels only — no execution).
        for order, name in enumerate(step_names):
            run.plan_step(step_name=name, step_order=order, max_retries=max_retries)

        run.mark_running()
        self._runs.save(run)

        # 4. Persist the WorkflowStarted event to the outbox in the SAME
        #    transaction (ADR-007). correlation_id propagates onto the event.
        started = WorkflowStarted(
            tenant_id=run.tenant_id,  # type: ignore[arg-type]
            workflow_run_id=WorkflowRunId(run.id),
            application_id=ApplicationId(run.application_id),
            workflow_type=run.workflow_type,
            correlation_id=run.correlation_id,
        )
        self._outbox.add(started)

        # 5. Enqueue the first step. correlation_id propagates onto the job.
        #    Reserved coordination keys are written last so caller-supplied
        #    context can never override them.
        first_step = run.steps[0]
        payload: dict[str, object] = dict(job_payload_extra or {})
        payload.update(
            {
                "workflow_run_id": str(run.id),
                "step_id": str(first_step.id),
                "step_name": first_step.step_name,
                "application_id": str(run.application_id),
                "tenant_id": str(run.tenant_id),
                "correlation_id": run.correlation_id,
            }
        )
        self._queue.enqueue(
            Job(
                # job_type = the step name, not a generic label: multiple
                # distinct worker types share one physical queue, and each
                # must only ever dequeue jobs for its own step (JobQueue's
                # docstring / ADR-008 note explain why this matters).
                job_type=first_step.step_name,
                idempotency_key=self._step_idempotency_key(run.id, first_step.step_name),
                payload=payload,
                max_retries=max_retries,
            )
        )

        return run

    @staticmethod
    def _step_idempotency_key(workflow_run_id: UUID, step_name: str) -> str:
        """
        Deterministic idempotency key for a step's job (ADR-008).

        Derived from the run id and step name — never from a random value — so
        a redelivered trigger computes the same key and the queue deduplicates.
        """
        return f"{workflow_run_id}:{step_name}"
