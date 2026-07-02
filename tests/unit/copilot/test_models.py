"""Unit tests for mil.copilot.models — CopilotSession, CopilotQuery, CopilotResponse."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mil.copilot.citations import FINDING, Citation
from mil.copilot.models import CopilotQuery, CopilotResponse, CopilotSession
from mil.kernel.errors import ValidationError


class TestCopilotSessionCreate:
    def test_sets_scope_fields(self) -> None:
        application_id, tenant_id, user_id = uuid4(), uuid4(), uuid4()
        session = CopilotSession.create(
            application_id=application_id,
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            correlation_id="corr-001",
        )
        assert session.application_id == application_id
        assert session.tenant_id == tenant_id
        assert session.created_by_user_id == user_id
        assert session.correlation_id == "corr-001"

    def test_sets_created_at(self) -> None:
        session = CopilotSession.create(
            application_id=uuid4(),
            tenant_id=uuid4(),
            created_by_user_id=uuid4(),
            correlation_id="corr-001",
        )
        assert session.created_at is not None

    def test_rejects_empty_correlation_id(self) -> None:
        with pytest.raises(ValidationError):
            CopilotSession.create(
                application_id=uuid4(),
                tenant_id=uuid4(),
                created_by_user_id=uuid4(),
                correlation_id="",
            )

    def test_table_in_copilot_schema(self) -> None:
        assert CopilotSession.__table__.schema == "copilot"


class TestCopilotQueryCreate:
    def test_links_to_session(self) -> None:
        session_id = uuid4()
        query = CopilotQuery.create(
            session_id=session_id, asked_by_user_id=uuid4(), question_text="Why was this flagged?"
        )
        assert query.session_id == session_id

    def test_records_question_text(self) -> None:
        query = CopilotQuery.create(
            session_id=uuid4(), asked_by_user_id=uuid4(), question_text="Explain this finding."
        )
        assert query.question_text == "Explain this finding."

    def test_rejects_empty_question_text(self) -> None:
        with pytest.raises(ValidationError):
            CopilotQuery.create(session_id=uuid4(), asked_by_user_id=uuid4(), question_text="")

    def test_rejects_whitespace_only_question_text(self) -> None:
        with pytest.raises(ValidationError):
            CopilotQuery.create(session_id=uuid4(), asked_by_user_id=uuid4(), question_text="   ")

    def test_sets_created_at(self) -> None:
        query = CopilotQuery.create(
            session_id=uuid4(), asked_by_user_id=uuid4(), question_text="Explain this."
        )
        assert query.created_at is not None

    def test_table_in_copilot_schema(self) -> None:
        assert CopilotQuery.__table__.schema == "copilot"


class TestCopilotResponseCreate:
    def test_links_to_query(self) -> None:
        query_id = uuid4()
        response = CopilotResponse.create(
            query_id=query_id,
            answer_text="The finding was raised due to income inconsistency.",
            prompt_version="explain-finding-v1",
            model_version="mock-inference-1.0.0",
        )
        assert response.query_id == query_id

    def test_records_attribution(self) -> None:
        response = CopilotResponse.create(
            query_id=uuid4(),
            answer_text="Answer.",
            prompt_version="explain-finding-v1",
            model_version="mock-inference-1.0.0",
        )
        assert response.prompt_version == "explain-finding-v1"
        assert response.model_version == "mock-inference-1.0.0"

    def test_serializes_citations(self) -> None:
        response = CopilotResponse.create(
            query_id=uuid4(),
            answer_text="Answer.",
            prompt_version="explain-finding-v1",
            model_version="mock-inference-1.0.0",
            citations=[Citation(kind=FINDING, ref="finding-001")],
        )
        assert response.citations == [{"kind": FINDING, "ref": "finding-001"}]

    def test_defaults_citations_to_empty_list(self) -> None:
        response = CopilotResponse.create(
            query_id=uuid4(),
            answer_text="Answer.",
            prompt_version="explain-finding-v1",
            model_version="mock-inference-1.0.0",
        )
        assert response.citations == []

    def test_rejects_empty_answer_text(self) -> None:
        with pytest.raises(ValidationError):
            CopilotResponse.create(
                query_id=uuid4(),
                answer_text="",
                prompt_version="explain-finding-v1",
                model_version="mock-inference-1.0.0",
            )

    def test_rejects_empty_prompt_version(self) -> None:
        with pytest.raises(ValidationError):
            CopilotResponse.create(
                query_id=uuid4(),
                answer_text="Answer.",
                prompt_version="",
                model_version="mock-inference-1.0.0",
            )

    def test_rejects_empty_model_version(self) -> None:
        with pytest.raises(ValidationError):
            CopilotResponse.create(
                query_id=uuid4(),
                answer_text="Answer.",
                prompt_version="explain-finding-v1",
                model_version="",
            )

    def test_sets_created_at(self) -> None:
        response = CopilotResponse.create(
            query_id=uuid4(),
            answer_text="Answer.",
            prompt_version="explain-finding-v1",
            model_version="mock-inference-1.0.0",
        )
        assert response.created_at is not None

    def test_table_in_copilot_schema(self) -> None:
        assert CopilotResponse.__table__.schema == "copilot"
