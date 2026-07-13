"""
Persistence gateway for the Intelligence Orchestrator bounded context.

``WorkflowRepository`` persists and retrieves ``WorkflowRun`` aggregates (and
their owned ``WorkflowStep`` rows). It does not commit or roll back — the caller
owns the unit of work, so the run, its steps, and any outbox events written by
the orchestrator commit atomically together (ADR-007, ADR-008 per-job Unit of
Work).

The repository performs no business logic and emits no events itself. The
orchestrator service is responsible for outbox writes and job enqueue.

Dependency rule: imports only from ``mil.orchestrator.models``, ``mil.kernel``,
and the Python standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from mil.orchestrator.models import WorkflowRun, WorkflowStep

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class WorkflowRepository:
    """
    Read/write gateway for ``WorkflowRun`` aggregates.

    Construct with the caller's active session. ``save`` adds the run (with its
    cascaded steps) and flushes so server-side defaults and constraint
    violations surface within the caller's transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, run: WorkflowRun) -> None:
        """
        Persist a workflow run and its owned steps.

        Adds the aggregate to the session and flushes. The owned ``steps`` are
        cascaded by the relationship. Commit is the caller's responsibility, so
        the run, its steps, and any outbox rows written in the same session
        commit atomically.
        """
        self._session.add(run)
        self._session.flush()

    def get_by_id(self, workflow_run_id: UUID) -> WorkflowRun | None:
        """Return the run with the given id, or ``None`` if not found."""
        return self._session.get(WorkflowRun, workflow_run_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> WorkflowRun | None:
        """
        Return the run with the given idempotency key, or ``None``.

        Used by the orchestrator to make ``start_workflow`` idempotent: a repeat
        trigger with the same key returns the existing run instead of creating
        a duplicate (ADR-008 replay behaviour).
        """
        stmt = select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        return self._session.scalars(stmt).one_or_none()

    def get_for_application(self, application_id: UUID) -> list[WorkflowRun]:
        """Return all workflow runs for an application, most recent first."""
        stmt = (
            select(WorkflowRun)
            .where(WorkflowRun.application_id == application_id)
            .order_by(WorkflowRun.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def count_by_type_and_status(self, tenant_id: UUID) -> list[tuple[str, str, int]]:
        """
        Return ``(workflow_type, status, count)`` rows for every workflow run
        in a tenant (spec 005-enterprise-platform §10, Wave 3 — Operational
        Dashboard's real queue-depth signal). A single aggregated query, not
        an all-rows fetch — scales with the number of distinct
        (workflow_type, status) pairs, not the number of runs.
        """
        stmt = (
            select(WorkflowRun.workflow_type, WorkflowRun.status, func.count(WorkflowRun.id))
            .where(WorkflowRun.tenant_id == tenant_id)
            .group_by(WorkflowRun.workflow_type, WorkflowRun.status)
        )
        return [(wt, status, int(count)) for wt, status, count in self._session.execute(stmt).all()]

    def get_poison_steps(self, tenant_id: UUID) -> list[WorkflowStep]:
        """
        Return every ``WorkflowStep`` that has exhausted its retry ceiling
        (``retry_count >= max_retries``) and is still ``FAILED`` — the RC1
        release checklist's documented "poison job" risk (no redelivery/
        visibility-timeout on worker crash) made *visible*, not fixed, per
        spec 005-enterprise-platform §10, Wave 3. A real, defensible proxy
        for "exceeded retry ceiling": this schema has no separate
        "abandoned mid-flight" flag, so a step a crashed worker never
        revisited stays ``IN_PROGRESS`` forever and is not counted here —
        an honest limitation, not fabricated detection.
        """
        stmt = (
            select(WorkflowStep)
            .join(WorkflowRun, WorkflowStep.workflow_run_id == WorkflowRun.id)
            .where(
                WorkflowRun.tenant_id == tenant_id,
                WorkflowStep.status == "FAILED",
                WorkflowStep.retry_count >= WorkflowStep.max_retries,
            )
        )
        return list(self._session.scalars(stmt))
