"""Unit tests for mil.copilot.service — CopilotService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from mil.copilot.citations import EVIDENCE, FINDING, PARTY
from mil.copilot.classifier import classify_query
from mil.copilot.ports import (
    ApplicationView,
    FindingView,
    PartyView,
    PolicyResultView,
    ReviewSessionView,
)
from mil.copilot.prompts import get_prompt_version
from mil.copilot.service import CopilotService, GroundingBundle
from mil.kernel.errors import (
    AuthorizationError,
    NotFoundError,
    ProviderError,
    ProviderVersionMissingError,
    ScopeViolationError,
)
from mil.kernel.providers.inference import InferenceContext, InferenceResult
from mil.kernel.security import AuthenticatedUser, Role
from mil.kernel.types import TenantId, UserId

if TYPE_CHECKING:
    from mil.copilot.models import CopilotQuery, CopilotResponse, CopilotSession
    from mil.copilot.ports import DocumentTextView, DocumentView, EvidenceView, ReviewActionView

_MODEL_VERSION = "mock-inference-1.0.0"


def _user(tenant_id: object | None = None, *, permitted: bool = True) -> AuthenticatedUser:
    """An AuthenticatedUser with (or, if ``permitted=False``, without) query:copilot."""
    roles = frozenset({Role.UNDERWRITER}) if permitted else frozenset({Role.RELATIONSHIP_MANAGER})
    return AuthenticatedUser(
        user_id=UserId(uuid4()),
        tenant_id=TenantId(tenant_id if tenant_id is not None else uuid4()),  # type: ignore[arg-type]
        roles=roles,
        email="reviewer@mil.test",
        display_name="Test Reviewer",
    )


class FakeCopilotRepository:
    def __init__(self) -> None:
        self.saved_sessions: list[CopilotSession] = []
        self.saved_queries: list[CopilotQuery] = []
        self.saved_responses: list[CopilotResponse] = []

    def create_session(self, session: CopilotSession) -> None:
        self.saved_sessions.append(session)

    def append_query(self, query: CopilotQuery) -> None:
        self.saved_queries.append(query)

    def append_response(self, response: CopilotResponse) -> None:
        self.saved_responses.append(response)

    def get_session(self, session_id: object) -> CopilotSession | None:
        return next((s for s in self.saved_sessions if s.id == session_id), None)

    def get_latest_session_for_application(self, application_id: object) -> CopilotSession | None:
        matches = [s for s in self.saved_sessions if s.application_id == application_id]
        return max(matches, key=lambda s: s.created_at) if matches else None

    def get_history(self, session_id: object) -> list[tuple[CopilotQuery, CopilotResponse | None]]:
        queries = [q for q in self.saved_queries if q.session_id == session_id]
        responses_by_query_id = {r.query_id: r for r in self.saved_responses}
        return [(q, responses_by_query_id.get(q.id)) for q in queries]


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record(self, **kwargs: object) -> object:
        self.records.append(kwargs)
        return object()


class FakeInferenceProvider:
    def __init__(
        self,
        version: str = _MODEL_VERSION,
        *,
        result: InferenceResult | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._version = version
        self._result = result
        self._raises = raises
        self.calls: list[InferenceContext] = []

    def infer(self, context: InferenceContext) -> InferenceResult:
        self.calls.append(context)
        if self._raises is not None:
            raise self._raises
        if self._result is not None:
            return self._result
        # Default: cite every grounding item's ref (fully grounded response).
        citations = tuple(item.ref for item in context.grounding_items)
        return InferenceResult(
            content="Grounded answer citing all supplied records.",
            model_version=self._version,
            prompt_version=context.prompt_version,
            evidence_citations=citations,
        )

    def version(self) -> str:
        return self._version


class FakeApplicationReader:
    def __init__(self, application: ApplicationView | None) -> None:
        self._application = application

    def get_by_id(self, application_id: object) -> ApplicationView | None:
        return self._application


class FakePartyReader:
    def __init__(self, parties: list[PartyView] | None = None) -> None:
        self._parties = parties or []

    def get_for_application(self, application_id: object) -> list[PartyView]:
        return self._parties


class FakeDocumentReader:
    def __init__(self, documents: list[DocumentView] | None = None) -> None:
        self._documents = documents or []

    def get_for_application(self, application_id: object) -> list[DocumentView]:
        return self._documents


class FakeDocumentTextReader:
    def __init__(self, document_texts: list[DocumentTextView] | None = None) -> None:
        self._document_texts = document_texts or []

    def get_for_application(self, application_id: object) -> list[DocumentTextView]:
        return self._document_texts


class FakeEvidenceReader:
    def __init__(self, evidence: list[EvidenceView] | None = None) -> None:
        self._evidence = evidence or []

    def get_for_application(self, application_id: object) -> list[EvidenceView]:
        return self._evidence


class FakeFindingReader:
    def __init__(self, findings: list[FindingView] | None = None) -> None:
        self._findings = findings or []

    def get_for_application(self, application_id: object) -> list[FindingView]:
        return self._findings

    def get_by_id(self, finding_id: object) -> FindingView | None:
        return next((f for f in self._findings if f.id == finding_id), None)


class FakePolicyResultReader:
    def __init__(
        self, results_by_finding: dict[object, list[PolicyResultView]] | None = None
    ) -> None:
        self._results_by_finding = results_by_finding or {}

    def get_for_finding(self, finding_id: object) -> list[PolicyResultView]:
        return self._results_by_finding.get(finding_id, [])


class FakeReviewReader:
    def __init__(
        self,
        sessions_by_finding: dict[object, ReviewSessionView] | None = None,
        actions_by_session: dict[object, list[ReviewActionView]] | None = None,
    ) -> None:
        self._sessions_by_finding = sessions_by_finding or {}
        self._actions_by_session = actions_by_session or {}

    def get_session_for_finding(self, finding_id: object) -> ReviewSessionView | None:
        return self._sessions_by_finding.get(finding_id)

    def get_actions_for_session(self, review_session_id: object) -> list[ReviewActionView]:
        return self._actions_by_session.get(review_session_id, [])

    def get_comments_for_session(self, review_session_id: object) -> list[object]:
        return []


def _application_view(
    application_id: object,
    tenant_id: object,
    *,
    loan_number: str | None = "4009123456",
    los_reference: str | None = "LOS-0000042",
) -> ApplicationView:
    return ApplicationView(
        id=application_id,  # type: ignore[arg-type]
        tenant_id=tenant_id,  # type: ignore[arg-type]
        status="SUBMITTED",
        loan_number=loan_number,
        los_reference=los_reference,
        created_at=datetime.now(UTC),
    )


def _party_view(
    application_id: object, *, party_type: str = "APPLICANT", display_name: str = "Daniel Carter"
) -> PartyView:
    return PartyView(
        id=uuid4(),
        application_id=application_id,  # type: ignore[arg-type]
        party_type=party_type,
        display_name=display_name,
    )


def _finding_view(application_id: object) -> FindingView:
    return FindingView(
        id=uuid4(),
        application_id=application_id,  # type: ignore[arg-type]
        finding_type="INCOME_VERIFICATION",
        title="Income mismatch",
        rationale="Declared income does not match payslip.",
        evidence_summary="payslip=5000; declared=6000",
        confidence_label="MEDIUM",
        recommended_action="Verify with employer.",
        model_version=_MODEL_VERSION,
        prompt_version="explain-finding-v1",
        extraction_version="mock-extraction-1.0.0",
        created_at=datetime.now(UTC),
    )


def _make_service(
    *,
    application: ApplicationView | None = None,
    parties: list[PartyView] | None = None,
    documents: list[DocumentView] | None = None,
    document_texts: list[DocumentTextView] | None = None,
    evidence: list[EvidenceView] | None = None,
    findings: list[FindingView] | None = None,
    policy_results: dict[object, list[PolicyResultView]] | None = None,
    review_sessions: dict[object, ReviewSessionView] | None = None,
    review_actions: dict[object, list[ReviewActionView]] | None = None,
    inference: FakeInferenceProvider | None = None,
) -> tuple[CopilotService, FakeCopilotRepository, FakeAuditWriter, FakeInferenceProvider]:
    repo = FakeCopilotRepository()
    audit = FakeAuditWriter()
    fake_inference = inference or FakeInferenceProvider()
    service = CopilotService(
        repo,  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
        inference=fake_inference,  # type: ignore[arg-type]
        applications=FakeApplicationReader(application),  # type: ignore[arg-type]
        parties=FakePartyReader(parties),  # type: ignore[arg-type]
        documents=FakeDocumentReader(documents),  # type: ignore[arg-type]
        document_texts=FakeDocumentTextReader(document_texts),  # type: ignore[arg-type]
        evidence=FakeEvidenceReader(evidence),  # type: ignore[arg-type]
        findings=FakeFindingReader(findings),  # type: ignore[arg-type]
        policy_results=FakePolicyResultReader(policy_results),  # type: ignore[arg-type]
        reviews=FakeReviewReader(review_sessions, review_actions),  # type: ignore[arg-type]
    )
    return service, repo, audit, fake_inference


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_creates_and_saves_session(self) -> None:
        service, repo, _, _ = _make_service()
        tenant_id = uuid4()
        session = service.create_session(
            _user(tenant_id),
            application_id=uuid4(),
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        assert session in repo.saved_sessions

    def test_emits_session_created_audit_event(self) -> None:
        service, _, audit, _ = _make_service()
        service.create_session(
            _user(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        assert audit.records[0]["event_type"] == "COPILOT_SESSION_CREATED"

    def test_audit_event_carries_actor(self) -> None:
        service, _, audit, _ = _make_service()
        actor_id = uuid4()
        service.create_session(
            _user(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            created_by_user_id=actor_id,
            correlation_id="c-1",
        )
        assert audit.records[0]["actor_id"] == actor_id

    def test_raises_authorization_error_without_permission(self) -> None:
        service, _, _, _ = _make_service()
        with pytest.raises(AuthorizationError):
            service.create_session(
                _user(permitted=False),
                application_id=uuid4(),
                tenant_id=uuid4(),
                created_by_user_id=uuid4(),
                correlation_id="c-1",
            )


# ---------------------------------------------------------------------------
# start_or_resume_session
# ---------------------------------------------------------------------------


class TestStartOrResumeSession:
    def test_creates_new_session_when_no_session_id(self) -> None:
        service, repo, _, _ = _make_service()
        tenant_id, application_id = uuid4(), uuid4()
        session = service.start_or_resume_session(
            _user(tenant_id),
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            session_id=None,
            correlation_id="c-1",
        )
        assert session in repo.saved_sessions

    def test_resumes_existing_session(self) -> None:
        service, repo, _, _ = _make_service()
        tenant_id, application_id = uuid4(), uuid4()
        created = service.create_session(
            _user(tenant_id),
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        resumed = service.start_or_resume_session(
            _user(tenant_id),
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            session_id=created.id,
            correlation_id="ignored",
        )
        assert resumed.id == created.id
        assert len(repo.saved_sessions) == 1  # no duplicate session created

    def test_raises_not_found_for_unknown_session_id(self) -> None:
        service, _, _, _ = _make_service()
        with pytest.raises(NotFoundError):
            service.start_or_resume_session(
                _user(),
                application_id=uuid4(),
                tenant_id=uuid4(),
                created_by_user_id=uuid4(),
                session_id=uuid4(),
                correlation_id="c-1",
            )

    def test_raises_not_found_when_session_belongs_to_different_application(self) -> None:
        service, _, _, _ = _make_service()
        tenant_id = uuid4()
        created = service.create_session(
            _user(tenant_id),
            application_id=uuid4(),
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        with pytest.raises(NotFoundError):
            service.start_or_resume_session(
                _user(tenant_id),
                application_id=uuid4(),  # different application
                tenant_id=tenant_id,
                created_by_user_id=uuid4(),
                session_id=created.id,
                correlation_id="c-1",
            )


# ---------------------------------------------------------------------------
# submit_query
# ---------------------------------------------------------------------------


class TestSubmitQuery:
    def _session(self, service: CopilotService) -> CopilotSession:
        return service.create_session(
            _user(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )

    def test_records_query_on_session(self) -> None:
        service, repo, _, _ = _make_service()
        session = self._session(service)
        query = service.submit_query(
            _user(), session, question_text="Why was this flagged?", asked_by_user_id=uuid4()
        )
        assert query in repo.saved_queries
        assert query.session_id == session.id

    def test_emits_query_recorded_audit_event(self) -> None:
        service, _, audit, _ = _make_service()
        session = self._session(service)
        service.submit_query(_user(), session, question_text="Why?", asked_by_user_id=uuid4())
        assert audit.records[-1]["event_type"] == "COPILOT_QUERY_RECORDED"

    def test_raises_authorization_error_without_permission(self) -> None:
        service, _, _, _ = _make_service()
        session = self._session(service)
        with pytest.raises(AuthorizationError):
            service.submit_query(
                _user(permitted=False),
                session,
                question_text="Why?",
                asked_by_user_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# record_response
# ---------------------------------------------------------------------------


class TestRecordResponse:
    def test_persists_response(self) -> None:
        service, repo, _, _ = _make_service()
        session = service.create_session(
            _user(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            _user(), session, question_text="Why?", asked_by_user_id=uuid4()
        )
        response = service.record_response(
            query, answer_text="Because.", prompt_version="v1", model_version="m1"
        )
        assert response in repo.saved_responses
        assert response.query_id == query.id

    def test_does_not_emit_audit_event(self) -> None:
        """record_response is the low-level append; generate_response owns auditing."""
        service, _, audit, _ = _make_service()
        session = service.create_session(
            _user(),
            application_id=uuid4(),
            tenant_id=uuid4(),
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            _user(), session, question_text="Why?", asked_by_user_id=uuid4()
        )
        audit_count_before = len(audit.records)
        service.record_response(
            query, answer_text="Because.", prompt_version="v1", model_version="m1"
        )
        assert len(audit.records) == audit_count_before


# ---------------------------------------------------------------------------
# get_session / get_latest_session_for_application / get_history
# ---------------------------------------------------------------------------


class TestGetSession:
    def test_returns_session_for_owning_tenant(self) -> None:
        service, _, _, _ = _make_service()
        tenant_id = uuid4()
        created = service.create_session(
            _user(tenant_id),
            application_id=uuid4(),
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        found = service.get_session(_user(tenant_id), created.id)
        assert found.id == created.id

    def test_raises_not_found_for_unknown_session(self) -> None:
        service, _, _, _ = _make_service()
        with pytest.raises(NotFoundError):
            service.get_session(_user(), uuid4())

    def test_raises_not_found_for_cross_tenant_session(self) -> None:
        service, _, _, _ = _make_service()
        owning_tenant, other_tenant = uuid4(), uuid4()
        created = service.create_session(
            _user(owning_tenant),
            application_id=uuid4(),
            tenant_id=owning_tenant,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        with pytest.raises(NotFoundError):
            service.get_session(_user(other_tenant), created.id)

    def test_raises_authorization_error_without_permission(self) -> None:
        service, _, _, _ = _make_service()
        tenant_id = uuid4()
        created = service.create_session(
            _user(tenant_id),
            application_id=uuid4(),
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        with pytest.raises(AuthorizationError):
            service.get_session(_user(tenant_id, permitted=False), created.id)


class TestGetLatestSessionForApplication:
    def test_returns_most_recent_session(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        service, _, _, _ = _make_service(application=application)
        service.create_session(
            _user(tenant_id),
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        latest = service.create_session(
            _user(tenant_id),
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-2",
        )
        found = service.get_latest_session_for_application(
            _user(tenant_id), application_id, tenant_id=tenant_id
        )
        assert found.id == latest.id

    def test_raises_not_found_for_missing_application(self) -> None:
        service, _, _, _ = _make_service(application=None)
        with pytest.raises(NotFoundError):
            service.get_latest_session_for_application(_user(), uuid4(), tenant_id=uuid4())

    def test_raises_scope_violation_for_wrong_tenant(self) -> None:
        application_id, owning_tenant, other_tenant = uuid4(), uuid4(), uuid4()
        application = _application_view(application_id, owning_tenant)
        service, _, _, _ = _make_service(application=application)
        with pytest.raises(ScopeViolationError):
            service.get_latest_session_for_application(
                _user(other_tenant), application_id, tenant_id=other_tenant
            )

    def test_raises_not_found_when_no_session_exists_yet(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        service, _, _, _ = _make_service(application=application)
        with pytest.raises(NotFoundError):
            service.get_latest_session_for_application(
                _user(tenant_id), application_id, tenant_id=tenant_id
            )


class TestGetHistory:
    def test_pairs_queries_with_responses(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        service, _, _, _ = _make_service(application=application, findings=[finding])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain the finding.", asked_by_user_id=uuid4()
        )
        service.generate_response(user, session, query)

        history = service.get_history(user, session)

        assert len(history) == 1
        returned_query, returned_response = history[0]
        assert returned_query.id == query.id
        assert returned_response is not None

    def test_emits_response_viewed_audit_event_per_response(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        service, _, audit, _ = _make_service(application=application, findings=[finding])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain the finding.", asked_by_user_id=uuid4()
        )
        service.generate_response(user, session, query)
        audit.records.clear()

        service.get_history(user, session)

        assert len(audit.records) == 1
        assert audit.records[0]["event_type"] == "COPILOT_RESPONSE_VIEWED"

    def test_no_audit_event_when_query_has_no_response_yet(self) -> None:
        service, _, audit, _ = _make_service()
        user = _user()
        session = service.create_session(
            user,
            application_id=uuid4(),
            tenant_id=uuid4(),
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        service.submit_query(user, session, question_text="Why?", asked_by_user_id=uuid4())
        audit.records.clear()

        service.get_history(user, session)

        assert audit.records == []


# ---------------------------------------------------------------------------
# assemble_grounding
# ---------------------------------------------------------------------------


class TestAssembleGrounding:
    def test_raises_not_found_for_missing_application(self) -> None:
        service, _, _, _ = _make_service(application=None)
        with pytest.raises(NotFoundError):
            service.assemble_grounding(uuid4(), tenant_id=uuid4())

    def test_raises_scope_violation_for_wrong_tenant(self) -> None:
        application_id, owning_tenant, other_tenant = uuid4(), uuid4(), uuid4()
        application = _application_view(application_id, owning_tenant)
        service, _, _, _ = _make_service(application=application)
        with pytest.raises(ScopeViolationError):
            service.assemble_grounding(application_id, tenant_id=other_tenant)

    def test_returns_bundle_scoped_to_application(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        policy_result = PolicyResultView(
            id=uuid4(),
            finding_id=finding.id,
            policy_version="policy-v1",
            rule_ref="RULE-001",
            status="PASS",
            rationale="Within tolerance.",
            evaluated_at=datetime.now(UTC),
        )
        review_session = ReviewSessionView(
            id=uuid4(),
            finding_id=finding.id,
            application_id=application_id,  # type: ignore[arg-type]
            status="PENDING_REVIEW",
            assigned_reviewer_id=None,
            created_at=datetime.now(UTC),
            closed_at=None,
        )
        service, _, _, _ = _make_service(
            application=application,
            findings=[finding],
            policy_results={finding.id: [policy_result]},
            review_sessions={finding.id: review_session},
        )

        bundle = service.assemble_grounding(application_id, tenant_id=tenant_id)

        assert isinstance(bundle, GroundingBundle)
        assert bundle.application_id == application_id
        assert bundle.application == application
        assert bundle.findings == (finding,)
        assert bundle.policy_results == (policy_result,)
        assert bundle.review_sessions == (review_session,)
        assert bundle.review_actions == ()


# ---------------------------------------------------------------------------
# generate_response
# ---------------------------------------------------------------------------


class TestGenerateResponseGrounded:
    def _grounded_service(
        self,
    ) -> tuple[
        CopilotService,
        FakeCopilotRepository,
        FakeAuditWriter,
        AuthenticatedUser,
        CopilotSession,
        CopilotQuery,
    ]:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        service, repo, audit, _ = _make_service(application=application, findings=[finding])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Why was this finding raised?", asked_by_user_id=uuid4()
        )
        return service, repo, audit, user, session, query

    def test_returns_and_persists_grounded_response(self) -> None:
        service, repo, _, user, session, query = self._grounded_service()
        response = service.generate_response(user, session, query)
        assert response in repo.saved_responses
        assert response.answer_text == "Grounded answer citing all supplied records."

    def test_records_model_and_prompt_version(self) -> None:
        service, _, _, user, session, query = self._grounded_service()
        response = service.generate_response(user, session, query)
        assert response.model_version == _MODEL_VERSION
        assert response.prompt_version

    def test_includes_citations(self) -> None:
        service, _, _, user, session, query = self._grounded_service()
        response = service.generate_response(user, session, query)
        assert len(response.citations) > 0
        assert any(c["kind"] == FINDING for c in response.citations)

    def test_emits_response_generated_audit_event(self) -> None:
        service, _, audit, user, session, query = self._grounded_service()
        service.generate_response(user, session, query)
        assert audit.records[-1]["event_type"] == "COPILOT_RESPONSE_GENERATED"
        assert audit.records[-1]["event_data"]["degraded"] is False  # type: ignore[index]

    def test_uses_prompt_version_selected_by_the_classifier(self) -> None:
        service, _, _, user, session, query = self._grounded_service()
        response = service.generate_response(user, session, query)
        expected_prompt_id = classify_query(query.question_text)
        assert response.prompt_version == get_prompt_version(expected_prompt_id)

    def test_raises_authorization_error_without_permission(self) -> None:
        service, _, _, _user_unused, session, query = self._grounded_service()
        unpermitted = _user(session.tenant_id, permitted=False)
        with pytest.raises(AuthorizationError):
            service.generate_response(unpermitted, session, query)

    def test_grounding_items_passed_to_provider_include_evidence_kind(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        from mil.copilot.ports import EvidenceView

        evidence = EvidenceView(
            id=uuid4(),
            application_id=application_id,  # type: ignore[arg-type]
            document_id=uuid4(),
            evidence_type="GROSS_MONTHLY_INCOME",
            value_text="5000.00",
            confidence=0.9,
            page_number=1,
            field_location=None,
            extraction_method="mock",
            extraction_model_version="mock-extraction-1.0.0",
            extracted_at=datetime.now(UTC),
        )
        service, _, _, inference = _make_service(application=application, evidence=[evidence])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )
        service.generate_response(user, session, query)
        kinds = {item.kind for item in inference.calls[0].grounding_items}
        assert EVIDENCE in kinds


class TestGenerateResponseGroundedInDocumentText:
    """
    End-to-end: Copilot answers from a document's raw extracted text (Output 1
    of the Document Intelligence pipeline), citing it back — this is the path
    that was previously broken (grounding only ever saw structured Evidence,
    never the document's actual transcribed content, so free-form questions
    like "who is the borrower?" had nothing to ground on even when the
    document plainly contained the answer).
    """

    def test_document_text_alone_satisfies_the_grounding_gate(self) -> None:
        """No Evidence/Finding rows exist yet — only raw OCR text — and the
        service must still proceed to inference rather than returning the
        safe-failure response."""
        from mil.copilot.ports import DocumentTextView

        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        doc_text = DocumentTextView(
            document_id=uuid4(),
            provider_version="gemini-ocr:gemini-2.5-flash",
            page_count=1,
            full_text="Borrower: Jane Doe. Loan Amount: 350000.",
            processed_at=datetime.now(UTC),
        )
        service, repo, _, inference = _make_service(
            application=application, document_texts=[doc_text]
        )
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Who is the borrower?", asked_by_user_id=uuid4()
        )
        response = service.generate_response(user, session, query)

        assert inference.calls, "inference must be called — document text alone is sufficient"
        assert response in repo.saved_responses
        assert response.answer_text != ""

    def test_document_text_grounding_item_is_built_and_citable(self) -> None:
        from mil.copilot.citations import DOCUMENT_TEXT
        from mil.copilot.ports import DocumentTextView

        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        doc_id = uuid4()
        doc_text = DocumentTextView(
            document_id=doc_id,
            provider_version="gemini-ocr:gemini-2.5-flash",
            page_count=2,
            full_text="Borrower: Jane Doe. Employer: Acme Corp.",
            processed_at=datetime.now(UTC),
        )
        service, _, _, inference = _make_service(application=application, document_texts=[doc_text])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Who is the borrower?", asked_by_user_id=uuid4()
        )
        response = service.generate_response(user, session, query)

        grounding_items = inference.calls[0].grounding_items
        doc_text_items = [item for item in grounding_items if item.kind == DOCUMENT_TEXT]
        assert len(doc_text_items) == 1
        assert doc_text_items[0].ref == f"doctext-{doc_id}"
        assert "Jane Doe" in doc_text_items[0].summary

        # The default FakeInferenceProvider cites every grounding item's ref,
        # so the document-text citation must resolve back through the
        # citation index and appear on the persisted response.
        assert any(c["kind"] == DOCUMENT_TEXT for c in response.citations)


class TestGenerateResponseGroundedInPartyRecords:
    """
    End-to-end: Copilot answers "who is the borrower?" from the real,
    structured ``Party`` record (final grounding-pipeline sprint) — the path
    that was previously entirely missing. Before this, `assemble_grounding`
    never queried `core.parties` at all, so an identity question could only
    ever be answered incidentally, via an OCR-extracted `borrower_name`
    `EvidenceItem` that happened to carry the same value — never from the
    authoritative record itself, and never on an application that had real
    parties but no evidence extracted yet.
    """

    def test_party_alone_satisfies_the_grounding_gate(self) -> None:
        """No Evidence/Finding/DocumentText rows exist yet — only a real
        Party record — and the service must still proceed to inference
        rather than returning the safe-failure response."""
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        party = _party_view(application_id, party_type="APPLICANT", display_name="Daniel Carter")
        service, repo, _, inference = _make_service(application=application, parties=[party])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Who is the borrower?", asked_by_user_id=uuid4()
        )
        response = service.generate_response(user, session, query)

        assert inference.calls, "inference must be called — a Party record alone is sufficient"
        assert response in repo.saved_responses
        assert response.answer_text != ""

    def test_party_grounding_item_is_built_and_citable(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        party = _party_view(application_id, party_type="APPLICANT", display_name="Daniel Carter")
        service, _, _, inference = _make_service(application=application, parties=[party])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Who is the borrower?", asked_by_user_id=uuid4()
        )
        response = service.generate_response(user, session, query)

        grounding_items = inference.calls[0].grounding_items
        party_items = [item for item in grounding_items if item.kind == PARTY]
        assert len(party_items) == 1
        assert party_items[0].ref == str(party.id)
        assert "Daniel Carter" in party_items[0].summary
        assert "APPLICANT" in party_items[0].summary

        # The default FakeInferenceProvider cites every grounding item's ref,
        # so the party citation must resolve back through the citation index
        # and appear on the persisted response.
        assert any(c["kind"] == PARTY for c in response.citations)

    def test_application_summary_includes_the_real_loan_number_and_los_reference(self) -> None:
        """The APPLICATION grounding item previously carried only status —
        no loan number, no LOS reference — leaving nothing to cite for
        "what loan is this" style questions."""
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(
            application_id, tenant_id, loan_number="4009123456", los_reference="LOS-0000042"
        )
        party = _party_view(application_id)
        service, _, _, inference = _make_service(application=application, parties=[party])
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="What loan is this?", asked_by_user_id=uuid4()
        )
        service.generate_response(user, session, query)

        grounding_items = inference.calls[0].grounding_items
        application_item = next(item for item in grounding_items if item.kind == "APPLICATION")
        assert "4009123456" in application_item.summary
        assert "LOS-0000042" in application_item.summary


class TestGenerateResponseInsufficientGrounding:
    def test_returns_safe_failure_when_no_governed_records(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        service, repo, _, inference = _make_service(application=application)
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )

        response = service.generate_response(user, session, query)

        assert "don't have enough" in response.answer_text.lower()
        assert response.citations == []
        assert response in repo.saved_responses
        assert inference.calls == []  # never called inference on empty grounding

    def test_records_degraded_audit_event(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        service, _, audit, _ = _make_service(application=application)
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )

        service.generate_response(user, session, query)

        event = audit.records[-1]
        assert event["event_type"] == "COPILOT_RESPONSE_GENERATED"
        assert event["event_data"]["degraded"] is True  # type: ignore[index]
        assert event["event_data"]["citation_count"] == 0  # type: ignore[index]

    def test_still_attributes_prompt_and_model_version(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        service, _, _, _ = _make_service(application=application)
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )

        response = service.generate_response(user, session, query)

        assert response.model_version == _MODEL_VERSION
        assert response.prompt_version


class TestGenerateResponseUngroundedModelAnswer:
    def test_degrades_when_no_citations_resolve(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        hallucinated_result = InferenceResult(
            content="A fabricated claim citing nothing real.",
            model_version=_MODEL_VERSION,
            prompt_version="freeform-question-v1",
            evidence_citations=("does-not-exist",),
        )
        inference = FakeInferenceProvider(result=hallucinated_result)
        service, _, audit, _ = _make_service(
            application=application, findings=[finding], inference=inference
        )
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )

        response = service.generate_response(user, session, query)

        assert response.answer_text != hallucinated_result.content
        assert "don't have enough" in response.answer_text.lower()
        assert response.citations == []
        assert audit.records[-1]["event_data"]["degraded"] is True  # type: ignore[index]
        assert (
            audit.records[-1]["event_data"]["degraded_reason"]  # type: ignore[index]
            == "ungrounded_model_response"
        )

    def test_partial_hallucinated_citations_are_dropped_not_trusted(self) -> None:
        """A response with a mix of real and fabricated citations keeps only real ones."""
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        mixed_result = InferenceResult(
            content="Partially grounded answer.",
            model_version=_MODEL_VERSION,
            prompt_version="freeform-question-v1",
            evidence_citations=(str(finding.id), "does-not-exist"),
        )
        inference = FakeInferenceProvider(result=mixed_result)
        service, _, _, _ = _make_service(
            application=application, findings=[finding], inference=inference
        )
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )

        response = service.generate_response(user, session, query)

        assert response.answer_text == "Partially grounded answer."
        assert response.citations == [{"kind": FINDING, "ref": str(finding.id)}]


class TestGenerateResponseProviderVersionValidation:
    def test_raises_when_provider_version_missing(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        inference = FakeInferenceProvider(version="")
        service, _, _, _ = _make_service(
            application=application, findings=[finding], inference=inference
        )
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )

        with pytest.raises(ProviderVersionMissingError):
            service.generate_response(user, session, query)

    def test_raises_when_result_model_version_mismatches_provider_version(self) -> None:
        application_id, tenant_id = uuid4(), uuid4()
        application = _application_view(application_id, tenant_id)
        finding = _finding_view(application_id)
        mismatched_result = InferenceResult(
            content="Answer.",
            model_version="some-other-version",
            prompt_version="freeform-question-v1",
            evidence_citations=(str(finding.id),),
        )
        inference = FakeInferenceProvider(version=_MODEL_VERSION, result=mismatched_result)
        service, _, _, _ = _make_service(
            application=application, findings=[finding], inference=inference
        )
        user = _user(tenant_id)
        session = service.create_session(
            user,
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=uuid4(),
            correlation_id="c-1",
        )
        query = service.submit_query(
            user, session, question_text="Explain.", asked_by_user_id=uuid4()
        )

        with pytest.raises(ProviderError):
            service.generate_response(user, session, query)
