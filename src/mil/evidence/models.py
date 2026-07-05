"""
ORM model for persisted Evidence output (Evidence Management bounded context).

``EvidenceItem`` is the durable, immutable record of a single fact extracted
from a document. It is created once by the Extraction pipeline and never
updated or deleted (append-only, mirroring the immutability discipline
already applied to ``OCRResultRecord`` in ``mil.document.ocr_models``).

Provenance (Engineering Constitution Principle II — Evidence First / Principle
XII — Deterministic Intelligence): every ``EvidenceItem`` carries all seven
provenance attributes required of an ``EvidenceAttributes`` object — source
document, page number, field location, extraction confidence, extraction
method, timestamp, and extraction (model/engine) version. ``EvidenceItem.create``
refuses to construct a row unless every attribute is present, so an incomplete
fact can never reach the database.

Determinism / idempotency (ADR-008): a fact is identified by the document it
came from, the extraction engine version that produced it, and the field it
represents — ``(document_id, extraction_model_version, evidence_type)`` is
unique. Re-running extraction for the same document under the same extraction
version cannot produce a duplicate row for the same fact.

Schema: ``evidence`` PostgreSQL schema.

Note: ``policy_pack_id`` (present in the target data model at
``specs/001-mil-platform-spec/data-model.md``) is intentionally omitted from
this sprint. The Policy Pack bounded context does not exist yet (it is
US2 Sprint 5+, tasks T062-T066), and Evidence Sprint 3 must never evaluate or
reference Policy. A later Policy Pack migration adds that column.

Dependency rule: imports only from ``mil.kernel`` and the Python standard
library.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mil.kernel.db import Base
from mil.kernel.errors import ProvenanceError

if TYPE_CHECKING:
    from mil.kernel.providers.extraction import EvidenceAttributes, FieldLocation


def _serialise_field_location(location: FieldLocation | None) -> dict[str, object] | None:
    """Serialise a ``FieldLocation`` value object into a JSON-safe dict."""
    if location is None:
        return None
    return {
        "page_number": location.page_number,
        "field_name": location.field_name,
        "bounding_box": list(location.bounding_box) if location.bounding_box is not None else None,
    }


def _try_parse_numeric(field_value: str) -> Decimal | None:
    """Return ``field_value`` parsed as a ``Decimal``, or ``None`` if not numeric."""
    try:
        return Decimal(field_value)
    except (InvalidOperation, ValueError):
        return None


def _confidence_to_decimal(confidence: float) -> Decimal:
    """Round an extraction confidence float to the 3-decimal-place storage precision."""
    return Decimal(str(round(confidence, 3)))


class EvidenceItem(Base):
    """
    Immutable persisted fact extracted from a single document.

    Created once by the Extraction worker and never updated. References the
    source document (custody record), the application it pertains to, and the
    workflow run that produced it (lineage), and carries all seven Principle II
    provenance attributes.
    """

    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "extraction_model_version",
            "evidence_type",
            name="uq_evidence_items_document_version_type",
        ),
        {"schema": "evidence"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("core.applications.id"), nullable=False)
    party_id: Mapped[UUID | None] = mapped_column(ForeignKey("core.parties.id"), nullable=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("core.documents.id"), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("orchestrator.workflow_runs.id"), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    # Machine-readable fact identifier (e.g. "gross_monthly_income"). Sourced
    # from EvidenceAttributes.field_name.
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # Provenance attribute 2: page number.
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Provenance attribute 3: field location (None when not determinable).
    field_location: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    # Provenance attribute 4: extraction confidence.
    extraction_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    # Provenance attribute 5: extraction method.
    extraction_method: Mapped[str] = mapped_column(String(100), nullable=False)
    # Provenance attribute 7: originating extraction engine version.
    extraction_model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    # Provenance attribute 6: timestamp.
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evidence.evidence_items.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        document_id: UUID,
        workflow_run_id: UUID,
        tenant_id: UUID,
        attrs: EvidenceAttributes,
        party_id: UUID | None = None,
    ) -> EvidenceItem:
        """
        Build an immutable evidence item from a provider ``EvidenceAttributes``.

        Raises:
            ProvenanceError: If ``attrs`` is missing any of the seven required
                provenance attributes (Principle II). An incomplete fact can
                never be constructed, let alone persisted.
        """
        if not attrs.provenance_complete():
            raise ProvenanceError(
                f"EvidenceAttributes for field {attrs.field_name!r} is missing required "
                "provenance attributes; refusing to create EvidenceItem",
                details={"field_name": attrs.field_name, "document_id": str(document_id)},
            )
        return cls(
            id=uuid4(),
            application_id=application_id,
            party_id=party_id,
            document_id=document_id,
            workflow_run_id=workflow_run_id,
            tenant_id=tenant_id,
            evidence_type=attrs.field_name,
            value_text=attrs.field_value,
            value_numeric=_try_parse_numeric(attrs.field_value),
            currency=None,
            page_number=attrs.page_number,
            field_location=_serialise_field_location(attrs.field_location),
            extraction_confidence=_confidence_to_decimal(attrs.extraction_confidence),
            extraction_method=attrs.extraction_method,
            extraction_model_version=attrs.extraction_version,
            extracted_at=attrs.extracted_at,
            supersedes_id=None,
            created_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return (
            f"<EvidenceItem id={self.id} document={self.document_id} "
            f"type={self.evidence_type} version={self.extraction_model_version}>"
        )
