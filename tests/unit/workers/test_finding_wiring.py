"""
Wiring tests for the Finding worker composition root, including the
FINDING_GENERATION workflow trigger (ADR-009: DRAFT -> SUBMITTED).

Verifies that the InferenceProvider is resolved exclusively through the DI
container's ``ProviderRegistry``, that the handler runs the processor within a
session, and that the trigger derives pinned versions and dispatches the
FINDING job idempotently.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from mil.evidence.models import EvidenceItem
from mil.kernel.config import get_settings
from mil.kernel.container import build_container
from mil.kernel.job_queue import InProcessJobQueue, JobQueue
from mil.kernel.providers.extraction import EvidenceAttributes
from mil.kernel.providers.inference import InferenceProvider
from mil.kernel.providers.registry import ProviderRegistry
from mil.orchestrator.models import WorkflowStatus
from workers.finding_pipeline import (
    FINDING_STEP_NAME,
    FINDING_WORKFLOW_TYPE,
    build_finding_collaborators,
    make_finding_handler,
    start_finding_generation_workflow,
)


class TestBuildCollaborators:
    def test_resolves_inference_provider_from_registry(self) -> None:
        container = build_container(get_settings())
        collaborators = build_finding_collaborators(MagicMock(), container)
        assert isinstance(collaborators.inference_provider, InferenceProvider)

    def test_provider_comes_through_the_registry(self) -> None:
        """The provider must be resolved via ProviderRegistry, not instantiated."""
        container = build_container(get_settings())
        registry = container.resolve(ProviderRegistry)
        collaborators = build_finding_collaborators(MagicMock(), container)
        assert collaborators.inference_provider is registry.get_inference()

    def test_builds_session_scoped_repositories(self) -> None:
        container = build_container(get_settings())
        session = MagicMock()
        collaborators = build_finding_collaborators(session, container)
        assert collaborators.evidence_items is not None
        assert collaborators.finding is not None
        assert collaborators.findings is not None
        assert collaborators.workflows is not None
        assert collaborators.outbox is not None
        assert collaborators.job_queue is not None


class TestMakeFindingHandler:
    def test_returns_callable_handler(self) -> None:
        container = build_container(get_settings())
        handler = make_finding_handler(container)
        assert callable(handler)


# ---------------------------------------------------------------------------
# start_finding_generation_workflow — the DRAFT -> SUBMITTED trigger (ADR-009)
# ---------------------------------------------------------------------------


def _evidence_item(*, application_id: UUID, extraction_model_version: str) -> EvidenceItem:
    attrs = EvidenceAttributes(
        field_name="gross_monthly_income",
        field_value="5000.00",
        document_id="doc-1",
        source_document_ref="ref-1",
        page_number=1,
        field_location=None,
        extraction_confidence=0.9,
        extraction_method="mock-keyword-matcher",
        extracted_at=datetime.now(UTC),
        extraction_version=extraction_model_version,
    )
    return EvidenceItem.create(
        application_id=application_id,
        document_id=uuid4(),
        workflow_run_id=uuid4(),
        tenant_id=uuid4(),
        attrs=attrs,
    )


def _mock_session(
    evidence_items: list[EvidenceItem] | None = None, *, existing_run: object = None
) -> MagicMock:
    """
    Build a session mock that serves two distinct queries through the same
    ``session.scalars(...)`` call: ``EvidenceRepository.get_for_application``
    (consumed via iteration) and ``WorkflowRepository.get_by_idempotency_key``
    (consumed via ``.one_or_none()``). Both must be satisfiable from the same
    mocked return value since the trigger issues both through one session.
    """
    session = MagicMock()
    scalars_result = MagicMock()
    scalars_result.__iter__ = lambda self: iter(evidence_items or [])
    scalars_result.one_or_none.return_value = existing_run
    session.scalars.return_value = scalars_result
    return session


class TestStartFindingGenerationWorkflow:
    def _container_with_job_queue(self) -> tuple[object, InProcessJobQueue]:
        container = build_container(get_settings())
        queue = InProcessJobQueue()
        container.register_instance(JobQueue, queue)
        return container, queue

    def test_starts_a_new_workflow_run(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session, container, application_id=uuid4(), tenant_id=uuid4()
        )
        assert run.workflow_type == FINDING_WORKFLOW_TYPE
        assert run.status == WorkflowStatus.RUNNING

    def test_plans_the_finding_policy_and_review_steps(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session, container, application_id=uuid4(), tenant_id=uuid4()
        )
        assert [s.step_name for s in run.steps] == [FINDING_STEP_NAME, "POLICY", "REVIEW"]

    def test_pins_the_live_inference_provider_version(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        registry = container.resolve(ProviderRegistry)
        run = start_finding_generation_workflow(
            session, container, application_id=uuid4(), tenant_id=uuid4()
        )
        assert run.pinned_versions.inference == registry.get_inference().version()

    def test_pins_the_live_policy_provider_version(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        registry = container.resolve(ProviderRegistry)
        run = start_finding_generation_workflow(
            session, container, application_id=uuid4(), tenant_id=uuid4()
        )
        assert run.pinned_versions.policy == registry.get_policy().version()

    def test_extraction_version_is_na_when_no_evidence(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session, container, application_id=uuid4(), tenant_id=uuid4()
        )
        assert run.pinned_versions.extraction == "n/a"

    def test_extraction_version_derived_from_evidence(self) -> None:
        application_id = uuid4()
        items = [
            _evidence_item(application_id=application_id, extraction_model_version="v2"),
            _evidence_item(application_id=application_id, extraction_model_version="v1"),
        ]
        session = _mock_session(items)
        container, _ = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session, container, application_id=application_id, tenant_id=uuid4()
        )
        assert run.pinned_versions.extraction == "v1,v2"

    def test_dispatches_the_finding_job(self) -> None:
        session = _mock_session()
        container, queue = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session, container, application_id=uuid4(), tenant_id=uuid4()
        )
        job = queue.dequeue()
        assert job is not None
        assert job.payload["step_name"] == FINDING_STEP_NAME
        assert job.payload["workflow_run_id"] == str(run.id)

    def test_deterministic_idempotency_key_per_application(self) -> None:
        """
        The idempotency key is derived solely from the application id, so a
        repeated trigger for the same application always computes the same
        key — the property ``IntelligenceOrchestrator.start_workflow`` (already
        unit-tested independently) relies on to make replays a no-op (ADR-008).
        """
        application_id = uuid4()
        session_one = _mock_session()
        container_one, _ = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session_one, container_one, application_id=application_id, tenant_id=uuid4()
        )
        assert run.idempotency_key == f"{FINDING_WORKFLOW_TYPE}:{application_id}"

    def test_retry_count_zero_preserves_original_key(self) -> None:
        application_id = uuid4()
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session, container, application_id=application_id, tenant_id=uuid4(), retry_count=0
        )
        assert run.idempotency_key == f"{FINDING_WORKFLOW_TYPE}:{application_id}"

    def test_retry_count_distinguishes_the_idempotency_key(self) -> None:
        """
        A real retry must mint a new key — IntelligenceOrchestrator.start_workflow
        returns the existing run for a repeat key, so an unchanged key would
        make retry a silent no-op.
        """
        application_id = uuid4()
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_finding_generation_workflow(
            session, container, application_id=application_id, tenant_id=uuid4(), retry_count=1
        )
        assert run.idempotency_key == f"{FINDING_WORKFLOW_TYPE}:{application_id}:retry1"

    def test_retry_dispatches_a_new_job_instead_of_no_op(self) -> None:
        application_id = uuid4()
        tenant_id = uuid4()
        container, queue = self._container_with_job_queue()

        first = start_finding_generation_workflow(
            _mock_session(), container, application_id=application_id, tenant_id=tenant_id
        )
        queue.dequeue()

        retried = start_finding_generation_workflow(
            _mock_session(),
            container,
            application_id=application_id,
            tenant_id=tenant_id,
            retry_count=1,
        )
        assert retried.id != first.id
        assert queue.dequeue() is not None

    def test_repeat_call_with_existing_run_returns_it_unchanged(self) -> None:
        """Simulates a replay where the idempotency lookup finds a prior run."""
        application_id = uuid4()
        tenant_id = uuid4()
        container, queue = self._container_with_job_queue()

        first = start_finding_generation_workflow(
            _mock_session(), container, application_id=application_id, tenant_id=tenant_id
        )
        queue.dequeue()

        second = start_finding_generation_workflow(
            _mock_session(existing_run=first),
            container,
            application_id=application_id,
            tenant_id=tenant_id,
        )
        assert second is first
        # No second job dispatched for the replay.
        assert queue.dequeue() is None
