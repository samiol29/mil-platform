"""Unit tests for mil.evidence.service — EvidenceService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from mil.evidence.service import EvidenceService
from mil.kernel.providers.extraction import EvidenceAttributes, FieldLocation

if TYPE_CHECKING:
    from mil.evidence.models import EvidenceItem


def _attrs(field_name: str = "gross_monthly_income", **overrides: object) -> EvidenceAttributes:
    defaults: dict[str, object] = {
        "field_name": field_name,
        "field_value": "5000.00",
        "document_id": "doc-1",
        "source_document_ref": "ref-1",
        "page_number": 1,
        "field_location": FieldLocation(page_number=1, field_name=field_name),
        "extraction_confidence": 0.85,
        "extraction_method": "mock-keyword-matcher",
        "extracted_at": datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        "extraction_version": "mock-extraction-1.0.0",
    }
    defaults.update(overrides)
    return EvidenceAttributes(**defaults)  # type: ignore[arg-type]


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.saved: list[EvidenceItem] = []

    def save(self, item: EvidenceItem) -> None:
        self.saved.append(item)


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[EvidenceService, FakeEvidenceRepository, FakeAuditWriter]:
    repo = FakeEvidenceRepository()
    audit = FakeAuditWriter()
    return EvidenceService(repo, audit), repo, audit  # type: ignore[arg-type]


class TestCreateEvidenceItems:
    def test_creates_one_item_per_attrs(self) -> None:
        service, repo, _ = _make_service()
        created = service.create_evidence_items(
            application_id=uuid4(),
            document_id=uuid4(),
            workflow_run_id=uuid4(),
            tenant_id=uuid4(),
            attrs_list=[_attrs("gross_monthly_income"), _attrs("net_monthly_income")],
        )
        assert len(created) == 2
        assert len(repo.saved) == 2

    def test_empty_attrs_list_creates_nothing(self) -> None:
        service, repo, audit = _make_service()
        created = service.create_evidence_items(
            application_id=uuid4(),
            document_id=uuid4(),
            workflow_run_id=uuid4(),
            tenant_id=uuid4(),
            attrs_list=[],
        )
        assert created == []
        assert repo.saved == []
        assert audit.records == []

    def test_emits_evidence_created_audit_event_per_item(self) -> None:
        service, _, audit = _make_service()
        service.create_evidence_items(
            application_id=uuid4(),
            document_id=uuid4(),
            workflow_run_id=uuid4(),
            tenant_id=uuid4(),
            attrs_list=[_attrs("gross_monthly_income"), _attrs("net_monthly_income")],
        )
        assert len(audit.records) == 2
        assert all(r["event_type"] == "EVIDENCE_CREATED" for r in audit.records)
        assert all(r["entity_type"] == "EVIDENCE_ITEM" for r in audit.records)

    def test_audit_event_carries_tenant_and_application(self) -> None:
        service, _, audit = _make_service()
        app_id, tenant_id = uuid4(), uuid4()
        service.create_evidence_items(
            application_id=app_id,
            document_id=uuid4(),
            workflow_run_id=uuid4(),
            tenant_id=tenant_id,
            attrs_list=[_attrs()],
        )
        record = audit.records[0]
        assert record["tenant_id"] == tenant_id
        assert record["application_id"] == app_id

    def test_links_items_to_document_and_application(self) -> None:
        service, repo, _ = _make_service()
        app_id, doc_id = uuid4(), uuid4()
        service.create_evidence_items(
            application_id=app_id,
            document_id=doc_id,
            workflow_run_id=uuid4(),
            tenant_id=uuid4(),
            attrs_list=[_attrs()],
        )
        item = repo.saved[0]
        assert item.application_id == app_id
        assert item.document_id == doc_id

    def test_party_id_propagated_when_supplied(self) -> None:
        service, repo, _ = _make_service()
        party_id = uuid4()
        service.create_evidence_items(
            application_id=uuid4(),
            document_id=uuid4(),
            workflow_run_id=uuid4(),
            tenant_id=uuid4(),
            attrs_list=[_attrs()],
            party_id=party_id,
        )
        assert repo.saved[0].party_id == party_id
