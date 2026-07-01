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
    FindingTrigger,
    get_application_service,
    get_current_user,
    get_document_service,
    get_finding_trigger,
)
from mil.application.models import ApplicationStatus, MortgageApplication, Party, PartyType
from mil.application.service import ApplicationService
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
) -> MortgageApplication:
    """Return a MortgageApplication domain object with test-friendly defaults."""
    app = MortgageApplication.create(
        tenant_id=TEST_TENANT_ID,
        created_by=TEST_USER_ID,
        los_reference=los_reference,
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
def mock_finding_trigger() -> MagicMock:
    """Mocked FindingTrigger (the DRAFT -> SUBMITTED composition root, ADR-009)."""
    return MagicMock(spec=FindingTrigger)


@pytest.fixture()
def client(
    current_user: AuthenticatedUser,
    mock_app_service: MagicMock,
    mock_doc_service: MagicMock,
    mock_finding_trigger: MagicMock,
) -> TestClient:
    """
    Return a synchronous TestClient with all service and auth deps overridden.

    The lifespan is disabled so tests do not need a database or DI container.
    """
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_application_service] = lambda: mock_app_service
    app.dependency_overrides[get_document_service] = lambda: mock_doc_service
    app.dependency_overrides[get_finding_trigger] = lambda: mock_finding_trigger
    return TestClient(app, raise_server_exceptions=True)
