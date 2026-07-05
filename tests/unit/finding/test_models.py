"""Unit tests for mil.finding.models — Finding."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from mil.finding.models import Finding
from mil.kernel.errors import ExplainabilityError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(**overrides: object) -> Finding:
    kwargs: dict[str, object] = {
        "application_id": uuid4(),
        "tenant_id": uuid4(),
        "workflow_run_id": uuid4(),
        "finding_type": "AI_GENERATED_ASSESSMENT",
        "title": "AI-Generated Finding: AI_GENERATED_ASSESSMENT",
        "rationale": "Evidence is consistent with the declared income.",
        "evidence_summary": "gross_monthly_income=5000.00",
        "confidence_label": "HIGH",
        "recommended_action": "Review the cited evidence.",
        "confidence_score": Decimal("0.900"),
        "model_version": "mock-inference-1.0.0",
        "prompt_version": "finding-generation-prompt-v1",
        "extraction_version": "mock-extraction-1.0.0",
        "evidence_item_ids": [uuid4()],
        "generated_at": datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
    }
    kwargs.update(overrides)
    return Finding.create(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestCreate:
    def test_records_finding_type(self) -> None:
        finding = _make_finding(finding_type="CUSTOM_TYPE")
        assert finding.finding_type == "CUSTOM_TYPE"

    def test_defaults_lifecycle_state_to_extracted(self) -> None:
        assert _make_finding().lifecycle_state == "EXTRACTED"

    def test_records_all_five_explainability_fields(self) -> None:
        finding = _make_finding(
            title="T",
            rationale="R",
            evidence_summary="ES",
            confidence_label="HIGH",
            recommended_action="RA",
        )
        assert finding.title == "T"
        assert finding.rationale == "R"
        assert finding.evidence_summary == "ES"
        assert finding.confidence_label == "HIGH"
        assert finding.recommended_action == "RA"

    def test_records_confidence_score(self) -> None:
        finding = _make_finding(confidence_score=Decimal("0.750"))
        assert finding.confidence_score == Decimal("0.750")

    def test_records_attribution_fields(self) -> None:
        finding = _make_finding(model_version="m2", prompt_version="p2", extraction_version="e2")
        assert finding.model_version == "m2"
        assert finding.prompt_version == "p2"
        assert finding.extraction_version == "e2"

    def test_serialises_evidence_item_ids_as_strings(self) -> None:
        eid = uuid4()
        finding = _make_finding(evidence_item_ids=[eid])
        assert finding.evidence_item_ids == [str(eid)]

    def test_records_multiple_evidence_item_ids(self) -> None:
        ids = [uuid4(), uuid4(), uuid4()]
        finding = _make_finding(evidence_item_ids=ids)
        assert finding.evidence_item_ids == [str(i) for i in ids]

    def test_records_generated_at(self) -> None:
        ts = datetime(2026, 6, 1, 9, 30, tzinfo=UTC)
        finding = _make_finding(generated_at=ts)
        assert finding.generated_at == ts

    def test_defaults_generated_at_when_not_supplied(self) -> None:
        finding = _make_finding(generated_at=None)
        assert finding.generated_at is not None

    def test_sets_created_at(self) -> None:
        assert _make_finding().created_at is not None

    def test_links_application_tenant_and_run(self) -> None:
        app_id, tenant_id, run_id = uuid4(), uuid4(), uuid4()
        finding = _make_finding(application_id=app_id, tenant_id=tenant_id, workflow_run_id=run_id)
        assert finding.application_id == app_id
        assert finding.tenant_id == tenant_id
        assert finding.workflow_run_id == run_id


# ---------------------------------------------------------------------------
# Explainability enforcement (Principle I / III)
# ---------------------------------------------------------------------------


class TestExplainabilityEnforcement:
    @pytest.mark.parametrize(
        "field",
        ["title", "rationale", "evidence_summary", "confidence_label", "recommended_action"],
    )
    def test_empty_explainability_field_raises(self, field: str) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(**{field: ""})

    @pytest.mark.parametrize(
        "field",
        ["title", "rationale", "evidence_summary", "confidence_label", "recommended_action"],
    )
    def test_whitespace_only_explainability_field_raises(self, field: str) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(**{field: "   "})

    def test_empty_model_version_raises(self) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(model_version="")

    def test_empty_prompt_version_raises(self) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(prompt_version="")

    def test_empty_extraction_version_raises(self) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(extraction_version="")

    def test_no_supporting_evidence_raises(self) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(evidence_item_ids=[])

    def test_confidence_score_above_range_raises(self) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(confidence_score=Decimal("1.001"))

    def test_confidence_score_below_range_raises(self) -> None:
        with pytest.raises(ExplainabilityError):
            _make_finding(confidence_score=Decimal("-0.001"))

    def test_confidence_score_boundary_values_accepted(self) -> None:
        assert _make_finding(confidence_score=Decimal("0.000")).confidence_score == Decimal("0.000")
        assert _make_finding(confidence_score=Decimal("1.000")).confidence_score == Decimal("1.000")


# ---------------------------------------------------------------------------
# ORM metadata
# ---------------------------------------------------------------------------


class TestOrmMetadata:
    def test_table_in_finding_schema(self) -> None:
        assert Finding.__table__.schema == "finding"

    def test_unique_constraint_on_application_model_version(self) -> None:
        names = {c.name for c in Finding.__table__.constraints}
        assert "uq_findings_application_model_version" in names
