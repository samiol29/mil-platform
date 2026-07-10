"""
Policy Pipeline Worker (US2 Sprint 5).

This is the composition root for Policy jobs, dispatched by the Finding
worker (``workers.finding_pipeline``) when the FINDING stage completes. It
delegates to the Policy context (evaluate the persisted Finding against the
tenant's active Policy Pack, persist the immutable ``PolicyResult``),
advances the Orchestrator's ``WorkflowStep``, and publishes ``PolicyEvaluated``
through the Transactional Outbox. It contains no business *rules* — no human
review, no Copilot. It performs job pickup, execution dispatch, and result
reporting only.

Responsibilities (and explicit non-responsibilities):
    - Resolves ``PolicyProvider`` exclusively via ``ProviderRegistry``.
    - Loads the ``Finding`` produced by the FINDING step (never re-runs
      inference, never mutates the Finding).
    - Loads the tenant's active ``PolicyPack`` and its rule catalogue.
    - Executes evaluation and persists the immutable ``PolicyResult`` via
      ``PolicyService`` (full provider-version attribution — Principle XII).
    - Emits the newly added typed ``PolicyEvaluated`` ``DomainEvent`` through
      the Transactional Outbox (ADR-007) — never published directly to the bus.
    - Advances the ``WorkflowStep`` state (ADR-008 per-job Unit of Work), and,
      on success, dispatches the workflow's next planned step (``REVIEW``,
      US2 Sprint 6) exactly as ``workers.finding_pipeline`` dispatches
      ``POLICY`` after ``FINDING`` — or completes the ``WorkflowRun`` if
      ``POLICY`` is the last planned step (older runs / tests with no Review
      step planned).
    - Never performs human review, never invokes Copilot, never mutates
      ``Finding`` or ``EvidenceItem`` rows.

Per-job Unit of Work (ADR-008): everything a job writes — the PolicyResult,
the audit event (synchronous, same transaction), the workflow step/run state,
and the outbox event — commits in the single transaction owned by
``workers.bootstrap.process_next``. A crash before commit leaves no partial
state; the redelivered job re-runs, and idempotency (the unique constraint on
``(finding_id, policy_version)``, checked via
``PolicyRepository.exists_for_finding_and_version``) makes the replay a no-op.

Version pinning (ADR-009 / Principle XII): the workflow run pins the policy
engine version at creation, in ``workers.finding_pipeline.
start_finding_generation_workflow`` (``run.pinned_versions.policy``). This
worker validates that the registered ``PolicyProvider``'s live ``version()``
matches the pinned value before evaluating — a mismatch is a structural
configuration drift, not a transient fault, and is therefore terminal
(non-retryable).

Provider resolution is exclusively through the DI container (``ProviderRegistry``).
Concrete provider classes are never imported or instantiated here.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from mil.audit.writer import AuditWriter
from mil.finding.repository import FindingRepository
from mil.kernel.errors import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderVersionMissingError,
)
from mil.kernel.events import PolicyEvaluated, WorkflowStepFailed
from mil.kernel.job_queue import Job, JobQueue
from mil.kernel.metrics import MetricName
from mil.kernel.observability import MetricEmitter, NoOpMetricEmitter
from mil.kernel.providers.policy import PolicyEvaluationContext, PolicyRuleDefinition
from mil.kernel.providers.registry import ProviderRegistry
from mil.kernel.types import ApplicationId, FindingId, PolicyPackId, TenantId, WorkflowRunId
from mil.orchestrator.models import StepStatus, WorkflowRun, WorkflowStep
from mil.orchestrator.repository import WorkflowRepository
from mil.orchestrator.retry import (
    DeadLetterSink,
    NoOpDeadLetterSink,
    RetryDecision,
    RetryPolicy,
)
from mil.outbox.repository import OutboxRepository
from mil.policy.repository import PolicyRepository
from mil.policy.service import PolicyService
from workers.bootstrap import build_worker_context, process_next, run_forever

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mil.finding.models import Finding
    from mil.kernel.container import Container
    from mil.kernel.providers.policy import PolicyProvider
    from mil.policy.models import PolicyRule
    from workers.bootstrap import JobHandler, WorkerContext

# POLICY step label — dispatched by the Finding worker after FINDING completes.
POLICY_STEP_NAME = "POLICY"

# REVIEW step label — dispatched after POLICY completes (US2 Sprint 6).
# Duplicated as a literal here (rather than imported from
# workers.review_pipeline) to avoid a cross-worker import dependency; the two
# workers agree on this job-payload contract, not on shared code.
_REVIEW_STEP_NAME = "REVIEW"

# How long main()'s polling loop blocks on RedisJobQueue.dequeue() waiting for
# a job before checking again. A long-running worker process, not a one-shot
# drain — see main()'s docstring.
_POLL_TIMEOUT_SECONDS = 5.0


class PolicyProcessingOutcome(enum.StrEnum):
    """
    Result of processing one Policy job.

    COMPLETED       — evaluation ran, the PolicyResult was persisted, the step
                      (and run) completed, and ``PolicyEvaluated`` was queued.
    ALREADY_DONE    — a result already existed for (finding, policy version);
                      the job was a replay and was treated as a no-op.
    FAILED_TERMINAL — evaluation failed permanently; the step is FAILED and
                      ``WorkflowStepFailed`` was queued.

    A retryable failure with attempts remaining does not produce an outcome — it
    propagates so the Unit of Work rolls back and the queue requeues the job.
    """

    COMPLETED = "COMPLETED"
    ALREADY_DONE = "ALREADY_DONE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


@dataclass(frozen=True)
class PolicyCollaborators:
    """Session-scoped collaborators for processing one Policy job."""

    policy_provider: PolicyProvider
    findings: FindingRepository
    policy: PolicyService
    policy_repo: PolicyRepository
    workflows: WorkflowRepository
    outbox: OutboxRepository
    job_queue: JobQueue
    metrics: MetricEmitter = field(default_factory=NoOpMetricEmitter)


class PolicyJobProcessor:
    """
    Coordinates a single Policy job. Holds no business rules.

    Construct per job with session-scoped collaborators plus the retry policy
    and dead-letter sink (process-scoped extension points, ADR-008).
    """

    def __init__(
        self,
        collaborators: PolicyCollaborators,
        *,
        retry_policy: RetryPolicy | None = None,
        dead_letter: DeadLetterSink | None = None,
    ) -> None:
        self._c = collaborators
        self._retry = retry_policy if retry_policy is not None else RetryPolicy()
        self._dead_letter = dead_letter if dead_letter is not None else NoOpDeadLetterSink()

    def process(self, job: Job) -> PolicyProcessingOutcome:
        """
        Process one Policy job end-to-end within the caller's transaction.

        A tenant with no active Policy Pack is a terminal (not retryable)
        failure handled internally via ``_handle_failure`` — it does not
        raise, so the job is acknowledged rather than requeued.

        Raises:
            NotFoundError: If the workflow run, step, or Finding is missing.
            ProviderError: Re-raised for a retryable failure with attempts
                remaining, so the Unit of Work rolls back and the job requeues.
        """
        finding_id = _uuid(job.payload, "finding_id")
        workflow_run_id = _uuid(job.payload, "workflow_run_id")
        step_name = str(job.payload.get("step_name", POLICY_STEP_NAME))
        tenant_id = _uuid(job.payload, "tenant_id")
        application_id = _uuid(job.payload, "application_id")
        correlation_id = str(job.payload.get("correlation_id", ""))

        run = self._c.workflows.get_by_id(workflow_run_id)
        if run is None:
            raise NotFoundError("WorkflowRun", workflow_run_id)
        step = _find_step(run, step_name)
        if step is None:
            raise NotFoundError("WorkflowStep", step_name)

        # ADR-009 / Principle XII: validate the live provider matches the
        # version pinned to this run at creation — never trust the provider's
        # live version() output as the source of truth.
        expected_version = run.pinned_versions.policy
        provider_version = self._c.policy_provider.version()
        self._validate_provider_version(provider_version, expected_version)

        # Idempotent replay: a PolicyResult already generated deterministically
        # for this (finding, policy version). Treat as a no-op (ADR-008).
        if self._c.policy_repo.exists_for_finding_and_version(finding_id, expected_version):
            if step.status != StepStatus.COMPLETED:
                step.mark_completed()
                if _is_last_step(run, step):
                    run.mark_completed()
                self._c.workflows.save(run)
            return PolicyProcessingOutcome.ALREADY_DONE

        finding = self._c.findings.get_by_id(finding_id)
        if finding is None:
            raise NotFoundError("Finding", finding_id)

        step.mark_in_progress()
        step.record_retry(job.retry_count)

        active_pack = self._c.policy_repo.get_active_pack_for_tenant(tenant_id)
        if active_pack is None:
            # Terminal, not retryable — no amount of retrying makes a Policy
            # Pack appear. Routed through the same terminal-failure handling
            # as a non-retryable ProviderError, rather than a bare raise: a
            # bare raise propagates past this method entirely, and
            # `process_next`'s generic exception handler requeues
            # unconditionally on ANY exception with no retryability check —
            # confirmed live, the identical bug already found and fixed in
            # `finding_pipeline.py`'s no-evidence guard. This turns a tenant
            # with no active Policy Pack into a poison job that starves the
            # entire POLICY queue forever.
            return self._handle_failure(
                run=run,
                step=step,
                workflow_run_id=workflow_run_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                job=job,
                exc=ConflictError(f"Tenant {tenant_id} has no active Policy Pack"),
            )
        rules = self._c.policy_repo.get_rules_for_pack(active_pack.id)

        try:
            context = _build_context(finding, rules)
            result = self._c.policy_provider.evaluate(context)
            self._validate_result_version(result.policy_version, provider_version)
        except ProviderError as exc:
            return self._handle_failure(
                run=run,
                step=step,
                workflow_run_id=workflow_run_id,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                job=job,
                exc=exc,
            )

        # Success: persist the immutable PolicyResult, complete the step (and
        # run, since POLICY is the last planned step), publish.
        policy_result, created = self._c.policy.record_policy_result(
            finding_id=finding_id,
            application_id=application_id,
            tenant_id=tenant_id,
            workflow_run_id=workflow_run_id,
            policy_pack_id=active_pack.id,
            result=result,
        )
        step.mark_completed()
        if _is_last_step(run, step):
            run.mark_completed()
        self._c.workflows.save(run)
        if created:
            # Lost a race against another worker otherwise (ADR-008 §5): the
            # audit event and PolicyEvaluated were already published by
            # whichever worker actually committed the result.
            self._c.outbox.add(
                PolicyEvaluated(
                    tenant_id=TenantId(tenant_id),
                    finding_id=FindingId(finding_id),
                    application_id=ApplicationId(application_id),
                    policy_pack_id=PolicyPackId(active_pack.id),
                    policy_version=policy_result.policy_version,
                    outcome=policy_result.outcome,
                    correlation_id=correlation_id,
                )
            )
        self._dispatch_next_step(
            run=run,
            completed_step=step,
            application_id=application_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            finding_id=finding_id,
            policy_result_id=policy_result.id,
        )
        return PolicyProcessingOutcome.COMPLETED

    def _dispatch_next_step(
        self,
        *,
        run: WorkflowRun,
        completed_step: WorkflowStep,
        application_id: UUID,
        tenant_id: UUID,
        correlation_id: str,
        finding_id: UUID,
        policy_result_id: UUID,
    ) -> None:
        """
        Enqueue the job for the next planned step (``REVIEW``, US2 Sprint 6),
        if any.

        Mirrors ``workers.finding_pipeline``'s FINDING -> POLICY dispatch:
        same job type, same idempotency-key derivation. A run with no further
        planned steps (e.g. two-step FINDING_GENERATION runs predating
        Sprint 6) is a no-op.
        """
        next_step = next(
            (s for s in run.steps if s.step_order == completed_step.step_order + 1), None
        )
        if next_step is None or next_step.status != StepStatus.PENDING:
            return
        self._c.job_queue.enqueue(
            Job(
                job_type=next_step.step_name,
                idempotency_key=f"{run.id}:{next_step.step_name}",
                payload={
                    "workflow_run_id": str(run.id),
                    "step_id": str(next_step.id),
                    "step_name": next_step.step_name,
                    "application_id": str(application_id),
                    "tenant_id": str(tenant_id),
                    "correlation_id": correlation_id,
                    "finding_id": str(finding_id),
                    "policy_result_id": str(policy_result_id),
                },
                max_retries=next_step.max_retries,
            )
        )

    # ------------------------------------------------------------------
    # Failure handling (ADR-008 retry classification)
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        *,
        run: WorkflowRun,
        step: WorkflowStep,
        workflow_run_id: UUID,
        tenant_id: UUID,
        correlation_id: str,
        job: Job,
        exc: ProviderError | ConflictError,
    ) -> PolicyProcessingOutcome:
        decision = self._retry.classify(
            exc, retry_count=job.retry_count, max_retries=job.max_retries
        )
        if decision is RetryDecision.RETRY:
            # Re-raise so the Unit of Work rolls back and the queue requeues.
            raise exc

        # Terminal: record the permanent failure within this transaction.
        if decision is RetryDecision.RETRIES_EXHAUSTED:
            self._dead_letter.record(job, exc)

        self._c.metrics.increment(MetricName.PROVIDER_FAILURES_TOTAL)
        step.record_retry(job.retry_count)
        step.mark_failed(error_code=exc.code, error_message=exc.message)
        run.mark_failed()
        self._c.workflows.save(run)
        self._c.outbox.add(
            WorkflowStepFailed(
                tenant_id=TenantId(tenant_id),
                workflow_run_id=WorkflowRunId(workflow_run_id),
                step_name=step.step_name,
                error_code=exc.code,
                error_message=exc.message,
                retry_count=job.retry_count,
                correlation_id=correlation_id,
            )
        )
        return PolicyProcessingOutcome.FAILED_TERMINAL

    @staticmethod
    def _validate_provider_version(reported_version: str, expected_version: str) -> None:
        """
        Enforce the pinned-version contract (ADR-009 / Principle XII).

        A missing or drifted provider version relative to the version pinned
        on the workflow run is a structural violation, not a transient fault —
        it is terminal (non-retryable).
        """
        if not reported_version:
            raise ProviderVersionMissingError("PolicyProvider", "version")
        if reported_version != expected_version:
            raise ProviderError(
                f"PolicyProvider version mismatch: registered provider reports "
                f"{reported_version!r}, workflow run pinned {expected_version!r}",
                provider_name="PolicyProvider",
                retryable=False,
            )

    @staticmethod
    def _validate_result_version(result_version: str, expected_version: str) -> None:
        """
        Enforce that the returned ``PolicyEvaluationResult`` reports the same
        version as the provider's own ``version()`` — an internal consistency
        contract violation is terminal (non-retryable).
        """
        if not result_version:
            raise ProviderVersionMissingError("PolicyProvider", "policy_version")
        if result_version != expected_version:
            raise ProviderError(
                f"PolicyProvider returned a PolicyEvaluationResult with policy_version "
                f"{result_version!r}, expected {expected_version!r}",
                provider_name="PolicyProvider",
                retryable=False,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid(payload: dict[str, object], key: str) -> UUID:
    value = payload.get(key)
    if value is None:
        raise NotFoundError("PolicyJobPayloadField", key)
    return UUID(str(value))


def _find_step(run: WorkflowRun, step_name: str) -> WorkflowStep | None:
    return next((s for s in run.steps if s.step_name == step_name), None)


def _is_last_step(run: WorkflowRun, step: WorkflowStep) -> bool:
    return bool(run.steps) and step.step_order == run.steps[-1].step_order


def _build_context(finding: Finding, rules: list[PolicyRule]) -> PolicyEvaluationContext:
    """Build the scoped ``PolicyEvaluationContext`` from a Finding and its rule catalogue."""
    available = tuple(
        PolicyRuleDefinition(
            rule_key=rule.rule_key,
            name=rule.name,
            severity=rule.severity,
            description=rule.description,
        )
        for rule in rules
    )
    return PolicyEvaluationContext(
        application_id=str(finding.application_id),
        finding_ref=str(finding.id),
        finding_type=finding.finding_type,
        confidence_score=float(finding.confidence_score),
        evidence_summary=finding.evidence_summary,
        available_rules=available,
    )


# ---------------------------------------------------------------------------
# Wiring (composition root)
# ---------------------------------------------------------------------------


def build_policy_collaborators(session: Session, container: Container) -> PolicyCollaborators:
    """
    Build the session-scoped collaborators for one Policy job.

    Providers are resolved exclusively through the DI container's
    ``ProviderRegistry`` — concrete provider classes are never imported here.
    """
    registry = container.resolve(ProviderRegistry)
    policy_provider = registry.get_policy()
    metrics = container.resolve(MetricEmitter)  # type: ignore[type-abstract]

    audit = AuditWriter(session, metrics=metrics)
    policy_repository = PolicyRepository(session)
    policy_service = PolicyService(policy_repository, audit)
    return PolicyCollaborators(
        policy_provider=policy_provider,
        findings=FindingRepository(session),
        policy=policy_service,
        policy_repo=policy_repository,
        workflows=WorkflowRepository(session),
        outbox=OutboxRepository(session),
        job_queue=container.resolve(JobQueue),
        metrics=metrics,
    )


def make_policy_handler(
    container: Container,
    *,
    retry_policy: RetryPolicy | None = None,
    dead_letter: DeadLetterSink | None = None,
) -> JobHandler:
    """
    Build a ``JobHandler`` that processes Policy jobs.

    The returned handler builds session-scoped collaborators per job and runs
    the ``PolicyJobProcessor``. It does not commit — the bootstrap harness
    owns the transaction (per-job Unit of Work).
    """

    def handler(session: Session, job: Job) -> None:
        collaborators = build_policy_collaborators(session, container)
        processor = PolicyJobProcessor(
            collaborators, retry_policy=retry_policy, dead_letter=dead_letter
        )
        processor.process(job)

    return handler


def run_drain(ctx: WorkerContext, handler: JobHandler, *, max_iterations: int | None = None) -> int:
    """
    Process available jobs until the queue is empty (or ``max_iterations``).

    Returns the number of jobs processed. Bounded by ``max_iterations`` when
    supplied (used by tests); unbounded draining stops when the queue is empty.
    """
    processed = 0
    while max_iterations is None or processed < max_iterations:
        if not process_next(ctx, handler):
            break
        processed += 1
    return processed


def main() -> None:  # pragma: no cover - process entry point
    """
    Entry point for the Policy pipeline worker process.

    Runs indefinitely as a long-running service — see
    ``workers.document_pipeline.main``'s docstring for the same rationale.
    """
    ctx = build_worker_context()
    handler = make_policy_handler(ctx.container)
    run_forever(ctx, handler, job_type=POLICY_STEP_NAME, poll_timeout=_POLL_TIMEOUT_SECONDS)


if __name__ == "__main__":  # pragma: no cover
    main()
