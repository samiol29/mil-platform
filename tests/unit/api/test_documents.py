"""Unit tests for Document API endpoints."""

from __future__ import annotations

import io
from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.document.models import IngestionStatus
from mil.kernel.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from tests.unit.api.conftest import (
    TEST_APP_ID,
    TEST_DOC_ID,
    make_document,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _multipart(
    content: bytes = b"sample pdf content",
    filename: str = "payslip.pdf",
    document_type: str = "PAYSLIP",
    party_id: str | None = None,
) -> dict[object, object]:
    """Return keyword args for client.post(...) that match the upload endpoint."""
    files = {"file": (filename, io.BytesIO(content), "application/pdf")}
    data: dict[str, object] = {"document_type": document_type}
    if party_id is not None:
        data["party_id"] = party_id
    return {"files": files, "data": data}


# ---------------------------------------------------------------------------
# POST /v1/applications/{id}/documents
# ---------------------------------------------------------------------------


class TestUploadDocument:
    def test_returns_201(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(),
        )
        assert response.status_code == 201

    def test_returns_document_response(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        data = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(),
        ).json()
        assert "id" in data
        assert "content_hash" in data
        assert "ingestion_status" in data
        assert data["ingestion_status"] == IngestionStatus.PENDING
        assert data["filename"] == doc.original_filename

    def test_document_type_passed_as_mime_type(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        """document_type form field → mime_type parameter in service."""
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(document_type="BANK_STATEMENT"),
        )
        call_kwargs = mock_doc_service.ingest_document.call_args.kwargs
        assert call_kwargs["mime_type"] == "BANK_STATEMENT"

    def test_document_type_echoed_in_response(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        data = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(document_type="PAYSLIP"),
        ).json()
        # Response document_type maps to Document.mime_type (stored as business classification)
        assert data["document_type"] == "PAYSLIP"

    def test_optional_party_id_passed_to_service(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        party_id = str(uuid4())
        client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(party_id=party_id),
        )
        call_kwargs = mock_doc_service.ingest_document.call_args.kwargs
        assert str(call_kwargs["party_id"]) == party_id

    def test_no_party_id_passes_none(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(),
        )
        call_kwargs = mock_doc_service.ingest_document.call_args.kwargs
        assert call_kwargs["party_id"] is None

    def test_content_bytes_passed_to_service(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        content = b"unique file content for test"
        client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(content=content),
        )
        call_kwargs = mock_doc_service.ingest_document.call_args.kwargs
        assert call_kwargs["content"] == content

    def test_filename_passed_to_service(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(filename="bank-statement-jan.pdf"),
        )
        call_kwargs = mock_doc_service.ingest_document.call_args.kwargs
        assert call_kwargs["original_filename"] == "bank-statement-jan.pdf"

    def test_missing_file_returns_422(self, client: TestClient) -> None:
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            data={"document_type": "PAYSLIP"},
        )
        assert response.status_code == 422

    def test_missing_document_type_returns_422(self, client: TestClient) -> None:
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            files={"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")},
        )
        assert response.status_code == 422

    def test_authorization_error_returns_403(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        mock_doc_service.ingest_document.side_effect = AuthorizationError(
            "Permission denied: 'upload:document' is required"
        )
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(),
        )
        assert response.status_code == 403

    def test_validation_error_returns_422(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        mock_doc_service.ingest_document.side_effect = ValidationError(
            "Document content must not be empty."
        )
        response = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(content=b""),
        )
        assert response.status_code == 422

    def test_content_hash_present_in_response(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        data = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(),
        ).json()
        # 64-character SHA-256 hex digest
        assert len(data["content_hash"]) == 64

    def test_evidence_item_count_defaults_to_zero(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.ingest_document.return_value = doc
        data = client.post(
            f"/v1/applications/{TEST_APP_ID}/documents",
            **_multipart(),
        ).json()
        assert data["evidence_item_count"] == 0


# ---------------------------------------------------------------------------
# GET /v1/applications/{id}/documents
# ---------------------------------------------------------------------------


class TestListDocuments:
    def test_returns_200(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        mock_doc_service.list_documents.return_value = []
        response = client.get(f"/v1/applications/{TEST_APP_ID}/documents")
        assert response.status_code == 200

    def test_returns_empty_list(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        mock_doc_service.list_documents.return_value = []
        data = client.get(f"/v1/applications/{TEST_APP_ID}/documents").json()
        assert data == []

    def test_returns_documents(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        docs = [make_document(), make_document()]
        mock_doc_service.list_documents.return_value = docs
        data = client.get(f"/v1/applications/{TEST_APP_ID}/documents").json()
        assert len(data) == 2

    def test_passes_application_id_to_service(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        mock_doc_service.list_documents.return_value = []
        client.get(f"/v1/applications/{TEST_APP_ID}/documents")
        call_kwargs = mock_doc_service.list_documents.call_args.kwargs
        assert str(call_kwargs["application_id"]) == str(TEST_APP_ID)

    def test_authorization_error_returns_403(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        mock_doc_service.list_documents.side_effect = AuthorizationError("Permission denied")
        response = client.get(f"/v1/applications/{TEST_APP_ID}/documents")
        assert response.status_code == 403

    def test_document_fields_present(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        doc = make_document()
        mock_doc_service.list_documents.return_value = [doc]
        data = client.get(f"/v1/applications/{TEST_APP_ID}/documents").json()
        item = data[0]
        assert "id" in item
        assert "document_type" in item
        assert "ingestion_status" in item
        assert "content_hash" in item
        assert "uploaded_at" in item
        assert "uploaded_by" in item


# ---------------------------------------------------------------------------
# GET /v1/applications/{id}/documents/{doc_id}
# ---------------------------------------------------------------------------


class TestGetDocument:
    def test_returns_200(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        doc = make_document()
        mock_doc_service.get_document.return_value = doc
        response = client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}")
        assert response.status_code == 200

    def test_returns_document_fields(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        doc = make_document()
        mock_doc_service.get_document.return_value = doc
        data = client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}").json()
        assert data["id"] == str(doc.id)
        assert data["content_hash"] == doc.content_hash

    def test_not_found_returns_404(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        mock_doc_service.get_document.side_effect = NotFoundError("Document", TEST_DOC_ID)
        response = client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}")
        assert response.status_code == 404

    def test_not_found_error_body_has_code(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        mock_doc_service.get_document.side_effect = NotFoundError("Document", TEST_DOC_ID)
        data = client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}").json()
        assert data["code"] == "NOT_FOUND"

    def test_authorization_error_returns_403(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        mock_doc_service.get_document.side_effect = AuthorizationError("Cross-tenant access denied")
        response = client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}")
        assert response.status_code == 403

    def test_passes_document_id_to_service(
        self, client: TestClient, mock_doc_service: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.get_document.return_value = doc
        client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}")
        call_kwargs = mock_doc_service.get_document.call_args.kwargs
        assert str(call_kwargs["document_id"]) == str(TEST_DOC_ID)


class TestRetryDocument:
    def test_returns_200(
        self, client: TestClient, mock_doc_service: MagicMock, mock_ingestion_trigger: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.retry_ingestion.return_value = doc
        response = client.post(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/retry")
        assert response.status_code == 200

    def test_passes_document_id_to_service(
        self, client: TestClient, mock_doc_service: MagicMock, mock_ingestion_trigger: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.retry_ingestion.return_value = doc
        client.post(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/retry")
        call_kwargs = mock_doc_service.retry_ingestion.call_args.kwargs
        assert str(call_kwargs["document_id"]) == str(TEST_DOC_ID)

    def test_re_triggers_ingestion_workflow(
        self, client: TestClient, mock_doc_service: MagicMock, mock_ingestion_trigger: MagicMock
    ) -> None:
        doc = make_document()
        mock_doc_service.retry_ingestion.return_value = doc
        client.post(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/retry")
        mock_ingestion_trigger.trigger.assert_called_once_with(doc)

    def test_not_found_returns_404(
        self, client: TestClient, mock_doc_service: MagicMock, mock_ingestion_trigger: MagicMock
    ) -> None:
        mock_doc_service.retry_ingestion.side_effect = NotFoundError("Document", TEST_DOC_ID)
        response = client.post(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/retry")
        assert response.status_code == 404

    def test_conflict_when_not_failed_returns_409(
        self, client: TestClient, mock_doc_service: MagicMock, mock_ingestion_trigger: MagicMock
    ) -> None:
        mock_doc_service.retry_ingestion.side_effect = ConflictError(
            "Cannot retry a COMPLETED document"
        )
        response = client.post(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/retry")
        assert response.status_code == 409

    def test_authorization_error_returns_403(
        self, client: TestClient, mock_doc_service: MagicMock, mock_ingestion_trigger: MagicMock
    ) -> None:
        mock_doc_service.retry_ingestion.side_effect = AuthorizationError("Permission denied")
        response = client.post(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/retry")
        assert response.status_code == 403


class TestGetDocumentContent:
    def test_returns_200_with_pdf_bytes(
        self,
        client: TestClient,
        mock_doc_service: MagicMock,
        mock_storage_provider: MagicMock,
    ) -> None:
        doc = make_document()
        mock_doc_service.get_document.return_value = doc
        mock_storage_provider.retrieve.return_value = b"%PDF-1.4 fake pdf bytes"
        response = client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/content")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == b"%PDF-1.4 fake pdf bytes"

    def test_retrieves_by_storage_reference(
        self,
        client: TestClient,
        mock_doc_service: MagicMock,
        mock_storage_provider: MagicMock,
    ) -> None:
        doc = make_document()
        mock_doc_service.get_document.return_value = doc
        mock_storage_provider.retrieve.return_value = b"bytes"
        client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/content")
        mock_storage_provider.retrieve.assert_called_once_with(doc.storage_reference)

    def test_not_found_returns_404(self, client: TestClient, mock_doc_service: MagicMock) -> None:
        mock_doc_service.get_document.side_effect = NotFoundError("Document", TEST_DOC_ID)
        response = client.get(f"/v1/applications/{TEST_APP_ID}/documents/{TEST_DOC_ID}/content")
        assert response.status_code == 404
