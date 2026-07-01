"""Unit tests for mil.evidence.models — EvidenceItem."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from mil.evidence.models import EvidenceItem
from mil.kernel.errors import ProvenanceError
from mil.kernel.providers.extraction import EvidenceAttributes, FieldLocation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attrs(**overrides: object) -> EvidenceAttributes:
    defaults: dict[str, object] = {
        "field_name": "gross_monthly_income",
        "field_value": "5000.00",
        "document_id": "doc-1",
        "source_document_ref": "ref-1",
        "page_number": 1,
        "field_location": FieldLocation(
            page_number=1, field_name="gross_monthly_income", bounding_box=(0.1, 0.1, 0.5, 0.05)
        ),
        "extraction_confidence": 0.85,
        "extraction_method": "mock-keyword-matcher",
        "extracted_at": datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        "extraction_version": "mock-extraction-1.0.0",
    }
    defaults.update(overrides)
    return EvidenceAttributes(**defaults)  # type: ignore[arg-type]


def _make_item(**overrides: object) -> EvidenceItem:
    kwargs: dict[str, object] = {
        "application_id": uuid4(),
        "document_id": uuid4(),
        "workflow_run_id": uuid4(),
        "tenant_id": uuid4(),
        "attrs": _attrs(),
    }
    kwargs.update(overrides)
    return EvidenceItem.create(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestCreate:
    def test_records_evidence_type_from_field_name(self) -> None:
        item = _make_item(attrs=_attrs(field_name="net_monthly_income"))
        assert item.evidence_type == "net_monthly_income"

    def test_records_value_text_from_field_value(self) -> None:
        item = _make_item(attrs=_attrs(field_value="4200.50"))
        assert item.value_text == "4200.50"

    def test_parses_numeric_value_when_possible(self) -> None:
        item = _make_item(attrs=_attrs(field_value="4200.50"))
        assert item.value_numeric == Decimal("4200.50")

    def test_value_numeric_none_when_not_numeric(self) -> None:
        item = _make_item(attrs=_attrs(field_value="Acme Corp"))
        assert item.value_numeric is None

    def test_records_page_number(self) -> None:
        item = _make_item(attrs=_attrs(page_number=3))
        assert item.page_number == 3

    def test_serialises_field_location(self) -> None:
        item = _make_item()
        assert item.field_location is not None
        assert item.field_location["field_name"] == "gross_monthly_income"
        assert item.field_location["bounding_box"] == [0.1, 0.1, 0.5, 0.05]

    def test_field_location_none_when_not_determinable(self) -> None:
        item = _make_item(attrs=_attrs(field_location=None))
        assert item.field_location is None

    def test_records_extraction_confidence(self) -> None:
        item = _make_item(attrs=_attrs(extraction_confidence=0.923))
        assert item.extraction_confidence == Decimal("0.923")

    def test_records_extraction_method(self) -> None:
        item = _make_item()
        assert item.extraction_method == "mock-keyword-matcher"

    def test_records_extraction_model_version(self) -> None:
        item = _make_item(attrs=_attrs(extraction_version="azure-extract-2.0"))
        assert item.extraction_model_version == "azure-extract-2.0"

    def test_records_extracted_at(self) -> None:
        ts = datetime(2026, 6, 1, 9, 30, tzinfo=UTC)
        item = _make_item(attrs=_attrs(extracted_at=ts))
        assert item.extracted_at == ts

    def test_supersedes_id_defaults_to_none(self) -> None:
        assert _make_item().supersedes_id is None

    def test_currency_defaults_to_none(self) -> None:
        assert _make_item().currency is None

    def test_party_id_defaults_to_none(self) -> None:
        assert _make_item().party_id is None

    def test_party_id_can_be_set(self) -> None:
        party_id = uuid4()
        item = _make_item(party_id=party_id)
        assert item.party_id == party_id

    def test_sets_created_at(self) -> None:
        assert _make_item().created_at is not None

    def test_links_application_document_run_tenant(self) -> None:
        app_id, doc_id, run_id, tenant_id = uuid4(), uuid4(), uuid4(), uuid4()
        item = _make_item(
            application_id=app_id, document_id=doc_id, workflow_run_id=run_id, tenant_id=tenant_id
        )
        assert item.application_id == app_id
        assert item.document_id == doc_id
        assert item.workflow_run_id == run_id
        assert item.tenant_id == tenant_id


# ---------------------------------------------------------------------------
# Provenance enforcement (Principle II / Principle XII)
# ---------------------------------------------------------------------------


class TestProvenanceEnforcement:
    def test_missing_extraction_method_raises(self) -> None:
        with pytest.raises(ValueError, match="extraction_method"):
            _attrs(extraction_method="")

    def test_missing_extraction_version_raises(self) -> None:
        with pytest.raises(ValueError, match="extraction_version"):
            _attrs(extraction_version="")

    def test_out_of_range_confidence_raises(self) -> None:
        with pytest.raises(ValueError, match="extraction_confidence"):
            _attrs(extraction_confidence=1.5)

    def test_naive_timestamp_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _attrs(extracted_at=datetime(2026, 7, 1, 12, 0))

    def test_provenance_incomplete_attrs_raises_provenance_error(self) -> None:
        """
        EvidenceItem.create refuses to construct a row for an
        EvidenceAttributes-shaped object whose provenance_complete() reports
        incomplete — the guard is checked directly, not re-derived from
        EvidenceAttributes's own __post_init__ (which already forbids
        constructing such an object through the public dataclass API).
        """

        class _IncompleteAttrs:
            field_name = "gross_monthly_income"
            field_value = "5000.00"
            document_id = "doc-1"
            source_document_ref = "ref-1"
            page_number = 1
            field_location = None
            extraction_confidence = 0.85
            extraction_method = "mock-keyword-matcher"
            extracted_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
            extraction_version = "mock-extraction-1.0.0"

            def provenance_complete(self) -> bool:
                return False

        with pytest.raises(ProvenanceError):
            EvidenceItem.create(
                application_id=uuid4(),
                document_id=uuid4(),
                workflow_run_id=uuid4(),
                tenant_id=uuid4(),
                attrs=_IncompleteAttrs(),  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# ORM metadata
# ---------------------------------------------------------------------------


class TestOrmMetadata:
    def test_table_in_evidence_schema(self) -> None:
        assert EvidenceItem.__table__.schema == "evidence"

    def test_unique_constraint_on_document_version_type(self) -> None:
        names = {c.name for c in EvidenceItem.__table__.constraints}
        assert "uq_evidence_items_document_version_type" in names
