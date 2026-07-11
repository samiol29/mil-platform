"""Unit tests for Universal Search API endpoint (spec 005 §7, Wave 2)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003

from fastapi.testclient import TestClient  # noqa: TC002

from tests.unit.api.conftest import make_application, make_document


class TestSearch:
    def test_returns_matching_applications_and_documents(
        self, client: TestClient, mock_search_workspace: MagicMock
    ) -> None:
        app = make_application(los_reference="LOS-999")
        doc = make_document()
        mock_search_workspace.search_applications.return_value = [app]
        mock_search_workspace.search_documents.return_value = [doc]

        response = client.get("/v1/search?q=999")

        assert response.status_code == 200
        body = response.json()
        kinds = {r["kind"] for r in body["results"]}
        assert kinds == {"application", "document"}

    def test_kinds_param_narrows_results(
        self, client: TestClient, mock_search_workspace: MagicMock
    ) -> None:
        app = make_application()
        mock_search_workspace.search_applications.return_value = [app]
        mock_search_workspace.search_documents.return_value = []

        response = client.get("/v1/search?q=test&kinds=application")

        assert response.status_code == 200
        body = response.json()
        assert all(r["kind"] == "application" for r in body["results"])
        mock_search_workspace.search_documents.assert_not_called()
