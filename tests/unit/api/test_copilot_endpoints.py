"""Unit tests for Copilot API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from mil.api.deps import (
    get_application_service,
    get_current_user,
    get_document_service,
    get_finding_trigger,
)
from mil.kernel.errors import (
    AuthorizationError,
    NotFoundError,
    ProviderVersionMissingError,
    ScopeViolationError,
)
from mil.kernel.security import AuthenticatedUser, Role
from tests.unit.api.conftest import (
    TEST_APP_ID,
    TEST_TENANT_ID,
    make_copilot_query,
    make_copilot_response,
    make_copilot_session,
    make_user,
)


def _make_client_with_no_auth_override() -> TestClient:
    """TestClient WITHOUT the current_user override — exercises the real auth dependency."""
    from main import create_app

    app = create_app()
    app.dependency_overrides[get_application_service] = lambda: MagicMock()
    app.dependency_overrides[get_document_service] = lambda: MagicMock()
    app.dependency_overrides[get_finding_trigger] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# POST /v1/copilot/query
# ---------------------------------------------------------------------------


class TestSubmitCopilotQuery:
    def test_returns_201_on_grounded_response(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        response = make_copilot_response(query_id=query.id)
        mock_copilot_service.start_or_resume_session.return_value = session
        mock_copilot_service.submit_query.return_value = query
        mock_copilot_service.generate_response.return_value = response

        result = client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why was this flagged?"},
        )

        assert result.status_code == 201

    def test_returns_response_body_with_citations(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        response = make_copilot_response(query_id=query.id, citations=[])
        mock_copilot_service.start_or_resume_session.return_value = session
        mock_copilot_service.submit_query.return_value = query
        mock_copilot_service.generate_response.return_value = response

        data = client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why was this flagged?"},
        ).json()

        assert data["answer"] == response.answer_text
        assert data["prompt_version"] == response.prompt_version
        assert data["model_version"] == response.model_version
        assert data["session_id"] == str(session.id)
        assert data["citations"] == []

    def test_passes_application_id_and_question_to_service(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        response = make_copilot_response(query_id=query.id)
        mock_copilot_service.start_or_resume_session.return_value = session
        mock_copilot_service.submit_query.return_value = query
        mock_copilot_service.generate_response.return_value = response

        client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Explain the finding."},
        )

        start_kwargs = mock_copilot_service.start_or_resume_session.call_args.kwargs
        assert start_kwargs["application_id"] == TEST_APP_ID
        submit_kwargs = mock_copilot_service.submit_query.call_args.kwargs
        assert submit_kwargs["question_text"] == "Explain the finding."

    def test_tenant_id_comes_from_authenticated_user(
        self,
        client: TestClient,
        mock_copilot_service: MagicMock,
        current_user: AuthenticatedUser,
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        response = make_copilot_response(query_id=query.id)
        mock_copilot_service.start_or_resume_session.return_value = session
        mock_copilot_service.submit_query.return_value = query
        mock_copilot_service.generate_response.return_value = response

        client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why?"},
        )

        start_kwargs = mock_copilot_service.start_or_resume_session.call_args.kwargs
        assert start_kwargs["tenant_id"] == current_user.tenant_id

    def test_passes_session_id_when_resuming(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        response = make_copilot_response(query_id=query.id)
        mock_copilot_service.start_or_resume_session.return_value = session
        mock_copilot_service.submit_query.return_value = query
        mock_copilot_service.generate_response.return_value = response

        client.post(
            "/v1/copilot/query",
            json={
                "application_id": str(TEST_APP_ID),
                "session_id": str(session.id),
                "question": "Follow-up question.",
            },
        )

        start_kwargs = mock_copilot_service.start_or_resume_session.call_args.kwargs
        assert start_kwargs["session_id"] == session.id

    def test_missing_question_returns_422(self, client: TestClient) -> None:
        result = client.post("/v1/copilot/query", json={"application_id": str(TEST_APP_ID)})
        assert result.status_code == 422

    def test_empty_question_returns_422(self, client: TestClient) -> None:
        result = client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": ""},
        )
        assert result.status_code == 422

    def test_missing_application_id_returns_422(self, client: TestClient) -> None:
        result = client.post("/v1/copilot/query", json={"question": "Why?"})
        assert result.status_code == 422

    def test_service_authorization_error_returns_403(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        mock_copilot_service.start_or_resume_session.side_effect = AuthorizationError(
            message="Permission denied: 'query:copilot' is required",
            required_permission="query:copilot",
        )
        result = client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why?"},
        )
        assert result.status_code == 403

    def test_service_not_found_returns_404(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        mock_copilot_service.start_or_resume_session.side_effect = NotFoundError(
            "Application", TEST_APP_ID
        )
        result = client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why?"},
        )
        assert result.status_code == 404

    def test_service_scope_violation_returns_422(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        mock_copilot_service.start_or_resume_session.return_value = session
        mock_copilot_service.submit_query.return_value = query
        mock_copilot_service.generate_response.side_effect = ScopeViolationError(
            "Application does not belong to the requesting tenant"
        )
        result = client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why?"},
        )
        assert result.status_code == 422

    def test_provider_version_missing_returns_500(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        """A provider-attribution contract violation is an internal error, not a client error."""
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        mock_copilot_service.start_or_resume_session.return_value = session
        mock_copilot_service.submit_query.return_value = query
        mock_copilot_service.generate_response.side_effect = ProviderVersionMissingError(
            "InferenceProvider", "version"
        )
        result = client.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why?"},
        )
        assert result.status_code == 500

    def test_requires_authentication(self) -> None:
        tc = _make_client_with_no_auth_override()
        result = tc.post(
            "/v1/copilot/query",
            json={"application_id": str(TEST_APP_ID), "question": "Why?"},
        )
        assert result.status_code == 401


# ---------------------------------------------------------------------------
# GET /v1/copilot/sessions/{session_id}
# ---------------------------------------------------------------------------


class TestGetCopilotSession:
    def test_returns_200_with_session_metadata(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        mock_copilot_service.get_session.return_value = session

        result = client.get(f"/v1/copilot/sessions/{session.id}")

        assert result.status_code == 200
        data = result.json()
        assert data["id"] == str(session.id)
        assert data["application_id"] == str(session.application_id)
        assert data["correlation_id"] == session.correlation_id

    def test_passes_session_id_to_service(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        mock_copilot_service.get_session.return_value = session
        client.get(f"/v1/copilot/sessions/{session.id}")
        call_args = mock_copilot_service.get_session.call_args.args
        assert call_args[-1] == session.id

    def test_returns_404_when_not_found(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session_id = uuid4()
        mock_copilot_service.get_session.side_effect = NotFoundError("CopilotSession", session_id)
        result = client.get(f"/v1/copilot/sessions/{session_id}")
        assert result.status_code == 404

    def test_returns_403_without_permission(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        mock_copilot_service.get_session.side_effect = AuthorizationError(
            message="Permission denied: 'query:copilot' is required",
            required_permission="query:copilot",
        )
        result = client.get(f"/v1/copilot/sessions/{uuid4()}")
        assert result.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/copilot/sessions/{session_id}/history
# ---------------------------------------------------------------------------


class TestGetCopilotHistory:
    def test_returns_200_with_ordered_history(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        response = make_copilot_response(query_id=query.id)
        mock_copilot_service.get_session.return_value = session
        mock_copilot_service.get_history.return_value = [(query, response)]

        result = client.get(f"/v1/copilot/sessions/{session.id}/history")

        assert result.status_code == 200
        data = result.json()
        assert data["session_id"] == str(session.id)
        assert len(data["items"]) == 1
        assert data["items"][0]["question"] == query.question_text
        assert data["items"][0]["response"]["answer"] == response.answer_text

    def test_query_without_response_yields_null_response(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        query = make_copilot_query(session_id=session.id)
        mock_copilot_service.get_session.return_value = session
        mock_copilot_service.get_history.return_value = [(query, None)]

        result = client.get(f"/v1/copilot/sessions/{session.id}/history")

        assert result.json()["items"][0]["response"] is None

    def test_empty_history_returns_empty_items(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        mock_copilot_service.get_session.return_value = session
        mock_copilot_service.get_history.return_value = []

        result = client.get(f"/v1/copilot/sessions/{session.id}/history")

        assert result.json()["items"] == []

    def test_returns_404_when_session_not_found(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session_id = uuid4()
        mock_copilot_service.get_session.side_effect = NotFoundError("CopilotSession", session_id)
        result = client.get(f"/v1/copilot/sessions/{session_id}/history")
        assert result.status_code == 404


# ---------------------------------------------------------------------------
# GET /v1/applications/{application_id}/copilot
# ---------------------------------------------------------------------------


class TestGetLatestCopilotSession:
    def test_returns_200_with_latest_session(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        session = make_copilot_session()
        mock_copilot_service.get_latest_session_for_application.return_value = session

        result = client.get(f"/v1/applications/{TEST_APP_ID}/copilot")

        assert result.status_code == 200
        assert result.json()["id"] == str(session.id)

    def test_passes_application_id_and_tenant_id(
        self,
        client: TestClient,
        mock_copilot_service: MagicMock,
        current_user: AuthenticatedUser,
    ) -> None:
        session = make_copilot_session()
        mock_copilot_service.get_latest_session_for_application.return_value = session

        client.get(f"/v1/applications/{TEST_APP_ID}/copilot")

        call = mock_copilot_service.get_latest_session_for_application
        assert call.call_args.args[1] == TEST_APP_ID
        assert call.call_args.kwargs["tenant_id"] == current_user.tenant_id

    def test_returns_404_when_no_session_exists_yet(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        mock_copilot_service.get_latest_session_for_application.side_effect = NotFoundError(
            "CopilotSession", TEST_APP_ID
        )
        result = client.get(f"/v1/applications/{TEST_APP_ID}/copilot")
        assert result.status_code == 404

    def test_returns_422_for_cross_tenant_application(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        mock_copilot_service.get_latest_session_for_application.side_effect = ScopeViolationError(
            "Application does not belong to the requesting tenant"
        )
        result = client.get(f"/v1/applications/{TEST_APP_ID}/copilot")
        assert result.status_code == 422

    def test_returns_403_without_permission(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        mock_copilot_service.get_latest_session_for_application.side_effect = AuthorizationError(
            message="Permission denied: 'query:copilot' is required",
            required_permission="query:copilot",
        )
        result = client.get(f"/v1/applications/{TEST_APP_ID}/copilot")
        assert result.status_code == 403


# ---------------------------------------------------------------------------
# RBAC: role coverage sanity (documents that QUERY_COPILOT-bearing roles exist)
# ---------------------------------------------------------------------------


class TestQueryCopilotRoleCoverage:
    def test_underwriter_role_can_call_endpoint(
        self, client: TestClient, mock_copilot_service: MagicMock
    ) -> None:
        client.app.dependency_overrides[get_current_user] = lambda: make_user(Role.UNDERWRITER)
        session = make_copilot_session(tenant_id=TEST_TENANT_ID)
        mock_copilot_service.get_session.return_value = session
        result = client.get(f"/v1/copilot/sessions/{session.id}")
        assert result.status_code == 200
