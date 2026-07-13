"""
Unit tests for ``mil.api.deps.FindingTrigger`` — the composition-root wrapper
that starts the FINDING_GENERATION workflow on application submission
(ADR-009).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from mil.api.deps import FindingTrigger
from mil.application.models import MortgageApplication
from mil.kernel.errors import AuthorizationError, ConflictError
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId


def _application() -> MortgageApplication:
    app = MortgageApplication.create(tenant_id=uuid4(), created_by=uuid4(), los_reference="LOS-1")
    app.collect_pending_events()
    return app


def _user(*roles: str) -> AuthenticatedUser:
    if not roles:
        roles = (Role.RELATIONSHIP_MANAGER,)
    return AuthenticatedUser(
        user_id=UserId(uuid4()), tenant_id=TenantId(uuid4()), roles=frozenset(roles)
    )


def _run(workflow_type: str = "FINDING_GENERATION", status: str = "FAILED") -> MagicMock:
    run = MagicMock()
    run.workflow_type = workflow_type
    run.status = status
    return run


class TestFindingTrigger:
    def test_trigger_delegates_to_start_finding_generation_workflow(self) -> None:
        session = MagicMock()
        container = MagicMock()
        trigger = FindingTrigger(session=session, container=container)
        app = _application()

        with patch("workers.finding_pipeline.start_finding_generation_workflow") as start_mock:
            trigger.trigger(app)

        start_mock.assert_called_once_with(
            session, container, application_id=app.id, tenant_id=app.tenant_id
        )

    def test_trigger_returns_the_workflow_run(self) -> None:
        session = MagicMock()
        container = MagicMock()
        trigger = FindingTrigger(session=session, container=container)
        app = _application()
        sentinel_run = MagicMock()

        with patch(
            "workers.finding_pipeline.start_finding_generation_workflow",
            return_value=sentinel_run,
        ):
            result = trigger.trigger(app)

        assert result is sentinel_run


class TestFindingTriggerLatestRun:
    def test_returns_none_when_no_runs_exist(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        with patch("mil.api.deps.WorkflowRepository") as repo_cls:
            repo_cls.return_value.get_for_application.return_value = []
            assert trigger.latest_run(app) is None

    def test_returns_most_recent_finding_generation_run(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        finding_run = _run(workflow_type="FINDING_GENERATION", status="COMPLETED")
        other_run = _run(workflow_type="DOCUMENT_INGESTION", status="COMPLETED")
        with patch("mil.api.deps.WorkflowRepository") as repo_cls:
            repo_cls.return_value.get_for_application.return_value = [finding_run, other_run]
            assert trigger.latest_run(app) is finding_run

    def test_ignores_non_finding_generation_runs(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        other_run = _run(workflow_type="DOCUMENT_INGESTION", status="COMPLETED")
        with patch("mil.api.deps.WorkflowRepository") as repo_cls:
            repo_cls.return_value.get_for_application.return_value = [other_run]
            assert trigger.latest_run(app) is None


class TestFindingTriggerRetry:
    def test_retries_when_latest_run_failed(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        user = _user(Role.RELATIONSHIP_MANAGER)
        failed_run = _run(status="FAILED")
        with (
            patch("mil.api.deps.WorkflowRepository") as repo_cls,
            patch("workers.finding_pipeline.start_finding_generation_workflow") as start_mock,
        ):
            repo_cls.return_value.get_for_application.return_value = [failed_run]
            trigger.retry(user, app)
        start_mock.assert_called_once_with(
            trigger._session,
            trigger._container,
            application_id=app.id,
            tenant_id=app.tenant_id,
            retry_count=1,
        )

    def test_retry_count_reflects_number_of_prior_runs(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        user = _user(Role.RELATIONSHIP_MANAGER)
        runs = [_run(status="FAILED"), _run(status="FAILED"), _run(status="COMPLETED")]
        with (
            patch("mil.api.deps.WorkflowRepository") as repo_cls,
            patch("workers.finding_pipeline.start_finding_generation_workflow") as start_mock,
        ):
            repo_cls.return_value.get_for_application.return_value = runs
            trigger.retry(user, app)
        assert start_mock.call_args.kwargs["retry_count"] == 3

    def test_raises_conflict_when_no_runs_exist(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        user = _user(Role.RELATIONSHIP_MANAGER)
        with patch("mil.api.deps.WorkflowRepository") as repo_cls:
            repo_cls.return_value.get_for_application.return_value = []
            with pytest.raises(ConflictError):
                trigger.retry(user, app)

    def test_raises_conflict_when_latest_run_not_failed(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        user = _user(Role.RELATIONSHIP_MANAGER)
        with patch("mil.api.deps.WorkflowRepository") as repo_cls:
            repo_cls.return_value.get_for_application.return_value = [_run(status="RUNNING")]
            with pytest.raises(ConflictError):
                trigger.retry(user, app)

    def test_requires_write_application_permission(self) -> None:
        trigger = FindingTrigger(session=MagicMock(), container=MagicMock())
        app = _application()
        user = _user(Role.RISK_ANALYST)
        with patch("mil.api.deps.WorkflowRepository") as repo_cls:
            repo_cls.return_value.get_for_application.return_value = [_run(status="FAILED")]
            with pytest.raises(AuthorizationError):
                trigger.retry(user, app)
