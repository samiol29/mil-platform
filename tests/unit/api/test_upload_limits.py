"""
Backend Freeze Patch v1.0 — fix 5: configurable upload size limits.

Verifies an oversized upload is rejected cleanly with HTTP 413 before the
service is invoked, and a within-limit upload still succeeds.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock  # noqa: TC003

from fastapi.testclient import TestClient  # noqa: TC002

from mil.api.deps import get_app_settings
from mil.kernel.config import Settings
from tests.unit.api.conftest import TEST_APP_ID, make_document


def _upload(client: TestClient, content: bytes) -> object:
    files = {"file": ("doc.pdf", io.BytesIO(content), "application/pdf")}
    return client.post(
        f"/v1/applications/{TEST_APP_ID}/documents",
        files=files,
        data={"document_type": "PAYSLIP"},
    )


def test_oversized_upload_rejected(client: TestClient, mock_doc_service: MagicMock) -> None:
    client.app.dependency_overrides[get_app_settings] = lambda: Settings(mil_max_upload_bytes=8)
    response = _upload(client, b"x" * 64)
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "PAYLOAD_TOO_LARGE"
    mock_doc_service.ingest_document.assert_not_called()


def test_within_limit_upload_succeeds(client: TestClient, mock_doc_service: MagicMock) -> None:
    mock_doc_service.ingest_document.return_value = make_document()
    client.app.dependency_overrides[get_app_settings] = lambda: Settings(
        mil_max_upload_bytes=10_000
    )
    response = _upload(client, b"small-body")
    assert response.status_code == 201
    mock_doc_service.ingest_document.assert_called_once()
