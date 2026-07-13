"""Unit tests for Collaboration API endpoints (spec 005 §9)."""

from __future__ import annotations

from unittest.mock import MagicMock  # noqa: TC003
from uuid import uuid4

from fastapi.testclient import TestClient  # noqa: TC002

from mil.kernel.errors import AuthorizationError, ConflictError, NotFoundError
from mil.review.models import ReviewComment


class TestPostComment:
    def test_returns_201(self, client: TestClient, mock_review_service: MagicMock) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="please review"
        )
        mock_review_service.post_comment.return_value = (comment, uuid4())
        response = client.post(
            f"/v1/findings/{uuid4()}/comments", json={"comment_text": "please review"}
        )
        assert response.status_code == 201
        assert response.json()["comment_text"] == "please review"

    def test_no_review_session_returns_404(
        self, client: TestClient, mock_review_service: MagicMock
    ) -> None:
        mock_review_service.post_comment.side_effect = NotFoundError("ReviewSession", "x")
        response = client.post(f"/v1/findings/{uuid4()}/comments", json={"comment_text": "hi"})
        assert response.status_code == 404


class TestListComments:
    def test_returns_200(self, client: TestClient, mock_review_service: MagicMock) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="hi"
        )
        mock_review_service.get_comments_for_finding.return_value = [comment]
        response = client.get(f"/v1/findings/{uuid4()}/comments")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1


class TestEditComment:
    def test_non_author_returns_403(
        self, client: TestClient, mock_review_service: MagicMock
    ) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="hi"
        )
        mock_review_service.get_comment.return_value = comment
        mock_review_service.edit_comment.side_effect = AuthorizationError(
            "Only a comment's author may edit it."
        )
        response = client.patch(f"/v1/comments/{comment.id}", json={"comment_text": "edited"})
        assert response.status_code == 403

    def test_expired_window_returns_409(
        self, client: TestClient, mock_review_service: MagicMock
    ) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="hi"
        )
        mock_review_service.get_comment.return_value = comment
        mock_review_service.edit_comment.side_effect = ConflictError("edit window has elapsed")
        response = client.patch(f"/v1/comments/{comment.id}", json={"comment_text": "edited"})
        assert response.status_code == 409

    def test_returns_200_on_success(
        self, client: TestClient, mock_review_service: MagicMock
    ) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="hi"
        )
        comment.comment_text = "edited"
        mock_review_service.get_comment.return_value = comment
        mock_review_service.edit_comment.return_value = comment
        response = client.patch(f"/v1/comments/{comment.id}", json={"comment_text": "edited"})
        assert response.status_code == 200
        assert response.json()["comment_text"] == "edited"


class TestDeleteComment:
    def test_returns_200(self, client: TestClient, mock_review_service: MagicMock) -> None:
        comment = ReviewComment.create(
            review_session_id=uuid4(), author_user_id=uuid4(), comment_text="hi"
        )
        comment.soft_delete(comment.author_user_id)
        mock_review_service.get_comment.return_value = comment
        mock_review_service.delete_comment.return_value = comment
        response = client.delete(f"/v1/comments/{comment.id}")
        assert response.status_code == 200
        assert response.json()["deleted_at"] is not None

    def test_not_found_returns_404(
        self, client: TestClient, mock_review_service: MagicMock
    ) -> None:
        mock_review_service.get_comment.side_effect = NotFoundError("ReviewComment", uuid4())
        response = client.delete(f"/v1/comments/{uuid4()}")
        assert response.status_code == 404
