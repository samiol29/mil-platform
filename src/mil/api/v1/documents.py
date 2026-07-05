"""
Document REST endpoints — MIL API v1.

Endpoints:
    POST /v1/applications/{application_id}/documents
        Upload a document associated with an application.
    GET  /v1/applications/{application_id}/documents
        List all documents for an application.
    GET  /v1/applications/{application_id}/documents/{document_id}
        Retrieve document metadata.

Upload notes:
    The endpoint accepts ``multipart/form-data`` with:
        ``file``          — binary file upload
        ``document_type`` — business classification (BANK_STATEMENT, PAYSLIP, …)
        ``party_id``      — optional UUID of the party this document belongs to

    In Sprint 3D, ``document_type`` is stored as ``mime_type`` on the domain
    model (the ``Document`` entity does not yet have a dedicated
    ``document_type`` column).  The ``DocumentResponse.document_type`` field
    reflects the stored value.  A future sprint will add a dedicated column and
    separate storage of the IANA MIME type (from ``UploadFile.content_type``).

    Documents are immutable once uploaded — see ADR-006.

Route handlers must contain no business logic.  All decisions are delegated
to ``DocumentService``.

Dependency rule: imports from ``mil.api.deps``, ``mil.api.v1.schemas``,
``mil.kernel.types``, FastAPI, and the Python standard library only.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile, status

from mil.api.deps import CurrentUser, DocIngestionTriggerDep, DocService, SettingsDep  # noqa: TC001
from mil.api.v1.schemas import DocumentResponse
from mil.kernel.types import ApplicationId

router = APIRouter(
    prefix="/v1/applications/{application_id}/documents",
    tags=["Documents"],
)

# Read the upload in bounded chunks so an oversized (or hostile) body is
# rejected before the whole file is buffered in memory.
_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_upload_within_limit(file: UploadFile, max_bytes: int) -> bytes:
    """
    Read ``file`` fully, rejecting it once it exceeds ``max_bytes``.

    Returns the file bytes. Raises ``HTTPException(413)`` as soon as the
    accumulated size exceeds the configured maximum, so memory use is bounded
    to roughly ``max_bytes`` regardless of the declared or actual body size
    (Backend Freeze Patch v1.0 — upload safety).
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,  # Content Too Large
                detail={
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": (
                        f"Uploaded file exceeds the maximum allowed size of {max_bytes} bytes."
                    ),
                },
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "",
    summary="Upload a document to an application",
    description=(
        "Upload a source document for a mortgage application. "
        "The file is stored in durable content-addressed storage. "
        "A SHA-256 integrity hash is computed from the raw bytes and stored "
        "immutably with the document record (see ADR-006). "
        "The document is returned with ``ingestion_status=PENDING``, "
        "indicating that the Intelligence Pipeline (US2) has not yet "
        "processed it. "
        "Optionally associate the document with a specific ``party_id``. "
        "Documents are immutable after this call completes. "
        "Requires ``upload:document`` permission."
    ),
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        413: {"description": "Uploaded file exceeds the maximum allowed size"},
        422: {"description": "Empty file or missing document_type"},
    },
)
async def upload_document(
    application_id: UUID,
    user: CurrentUser,
    service: DocService,
    settings: SettingsDep,
    ingestion_trigger: DocIngestionTriggerDep,
    file: UploadFile,
    document_type: str = Form(
        description=(
            "Business document classification. "
            "Examples: BANK_STATEMENT, PAYSLIP, VALUATION_REPORT, IDENTITY_DOCUMENT."
        )
    ),
    party_id: UUID | None = Form(
        default=None,
        description="Optional party this document belongs to.",
    ),
) -> DocumentResponse:
    """Accept a file upload, ingest it, and start the document intelligence pipeline."""
    content = await _read_upload_within_limit(file, settings.mil_max_upload_bytes)
    original_filename = file.filename or "unknown"

    doc = service.ingest_document(
        user,
        application_id=ApplicationId(application_id),
        content=content,
        original_filename=original_filename,
        # Sprint 3D: document_type (business classification) stored as mime_type.
        # A dedicated document_type column will be added in a future sprint migration.
        mime_type=document_type,
        party_id=party_id,
    )
    # Start the DOCUMENT_INGESTION workflow (OCR -> Extraction) in the same
    # transaction as the upload — without this, a document is stored but the
    # intelligence pipeline never runs and it remains PENDING forever.
    ingestion_trigger.trigger(doc)
    return DocumentResponse.from_model(doc)


@router.get(
    "",
    summary="List documents for an application",
    description=(
        "Return all documents associated with a mortgage application, most "
        "recent first. "
        "Optional query parameters ``party_id``, ``document_type``, and "
        "``ingestion_status`` are accepted for forward compatibility "
        "but filtering is not applied in Sprint 3D "
        "(the full query layer is deferred to US2). "
        "Requires ``read:document`` permission."
    ),
    response_model=list[DocumentResponse],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Application not found"},
    },
)
def list_documents(
    application_id: UUID,
    user: CurrentUser,
    service: DocService,
    party_id: UUID | None = Query(default=None),
    document_type: str | None = Query(default=None),
    ingestion_status: str | None = Query(default=None),
) -> list[DocumentResponse]:
    """Return all documents for the application."""
    docs = service.list_documents(user, application_id=ApplicationId(application_id))
    return [DocumentResponse.from_model(d) for d in docs]


@router.get(
    "/{document_id}",
    summary="Get document metadata",
    description=(
        "Retrieve metadata for a specific document by its MIL identifier. "
        "Document content (bytes) is not returned — use the Storage API or "
        "a signed URL (US2) to retrieve the actual file. "
        "Requires ``read:document`` permission."
    ),
    response_model=DocumentResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Document not found"},
    },
)
def get_document(
    application_id: UUID,
    document_id: UUID,
    user: CurrentUser,
    service: DocService,
) -> DocumentResponse:
    """Retrieve document metadata by document ID."""
    doc = service.get_document(user, document_id=document_id)
    return DocumentResponse.from_model(doc)
