"""
Wiring tests for ``start_document_ingestion_workflow`` — the trigger that
starts the ``DOCUMENT_INGESTION`` (OCR -> Extraction) workflow immediately
after a document upload.

Mirrors ``test_finding_wiring.py``'s ``TestStartFindingGenerationWorkflow``:
verifies the pinned-version derivation, planned steps, idempotent replay
behaviour, and job dispatch, using a mocked session and the real DI container
(so the OCR/Extraction providers are resolved exactly as they would be at
runtime — this is what previously never happened at all: without this
trigger, an uploaded document never advanced past PENDING).
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from mil.kernel.config import get_settings
from mil.kernel.container import build_container
from mil.kernel.job_queue import InProcessJobQueue, JobQueue
from mil.kernel.providers.extraction import ExtractionProvider
from mil.kernel.providers.registry import ProviderRegistry
from mil.orchestrator.models import WorkflowStatus
from workers.document_pipeline import (
    DOCUMENT_INGESTION_WORKFLOW_TYPE,
    EXTRACTION_STEP_NAME,
    OCR_STEP_NAME,
    start_document_ingestion_workflow,
)


def _mock_session(*, existing_run: object = None) -> MagicMock:
    """
    Session mock serving ``WorkflowRepository.get_by_idempotency_key`` (the
    only query this trigger issues) via ``session.scalars(...).one_or_none()``.
    """
    session = MagicMock()
    scalars_result = MagicMock()
    scalars_result.one_or_none.return_value = existing_run
    session.scalars.return_value = scalars_result
    return session


class TestStartDocumentIngestionWorkflow:
    def _container_with_job_queue(self) -> tuple[object, InProcessJobQueue]:
        container = build_container(get_settings())
        queue = InProcessJobQueue()
        container.register_instance(JobQueue, queue)
        return container, queue

    def test_starts_a_new_workflow_run(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_document_ingestion_workflow(
            session,
            container,
            document_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
        )
        assert run.workflow_type == DOCUMENT_INGESTION_WORKFLOW_TYPE
        assert run.status == WorkflowStatus.RUNNING

    def test_plans_the_ocr_and_extraction_steps_in_order(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_document_ingestion_workflow(
            session,
            container,
            document_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
        )
        assert [s.step_name for s in run.steps] == [OCR_STEP_NAME, EXTRACTION_STEP_NAME]

    def test_pins_the_live_extraction_provider_version(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        registry = container.resolve(ProviderRegistry)
        run = start_document_ingestion_workflow(
            session,
            container,
            document_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
        )
        assert isinstance(registry.get_extraction(), ExtractionProvider)
        assert run.pinned_versions.extraction == registry.get_extraction().version()

    def test_non_applicable_dimensions_are_pinned_to_sentinel(self) -> None:
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_document_ingestion_workflow(
            session,
            container,
            document_id=uuid4(),
            application_id=uuid4(),
            tenant_id=uuid4(),
        )
        assert run.pinned_versions.policy == "n/a"
        assert run.pinned_versions.inference == "n/a"
        assert run.pinned_versions.prompt == "n/a"

    def test_dispatches_the_ocr_job_with_document_id(self) -> None:
        session = _mock_session()
        container, queue = self._container_with_job_queue()
        document_id = uuid4()
        run = start_document_ingestion_workflow(
            session,
            container,
            document_id=document_id,
            application_id=uuid4(),
            tenant_id=uuid4(),
        )
        job = queue.dequeue()
        assert job is not None
        assert job.payload["step_name"] == OCR_STEP_NAME
        assert job.payload["workflow_run_id"] == str(run.id)
        assert job.payload["document_id"] == str(document_id)

    def test_deterministic_idempotency_key_per_document(self) -> None:
        document_id = uuid4()
        session = _mock_session()
        container, _ = self._container_with_job_queue()
        run = start_document_ingestion_workflow(
            session,
            container,
            document_id=document_id,
            application_id=uuid4(),
            tenant_id=uuid4(),
        )
        assert run.idempotency_key == f"{DOCUMENT_INGESTION_WORKFLOW_TYPE}:{document_id}"

    def test_repeat_call_with_existing_run_returns_it_unchanged(self) -> None:
        """Simulates a replay where the idempotency lookup finds a prior run."""
        document_id = uuid4()
        application_id = uuid4()
        tenant_id = uuid4()
        container, queue = self._container_with_job_queue()

        first = start_document_ingestion_workflow(
            _mock_session(),
            container,
            document_id=document_id,
            application_id=application_id,
            tenant_id=tenant_id,
        )
        queue.dequeue()

        second = start_document_ingestion_workflow(
            _mock_session(existing_run=first),
            container,
            document_id=document_id,
            application_id=application_id,
            tenant_id=tenant_id,
        )
        assert second.id == first.id
        assert queue.dequeue() is None  # no duplicate job dispatched
