"""Unit tests for mil.copilot.repository — CopilotRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from mil.copilot.models import CopilotQuery, CopilotResponse, CopilotSession
from mil.copilot.repository import CopilotRepository


def _session() -> CopilotSession:
    return CopilotSession.create(
        application_id=uuid4(), tenant_id=uuid4(), created_by_user_id=uuid4(), correlation_id="c-1"
    )


def _query(session_id: object | None = None) -> CopilotQuery:
    return CopilotQuery.create(
        session_id=session_id or uuid4(), asked_by_user_id=uuid4(), question_text="Why?"
    )


def _response(query_id: object | None = None) -> CopilotResponse:
    return CopilotResponse.create(
        query_id=query_id or uuid4(),
        answer_text="Because.",
        prompt_version="v1",
        model_version="m1",
    )


def _make_repo() -> tuple[CopilotRepository, MagicMock]:
    session = MagicMock()
    return CopilotRepository(session), session


class TestCreateSession:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        copilot_session = _session()
        repo.create_session(copilot_session)
        session.add.assert_called_once_with(copilot_session)
        session.flush.assert_called_once()


class TestGetSession:
    def test_returns_session(self) -> None:
        repo, session = _make_repo()
        copilot_session = _session()
        session.get.return_value = copilot_session
        assert repo.get_session(copilot_session.id) is copilot_session

    def test_returns_none_when_missing(self) -> None:
        repo, session = _make_repo()
        session.get.return_value = None
        assert repo.get_session(uuid4()) is None


class TestGetLatestSessionForApplication:
    def test_returns_most_recent(self) -> None:
        repo, session = _make_repo()
        latest = _session()
        session.scalars.return_value.first.return_value = latest
        assert repo.get_latest_session_for_application(uuid4()) is latest

    def test_returns_none_when_absent(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value.first.return_value = None
        assert repo.get_latest_session_for_application(uuid4()) is None


class TestAppendQuery:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        query = _query()
        repo.append_query(query)
        session.add.assert_called_once_with(query)
        session.flush.assert_called_once()

    def test_does_not_commit(self) -> None:
        repo, session = _make_repo()
        repo.append_query(_query())
        session.commit.assert_not_called()


class TestGetQueriesForSession:
    def test_returns_list(self) -> None:
        repo, session = _make_repo()
        q1, q2 = _query(), _query()
        session.scalars.return_value = iter([q1, q2])
        assert repo.get_queries_for_session(uuid4()) == [q1, q2]


class TestAppendResponse:
    def test_adds_and_flushes(self) -> None:
        repo, session = _make_repo()
        response = _response()
        repo.append_response(response)
        session.add.assert_called_once_with(response)
        session.flush.assert_called_once()


class TestGetHistory:
    def test_returns_empty_list_when_no_queries(self) -> None:
        repo, session = _make_repo()
        session.scalars.return_value = iter([])
        assert repo.get_history(uuid4()) == []

    def test_pairs_query_with_its_response(self) -> None:
        repo, session = _make_repo()
        session_id = uuid4()
        query = _query(session_id)
        response = _response(query.id)

        # get_queries_for_session -> [query]; then responses lookup -> [response]
        session.scalars.side_effect = [iter([query]), iter([response])]

        assert repo.get_history(session_id) == [(query, response)]

    def test_query_without_response_pairs_with_none(self) -> None:
        repo, session = _make_repo()
        session_id = uuid4()
        query = _query(session_id)

        session.scalars.side_effect = [iter([query]), iter([])]

        assert repo.get_history(session_id) == [(query, None)]
