"""
Shared fixtures for API unit tests.

These fixtures wire up a FastAPI TestClient with all service dependencies
replaced by ``MagicMock`` objects.  No database, storage provider, or event
bus is required — all I/O is intercepted at the service boundary.

Auth:
    Tests inject an ``AuthenticatedUser`` directly via the ``current_user``
    override fixture.  Route handlers receive a real ``AuthenticatedUser``
    object with configurable roles.

Services:
    ``mock_app_service`` and ``mock_doc_service`` are ``MagicMock`` instances
    that replace ``get_application_service`` and ``get_document_service``
    respectively.  Test methods configure return values on these mocks.

Usage::

    def test_something(client, mock_app_service):
        mock_app_service.get_application.return_value = some_app
        response = client.get("/v1/applications/...")
        assert response.status_code == 200
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import create_app
from mil.api.deps import (
    DocumentIngestionTrigger,
    FindingTrigger,
    get_application_service,
    get_copilot_service,
    get_current_user,
    get_document_ingestion_trigger,
    get_document_service,
    get_finding_trigger,
)
from mil.application.models import ApplicationStatus, MortgageApplication, Party, PartyType
from mil.application.service import ApplicationService
from mil.copilot.service import CopilotService
from mil.document.models import Document
from mil.document.service import DocumentService
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId

# ---------------------------------------------------------------------------
# Default test identities
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_TENANT_ID = uuid4()
TEST_APP_ID = uuid4()
TEST_PARTY_ID = uuid4()
TEST_DOC_ID = uuid4()

_SAMPLE_CONTENT = b"sample pdf bytes for testing"
_SAMPLE_HASH = hashlib.sha256(_SAMPLE_CONTENT).hexdigest()


def make_user(*roles: str) -> AuthenticatedUser:
    """Return an AuthenticatedUser with the given roles."""
    if not roles:
        roles = (Role.ADMIN,)
    return AuthenticatedUser(
        user_id=UserId(TEST_USER_ID),
        tenant_id=TenantId(TEST_TENANT_ID),
        roles=frozenset(roles),
        email="test@mil.test",
        display_name="Test User",
    )


# ---------------------------------------------------------------------------
# Domain object factories
# ---------------------------------------------------------------------------


def make_application(
    *,
    app_id=None,
    status: str = ApplicationStatus.DRAFT,
    los_reference: str | None = "LOS-001",
    loan_number: str | None = "LN-0001",
) -> MortgageApplication:
    """Return a MortgageApplication domain object with test-friendly defaults."""
    app = MortgageApplication.create(
        tenant_id=TEST_TENANT_ID,
        created_by=TEST_USER_ID,
        los_reference=los_reference,
        loan_number=loan_number,
    )
    if app_id is not None:
        object.__setattr__(app, "id", app_id)
    app.status = status
    app.collect_pending_events()  # drain so tests start clean
    return app


def make_party(application_id=None) -> Party:
    """Return a Party domain object with test-friendly defaults."""
    now = datetime.now(UTC)
    party = Party(
        id=TEST_PARTY_ID,
        application_id=application_id or TEST_APP_ID,
        party_type=PartyType.APPLICANT,
        display_name="Primary Borrower",
    )
    party.created_at = now
    return party


def make_copilot_session(*, application_id=None, session_id=None, tenant_id=None):
    """Return a CopilotSession domain object with test-friendly defaults."""
    from mil.copilot.models import CopilotSession

    session = CopilotSession.create(
        application_id=application_id or TEST_APP_ID,
        tenant_id=tenant_id or TEST_TENANT_ID,
        created_by_user_id=TEST_USER_ID,
        correlation_id="test-correlation-id",
    )
    if session_id is not None:
        object.__setattr__(session, "id", session_id)
    return session


def make_copilot_query(*, session_id=None, query_id=None, question_text="Why was this flagged?"):
    """Return a CopilotQuery domain object with test-friendly defaults."""
    from mil.copilot.models import CopilotQuery

    query = CopilotQuery.create(
        session_id=session_id or TEST_APP_ID,
        asked_by_user_id=TEST_USER_ID,
        question_text=question_text,
    )
    if query_id is not None:
        object.__setattr__(query, "id", query_id)
    return query


def make_copilot_response(*, query_id=None, citations=()):
    """Return a CopilotResponse domain object with test-friendly defaults."""
    from mil.copilot.models import CopilotResponse

    return CopilotResponse.create(
        query_id=query_id or uuid4(),
        answer_text="Grounded answer citing all supplied records.",
        prompt_version="freeform-question-v1",
        model_version="mock-inference-1.0.0",
        citations=citations,
    )


def make_evidence_item(application_id=None, document_id=None, evidence_id=None):
    """Return an EvidenceItem domain object with test-friendly defaults."""
    from mil.evidence.models import EvidenceItem
    from mil.kernel.providers.extraction import EvidenceAttributes, FieldLocation

    attrs = EvidenceAttributes(
        field_name="gross_monthly_income",
        field_value="6200.00",
        document_id=str(document_id or TEST_DOC_ID),
        source_document_ref="ref-1",
        page_number=2,
        field_location=FieldLocation(page_number=2, field_name="gross_monthly_income"),
        extraction_confidence=0.9,
        extraction_method="mock-keyword-matcher",
        extracted_at=datetime(2026, 6, 21, 10, 15, tzinfo=UTC),
        extraction_version="mock-extraction-1.0.0",
    )
    item = EvidenceItem.create(
        application_id=application_id or TEST_APP_ID,
        document_id=document_id or TEST_DOC_ID,
        workflow_run_id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        attrs=attrs,
    )
    if evidence_id is not None:
        object.__setattr__(item, "id", evidence_id)
    return item


def make_finding(application_id=None, finding_id=None, evidence_item_ids=None):
    """Return a Finding domain object with test-friendly defaults."""
    from decimal import Decimal

    from mil.finding.models import Finding

    finding = Finding.create(
        application_id=application_id or TEST_APP_ID,
        tenant_id=TEST_TENANT_ID,
        workflow_run_id=uuid4(),
        finding_type="AI_GENERATED_ASSESSMENT",
        title="Reported income does not match pay stub",
        rationale="Application states $6,500/month; extracted value is $6,200/month.",
        evidence_summary="gross_monthly_income=6200.00",
        confidence_label="HIGH",
        recommended_action="Confirm current income with the borrower.",
        confidence_score=Decimal("0.900"),
        model_version="mock-inference-1.0.0",
        prompt_version="finding-generation-prompt-v1",
        extraction_version="mock-extraction-1.0.0",
        evidence_item_ids=evidence_item_ids or [uuid4()],
    )
    if finding_id is not None:
        object.__setattr__(finding, "id", finding_id)
    return finding


def make_document(application_id=None, doc_id=None) -> Document:
    """Return a Document domain object with test-friendly defaults."""
    doc = Document.create(
        tenant_id=TEST_TENANT_ID,
        application_id=application_id or TEST_APP_ID,
        uploaded_by=TEST_USER_ID,
        original_filename="payslip.pdf",
        mime_type="PAYSLIP",
        size_bytes=len(_SAMPLE_CONTENT),
        content_hash=_SAMPLE_HASH,
        storage_reference="/tmp/mil-test/" + _SAMPLE_HASH,
    )
    if doc_id is not None:
        object.__setattr__(doc, "id", doc_id)
    doc.collect_pending_events()  # drain so tests start clean
    return doc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def current_user() -> AuthenticatedUser:
    """Default test user with ADMIN role."""
    return make_user(Role.ADMIN)


@pytest.fixture()
def mock_app_service() -> MagicMock:
    """Mocked ApplicationService."""
    return MagicMock(spec=ApplicationService)


@pytest.fixture()
def mock_doc_service() -> MagicMock:
    """Mocked DocumentService."""
    return MagicMock(spec=DocumentService)


@pytest.fixture()
def mock_ingestion_trigger() -> MagicMock:
    """Mocked DocumentIngestionTrigger (the upload -> DOCUMENT_INGESTION composition root)."""
    return MagicMock(spec=DocumentIngestionTrigger)


@pytest.fixture()
def mock_finding_trigger() -> MagicMock:
    """Mocked FindingTrigger (the DRAFT -> SUBMITTED composition root, ADR-009)."""
    return MagicMock(spec=FindingTrigger)


@pytest.fixture()
def mock_copilot_service() -> MagicMock:
    """Mocked CopilotService."""
    return MagicMock(spec=CopilotService)


@pytest.fixture()
def mock_evidence_service() -> MagicMock:
    """Mocked EvidenceService."""
    from mil.evidence.service import EvidenceService

    return MagicMock(spec=EvidenceService)


@pytest.fixture()
def mock_finding_service() -> MagicMock:
    """Mocked FindingService."""
    from mil.finding.service import FindingService

    return MagicMock(spec=FindingService)


@pytest.fixture()
def mock_finding_review_actions() -> MagicMock:
    """Mocked FindingReviewActions (the verify/override HTTP composition root)."""
    from mil.api.deps import FindingReviewActions

    return MagicMock(spec=FindingReviewActions)


@pytest.fixture()
def mock_audit_repository() -> MagicMock:
    """Mocked AuditRepository."""
    from mil.audit.repository import AuditRepository

    return MagicMock(spec=AuditRepository)


@pytest.fixture()
def mock_storage_provider() -> MagicMock:
    """Mocked StorageProvider."""
    from mil.kernel.providers.storage import StorageProvider

    return MagicMock(spec=StorageProvider)


@pytest.fixture()
def client(
    current_user: AuthenticatedUser,
    mock_app_service: MagicMock,
    mock_doc_service: MagicMock,
    mock_ingestion_trigger: MagicMock,
    mock_finding_trigger: MagicMock,
    mock_copilot_service: MagicMock,
    mock_evidence_service: MagicMock,
    mock_finding_service: MagicMock,
    mock_finding_review_actions: MagicMock,
    mock_audit_repository: MagicMock,
    mock_storage_provider: MagicMock,
) -> TestClient:
    """
    Return a synchronous TestClient with all service and auth deps overridden.

    The lifespan is disabled so tests do not need a database or DI container.
    """
    from mil.api.deps import (
        get_audit_repository,
        get_evidence_service,
        get_finding_review_actions,
        get_finding_service,
        get_storage_provider,
    )

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_application_service] = lambda: mock_app_service
    app.dependency_overrides[get_document_service] = lambda: mock_doc_service
    app.dependency_overrides[get_document_ingestion_trigger] = lambda: mock_ingestion_trigger
    app.dependency_overrides[get_finding_trigger] = lambda: mock_finding_trigger
    app.dependency_overrides[get_copilot_service] = lambda: mock_copilot_service
    app.dependency_overrides[get_evidence_service] = lambda: mock_evidence_service
    app.dependency_overrides[get_finding_service] = lambda: mock_finding_service
    app.dependency_overrides[get_finding_review_actions] = lambda: mock_finding_review_actions
    app.dependency_overrides[get_audit_repository] = lambda: mock_audit_repository
    app.dependency_overrides[get_storage_provider] = lambda: mock_storage_provider
    return TestClient(app, raise_server_exceptions=True)
