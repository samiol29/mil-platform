"""Unit tests for mil.finding.service — FindingService."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from mil.finding.models import Finding
from mil.finding.service import FindingService
from mil.kernel.errors import AuthorizationError
from mil.kernel.providers.inference import InferenceResult
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId


@dataclass
class _FakeEvidenceItem:
    evidence_type: str
    value_text: str
    extraction_confidence: Decimal
    id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    page_number: int = 1


def _evidence_items() -> list[_FakeEvidenceItem]:
    return [
        _FakeEvidenceItem("gross_monthly_income", "5000.00", Decimal("0.850")),
        _FakeEvidenceItem("net_monthly_income", "4200.00", Decimal("0.950")),
    ]


def _inference_result(**overrides: object) -> InferenceResult:
    defaults: dict[str, object] = {
        "content": "Evidence is consistent with the declared income.",
        "model_version": "mock-inference-1.0.0",
        "prompt_version": "finding-generation-prompt-v1",
        "evidence_citations": (),
    }
    defaults.update(overrides)
    return InferenceResult(**defaults)  # type: ignore[arg-type]


class FakeFindingRepository:
    def __init__(self) -> None:
        self.saved: list[Finding] = []
        self.by_application: dict[object, list[Finding]] = {}
        self.by_id: dict[object, Finding] = {}
        self.force_collision = False
        self.collision_existing: Finding | None = None

    def save(self, finding: Finding) -> None:
        self.saved.append(finding)

    def save_if_not_exists(self, finding: Finding) -> bool:
        if self.force_collision:
            return False
        self.save(finding)
        return True

    def get_for_application(self, application_id: object) -> list[Finding]:
        return self.by_application.get(application_id, [])

    def get_by_id(self, finding_id: object) -> Finding | None:
        return self.by_id.get(finding_id)

    def get_by_application_and_version(
        self, application_id: object, model_version: str
    ) -> Finding | None:
        return self.collision_existing


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


def _make_service() -> tuple[FindingService, FakeFindingRepository, FakeAuditWriter]:
    repo = FakeFindingRepository()
    audit = FakeAuditWriter()
    return FindingService(repo, audit), repo, audit  # type: ignore[arg-type]


class TestGenerateFinding:
    def test_creates_one_finding(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert len(repo.saved) == 1

    def test_confidence_score_is_mean_of_evidence(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        # mean(0.850, 0.950) == 0.900
        assert repo.saved[0].confidence_score == Decimal("0.900")

    def test_confidence_label_derived_from_score(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert repo.saved[0].confidence_label == "HIGH"

    def test_rationale_is_inference_content(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(content="Custom rationale text."),
            extraction_version="mock-extraction-1.0.0",
        )
        assert repo.saved[0].rationale == "Custom rationale text."

    def test_records_model_and_prompt_version_from_result(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(model_version="m9", prompt_version="p9"),
            extraction_version="mock-extraction-1.0.0",
        )
        assert repo.saved[0].model_version == "m9"
        assert repo.saved[0].prompt_version == "p9"

    def test_records_extraction_version(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="custom-extraction-version",
        )
        assert repo.saved[0].extraction_version == "custom-extraction-version"

    def test_records_supporting_evidence_ids(self) -> None:
        service, repo, _ = _make_service()
        items = _evidence_items()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=items,  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert set(repo.saved[0].evidence_item_ids) == {str(item.id) for item in items}

    def test_default_finding_type(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert repo.saved[0].finding_type == "AI_GENERATED_ASSESSMENT"

    def test_custom_finding_type(self) -> None:
        service, repo, _ = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
            finding_type="INCOME_VERIFICATION",
        )
        assert repo.saved[0].finding_type == "INCOME_VERIFICATION"

    def test_emits_finding_generated_audit_event(self) -> None:
        service, _, audit = _make_service()
        service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert len(audit.records) == 1
        assert audit.records[0]["event_type"] == "FINDING_GENERATED"
        assert audit.records[0]["entity_type"] == "FINDING"

    def test_audit_event_carries_tenant_and_application(self) -> None:
        service, _, audit = _make_service()
        app_id, tenant_id = uuid4(), uuid4()
        service.generate_finding(
            application_id=app_id,
            tenant_id=tenant_id,
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert audit.records[0]["tenant_id"] == tenant_id
        assert audit.records[0]["application_id"] == app_id

    def test_links_finding_to_application_and_run(self) -> None:
        service, repo, _ = _make_service()
        app_id, run_id = uuid4(), uuid4()
        service.generate_finding(
            application_id=app_id,
            tenant_id=uuid4(),
            workflow_run_id=run_id,
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert repo.saved[0].application_id == app_id
        assert repo.saved[0].workflow_run_id == run_id

    def test_returns_created_true_on_first_call(self) -> None:
        service, _, _ = _make_service()
        _, created = service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(),
            extraction_version="mock-extraction-1.0.0",
        )
        assert created is True

    def test_replay_collision_returns_existing_finding_without_duplicate_audit(self) -> None:
        """ADR-008 §5: a uniqueness collision on create is a no-op, not an error."""
        service, repo, audit = _make_service()
        existing = Finding.create(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            finding_type="AI_GENERATED_ASSESSMENT",
            title="Existing",
            rationale="Existing rationale",
            evidence_summary="Existing summary",
            confidence_label="HIGH",
            recommended_action="Existing action",
            confidence_score=Decimal("0.9"),
            model_version="m1",
            prompt_version="p1",
            extraction_version="mock-extraction-1.0.0",
            evidence_item_ids=[uuid4()],
        )
        repo.force_collision = True
        repo.collision_existing = existing

        finding, created = service.generate_finding(
            application_id=uuid4(),
            tenant_id=uuid4(),
            workflow_run_id=uuid4(),
            evidence_items=_evidence_items(),  # type: ignore[arg-type]
            inference_result=_inference_result(model_version="m1"),
            extraction_version="mock-extraction-1.0.0",
        )

        assert created is False
        assert finding is existing
        assert repo.saved == []
        assert audit.records == []


def _make_user(*roles: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(uuid4()),
        roles=frozenset(roles or (Role.ADMIN,)),
    )


class TestListForApplication:
    def test_returns_items_for_application(self) -> None:
        service, repo, _ = _make_service()
        app_id = uuid4()
        findings = [uuid4(), uuid4()]
        repo.by_application[app_id] = findings  # type: ignore[assignment]
        result = service.list_for_application(_make_user(), application_id=app_id)
        assert result == findings

    def test_missing_permission_raises_authorization_error(self) -> None:
        service, _, _ = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()), tenant_id=TenantId(uuid4()), roles=frozenset()
        )
        with pytest.raises(AuthorizationError):
            service.list_for_application(user, application_id=uuid4())


class TestGetById:
    def test_returns_finding_when_present(self) -> None:
        service, repo, _ = _make_service()
        finding_id = uuid4()
        repo.by_id[finding_id] = "a-finding"  # type: ignore[assignment]
        result = service.get_by_id(_make_user(), finding_id=finding_id)
        assert result == "a-finding"

    def test_returns_none_when_absent(self) -> None:
        service, _, _ = _make_service()
        result = service.get_by_id(_make_user(), finding_id=uuid4())
        assert result is None

    def test_missing_permission_raises_authorization_error(self) -> None:
        service, _, _ = _make_service()
        user = AuthenticatedUser(
            user_id=UserId(uuid4()), tenant_id=TenantId(uuid4()), roles=frozenset()
        )
        with pytest.raises(AuthorizationError):
            service.get_by_id(user, finding_id=uuid4())
