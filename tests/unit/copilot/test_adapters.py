"""
Unit tests for mil.copilot.adapters — the Query Port adapters (ADR-010).

Each adapter is tested against a small fake repository exposing only the
methods the corresponding producing-context repository actually has, and
fake "ORM-row" objects carrying only the attributes the adapter reads. No
database is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from mil.copilot.adapters import (
    ApplicationReaderAdapter,
    DocumentReaderAdapter,
    EvidenceReaderAdapter,
    FindingReaderAdapter,
    PolicyResultReaderAdapter,
    ReviewReaderAdapter,
)

_NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Fake ORM rows (only the attributes each adapter reads)
# ---------------------------------------------------------------------------


@dataclass
class _FakeApplication:
    id: object = field(default_factory=uuid4)
    tenant_id: object = field(default_factory=uuid4)
    status: str = "SUBMITTED"
    created_at: datetime = _NOW


@dataclass
class _FakeDocument:
    id: object = field(default_factory=uuid4)
    application_id: object = field(default_factory=uuid4)
    mime_type: str = "PAYSLIP"
    original_filename: str = "payslip.pdf"
    ingestion_status: str = "COMPLETED"
    uploaded_at: datetime = _NOW


@dataclass
class _FakeEvidenceItem:
    id: object = field(default_factory=uuid4)
    application_id: object = field(default_factory=uuid4)
    document_id: object = field(default_factory=uuid4)
    evidence_type: str = "GROSS_MONTHLY_INCOME"
    value_text: str | None = "5000.00"
    extraction_confidence: Decimal = Decimal("0.900")
    page_number: int | None = 1
    field_location: dict[str, object] | None = None
    extraction_method: str = "mock"
    extraction_model_version: str = "mock-extraction-1.0.0"
    extracted_at: datetime = _NOW


@dataclass
class _FakeFinding:
    id: object = field(default_factory=uuid4)
    application_id: object = field(default_factory=uuid4)
    finding_type: str = "INCOME_VERIFICATION"
    title: str = "Income mismatch"
    rationale: str = "Declared income does not match payslip."
    evidence_summary: str = "payslip=5000; declared=6000"
    confidence_label: str = "MEDIUM"
    recommended_action: str = "Verify with employer."
    model_version: str = "mock-inference-1.0.0"
    prompt_version: str = "explain-finding-v1"
    extraction_version: str = "mock-extraction-1.0.0"
    created_at: datetime = _NOW


@dataclass
class _FakePolicyResult:
    id: object = field(default_factory=uuid4)
    finding_id: object = field(default_factory=uuid4)
    policy_version: str = "policy-v1"
    outcome: str = "PASS"
    triggered_rule_keys: list[str] = field(default_factory=list)
    evaluated_at: datetime = _NOW


@dataclass
class _FakeReviewSession:
    id: object = field(default_factory=uuid4)
    finding_id: object = field(default_factory=uuid4)
    application_id: object = field(default_factory=uuid4)
    status: str = "PENDING_REVIEW"
    assigned_reviewer_id: object | None = None
    created_at: datetime = _NOW
    closed_at: datetime | None = None


@dataclass
class _FakeReviewAction:
    id: object = field(default_factory=uuid4)
    review_session_id: object = field(default_factory=uuid4)
    action_type: str = "APPROVED"
    actor_user_id: object | None = field(default_factory=uuid4)
    actor_type: str = "USER"
    previous_status: str = "IN_REVIEW"
    new_status: str = "APPROVED"
    reason: str | None = None
    previous_value: str | None = None
    new_value: str | None = None
    created_at: datetime = _NOW


@dataclass
class _FakeReviewComment:
    id: object = field(default_factory=uuid4)
    review_session_id: object = field(default_factory=uuid4)
    author_user_id: object = field(default_factory=uuid4)
    comment_text: str = "Looks fine."
    created_at: datetime = _NOW


# ---------------------------------------------------------------------------
# Fake repositories (only the methods each adapter calls)
# ---------------------------------------------------------------------------


class _FakeApplicationRepository:
    def __init__(self, application: _FakeApplication | None) -> None:
        self._application = application

    def get_by_id(self, application_id: object) -> _FakeApplication | None:
        return self._application


class _FakeDocumentRepository:
    def __init__(self, documents: list[_FakeDocument]) -> None:
        self._documents = documents

    def get_for_application(self, application_id: object) -> list[_FakeDocument]:
        return self._documents


class _FakeEvidenceRepository:
    def __init__(self, items: list[_FakeEvidenceItem]) -> None:
        self._items = items

    def get_for_application(self, application_id: object) -> list[_FakeEvidenceItem]:
        return self._items


class _FakeFindingRepository:
    def __init__(self, findings: list[_FakeFinding]) -> None:
        self._findings = findings

    def get_for_application(self, application_id: object) -> list[_FakeFinding]:
        return self._findings

    def get_by_id(self, finding_id: object) -> _FakeFinding | None:
        return next((f for f in self._findings if f.id == finding_id), None)


class _FakePolicyRepository:
    def __init__(self, results: list[_FakePolicyResult]) -> None:
        self._results = results

    def get_for_finding(self, finding_id: object) -> list[_FakePolicyResult]:
        return self._results


class _FakeReviewRepository:
    def __init__(
        self,
        session: _FakeReviewSession | None = None,
        actions: list[_FakeReviewAction] | None = None,
        comments: list[_FakeReviewComment] | None = None,
    ) -> None:
        self._session = session
        self._actions = actions or []
        self._comments = comments or []

    def get_session_for_finding(self, finding_id: object) -> _FakeReviewSession | None:
        return self._session

    def get_actions_for_session(self, review_session_id: object) -> list[_FakeReviewAction]:
        return self._actions

    def get_comments_for_session(self, review_session_id: object) -> list[_FakeReviewComment]:
        return self._comments


# ---------------------------------------------------------------------------
# ApplicationReaderAdapter
# ---------------------------------------------------------------------------


class TestApplicationReaderAdapter:
    def test_maps_fields(self) -> None:
        application = _FakeApplication(status="APPROVED")
        adapter = ApplicationReaderAdapter(_FakeApplicationRepository(application))  # type: ignore[arg-type]
        view = adapter.get_by_id(application.id)
        assert view is not None
        assert view.id == application.id
        assert view.tenant_id == application.tenant_id
        assert view.status == "APPROVED"
        assert view.created_at == application.created_at

    def test_returns_none_when_missing(self) -> None:
        adapter = ApplicationReaderAdapter(_FakeApplicationRepository(None))  # type: ignore[arg-type]
        assert adapter.get_by_id(uuid4()) is None


# ---------------------------------------------------------------------------
# DocumentReaderAdapter
# ---------------------------------------------------------------------------


class TestDocumentReaderAdapter:
    def test_maps_mime_type_to_document_type(self) -> None:
        document = _FakeDocument(mime_type="BANK_STATEMENT")
        adapter = DocumentReaderAdapter(_FakeDocumentRepository([document]))  # type: ignore[arg-type]
        views = adapter.get_for_application(document.application_id)
        assert views[0].document_type == "BANK_STATEMENT"

    def test_maps_original_filename_to_filename(self) -> None:
        document = _FakeDocument(original_filename="statement.pdf")
        adapter = DocumentReaderAdapter(_FakeDocumentRepository([document]))  # type: ignore[arg-type]
        views = adapter.get_for_application(document.application_id)
        assert views[0].filename == "statement.pdf"

    def test_maps_ingestion_status_to_status(self) -> None:
        document = _FakeDocument(ingestion_status="FAILED")
        adapter = DocumentReaderAdapter(_FakeDocumentRepository([document]))  # type: ignore[arg-type]
        views = adapter.get_for_application(document.application_id)
        assert views[0].status == "FAILED"

    def test_empty_list_when_no_documents(self) -> None:
        adapter = DocumentReaderAdapter(_FakeDocumentRepository([]))  # type: ignore[arg-type]
        assert adapter.get_for_application(uuid4()) == ()


# ---------------------------------------------------------------------------
# EvidenceReaderAdapter
# ---------------------------------------------------------------------------


class TestEvidenceReaderAdapter:
    def test_confidence_is_derived_from_decimal(self) -> None:
        item = _FakeEvidenceItem(extraction_confidence=Decimal("0.850"))
        adapter = EvidenceReaderAdapter(_FakeEvidenceRepository([item]))  # type: ignore[arg-type]
        view = adapter.get_for_application(item.application_id)[0]
        assert view.confidence == 0.85
        assert isinstance(view.confidence, float)

    def test_null_value_text_becomes_empty_string(self) -> None:
        item = _FakeEvidenceItem(value_text=None)
        adapter = EvidenceReaderAdapter(_FakeEvidenceRepository([item]))  # type: ignore[arg-type]
        view = adapter.get_for_application(item.application_id)[0]
        assert view.value_text == ""

    def test_field_location_reduced_to_field_name(self) -> None:
        item = _FakeEvidenceItem(
            field_location={"page_number": 1, "field_name": "gross_income", "bounding_box": None}
        )
        adapter = EvidenceReaderAdapter(_FakeEvidenceRepository([item]))  # type: ignore[arg-type]
        view = adapter.get_for_application(item.application_id)[0]
        assert view.field_location == "gross_income"

    def test_null_field_location_stays_none(self) -> None:
        item = _FakeEvidenceItem(field_location=None)
        adapter = EvidenceReaderAdapter(_FakeEvidenceRepository([item]))  # type: ignore[arg-type]
        view = adapter.get_for_application(item.application_id)[0]
        assert view.field_location is None

    def test_null_page_number_defaults_to_zero(self) -> None:
        item = _FakeEvidenceItem(page_number=None)
        adapter = EvidenceReaderAdapter(_FakeEvidenceRepository([item]))  # type: ignore[arg-type]
        view = adapter.get_for_application(item.application_id)[0]
        assert view.page_number == 0


# ---------------------------------------------------------------------------
# FindingReaderAdapter
# ---------------------------------------------------------------------------


class TestFindingReaderAdapter:
    def test_maps_explainability_fields_by_name(self) -> None:
        finding = _FakeFinding(title="Custom title", rationale="Custom rationale")
        adapter = FindingReaderAdapter(_FakeFindingRepository([finding]))  # type: ignore[arg-type]
        view = adapter.get_for_application(finding.application_id)[0]
        assert view.title == "Custom title"
        assert view.rationale == "Custom rationale"

    def test_get_by_id_returns_matching_view(self) -> None:
        finding = _FakeFinding()
        adapter = FindingReaderAdapter(_FakeFindingRepository([finding]))  # type: ignore[arg-type]
        view = adapter.get_by_id(finding.id)
        assert view is not None
        assert view.id == finding.id

    def test_get_by_id_returns_none_when_missing(self) -> None:
        adapter = FindingReaderAdapter(_FakeFindingRepository([]))  # type: ignore[arg-type]
        assert adapter.get_by_id(uuid4()) is None


# ---------------------------------------------------------------------------
# PolicyResultReaderAdapter
# ---------------------------------------------------------------------------


class TestPolicyResultReaderAdapter:
    def test_maps_outcome_to_status(self) -> None:
        result = _FakePolicyResult(outcome="FAIL")
        adapter = PolicyResultReaderAdapter(_FakePolicyRepository([result]))  # type: ignore[arg-type]
        view = adapter.get_for_finding(result.finding_id)[0]
        assert view.status == "FAIL"

    def test_synthesizes_rule_ref_from_triggered_rule_keys(self) -> None:
        result = _FakePolicyResult(triggered_rule_keys=["RULE-001", "RULE-002"])
        adapter = PolicyResultReaderAdapter(_FakePolicyRepository([result]))  # type: ignore[arg-type]
        view = adapter.get_for_finding(result.finding_id)[0]
        assert view.rule_ref == "RULE-001, RULE-002"

    def test_synthesizes_rationale_including_outcome_and_rules(self) -> None:
        result = _FakePolicyResult(outcome="FAIL", triggered_rule_keys=["RULE-001"])
        adapter = PolicyResultReaderAdapter(_FakePolicyRepository([result]))  # type: ignore[arg-type]
        view = adapter.get_for_finding(result.finding_id)[0]
        assert "FAIL" in view.rationale
        assert "RULE-001" in view.rationale

    def test_no_triggered_rules_uses_sentinel(self) -> None:
        result = _FakePolicyResult(triggered_rule_keys=[])
        adapter = PolicyResultReaderAdapter(_FakePolicyRepository([result]))  # type: ignore[arg-type]
        view = adapter.get_for_finding(result.finding_id)[0]
        assert view.rule_ref == "N/A"
        assert "no rules triggered" in view.rationale


# ---------------------------------------------------------------------------
# ReviewReaderAdapter
# ---------------------------------------------------------------------------


class TestReviewReaderAdapter:
    def test_get_session_for_finding_maps_fields(self) -> None:
        session = _FakeReviewSession(status="APPROVED")
        adapter = ReviewReaderAdapter(_FakeReviewRepository(session=session))  # type: ignore[arg-type]
        view = adapter.get_session_for_finding(session.finding_id)
        assert view is not None
        assert view.status == "APPROVED"

    def test_get_session_for_finding_returns_none_when_absent(self) -> None:
        adapter = ReviewReaderAdapter(_FakeReviewRepository(session=None))  # type: ignore[arg-type]
        assert adapter.get_session_for_finding(uuid4()) is None

    def test_get_actions_for_session_maps_all_fields(self) -> None:
        action = _FakeReviewAction(action_type="OVERRIDDEN", reason="Data entry error")
        adapter = ReviewReaderAdapter(_FakeReviewRepository(actions=[action]))  # type: ignore[arg-type]
        views = adapter.get_actions_for_session(action.review_session_id)
        assert views[0].action_type == "OVERRIDDEN"
        assert views[0].reason == "Data entry error"

    def test_get_comments_for_session_maps_fields(self) -> None:
        comment = _FakeReviewComment(comment_text="Please verify.")
        adapter = ReviewReaderAdapter(_FakeReviewRepository(comments=[comment]))  # type: ignore[arg-type]
        views = adapter.get_comments_for_session(comment.review_session_id)
        assert views[0].comment_text == "Please verify."
