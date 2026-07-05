"""
Unit tests for ``mil.api.deps.FindingTrigger`` — the composition-root wrapper
that starts the FINDING_GENERATION workflow on application submission
(ADR-009).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from mil.api.deps import FindingTrigger
from mil.application.models import MortgageApplication


def _application() -> MortgageApplication:
    app = MortgageApplication.create(tenant_id=uuid4(), created_by=uuid4(), los_reference="LOS-1")
    app.collect_pending_events()
    return app


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
