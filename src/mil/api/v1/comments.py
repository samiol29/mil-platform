"""
Collaboration REST endpoints — MIL API v1 (spec 005-enterprise-platform §9).

Endpoints:
    POST   /v1/findings/{finding_id}/comments            Post a comment on a Finding's review
    GET    /v1/findings/{finding_id}/comments             List comments for a Finding's review
    PATCH  /v1/comments/{comment_id}                       Edit a comment (author, within 5 min)
    DELETE /v1/comments/{comment_id}                       Soft-delete a comment (author only)

Ground truth (confirmed before this route was written): `ReviewComment` is
scoped by `review_session_id` — i.e. discussion attaches to one Finding's
review, not an application-wide thread. A comment can only be posted once a
Review Session exists for the Finding (a 404, not a silently-created one).

Route handlers are thin; `ReviewService`'s new methods
(`post_comment`/`get_comments_for_finding`/`get_comment`/`edit_comment`/
`delete_comment`) self-check `comment:finding` permission, matching the
`CopilotService`/`IdentityService`/`PolicyService` (new methods) convention.

Dependency rule: imports from `mil.api.deps`, `mil.api.v1.schemas`, FastAPI,
and the Python standard library only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, status

from mil.api.deps import CurrentUser, NotificationServiceDep, ReviewServiceDep  # noqa: TC001
from mil.api.v1.schemas import (
    EditCommentRequest,
    PostCommentRequest,
    ReviewCommentListResponse,
    ReviewCommentResponse,
)

if TYPE_CHECKING:
    from mil.review.models import ReviewComment

router = APIRouter(tags=["Collaboration"])


def _comment_response(comment: ReviewComment) -> ReviewCommentResponse:
    return ReviewCommentResponse(
        id=comment.id,
        review_session_id=comment.review_session_id,
        author_user_id=comment.author_user_id,
        comment_text=comment.comment_text,
        mentioned_user_ids=comment.mentioned_user_ids,
        edited_at=comment.edited_at,
        deleted_at=comment.deleted_at,
        created_at=comment.created_at,
    )


@router.post(
    "/v1/findings/{finding_id}/comments",
    summary="Post a comment on a Finding's review",
    response_model=ReviewCommentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "No Review Session exists yet for this Finding"},
    },
)
def post_comment(
    finding_id: UUID,
    body: PostCommentRequest,
    user: CurrentUser,
    service: ReviewServiceDep,
    notifications: NotificationServiceDep,
) -> ReviewCommentResponse:
    comment, audit_event_id = service.post_comment(
        user,
        finding_id,
        comment_text=body.comment_text,
        mentioned_user_ids=body.mentioned_user_ids,
    )
    # spec 005-enterprise-platform §13 (Wave 2): notify every @-mentioned
    # user, pointing at the exact audit event this comment already wrote —
    # no separate notification payload invented.
    for mentioned_user_id in body.mentioned_user_ids:
        notifications.notify(
            tenant_id=user.tenant_id,
            recipient_user_id=mentioned_user_id,
            audit_event_id=audit_event_id,
        )
    return _comment_response(comment)


@router.get(
    "/v1/findings/{finding_id}/comments",
    summary="List comments on a Finding's review",
    response_model=ReviewCommentListResponse,
)
def list_comments(
    finding_id: UUID, user: CurrentUser, service: ReviewServiceDep
) -> ReviewCommentListResponse:
    comments = service.get_comments_for_finding(user, finding_id)
    return ReviewCommentListResponse(items=[_comment_response(c) for c in comments])


@router.patch(
    "/v1/comments/{comment_id}",
    summary="Edit a comment (author only, within the edit window)",
    response_model=ReviewCommentResponse,
    responses={
        403: {"description": "Not the comment's author"},
        404: {"description": "Comment not found"},
        409: {"description": "Edit window elapsed, or comment already deleted"},
    },
)
def edit_comment(
    comment_id: UUID,
    body: EditCommentRequest,
    user: CurrentUser,
    service: ReviewServiceDep,
) -> ReviewCommentResponse:
    comment = service.get_comment(user, comment_id)
    edited = service.edit_comment(user, comment, body.comment_text)
    return _comment_response(edited)


@router.delete(
    "/v1/comments/{comment_id}",
    summary="Soft-delete a comment (author only)",
    response_model=ReviewCommentResponse,
    responses={
        403: {"description": "Not the comment's author"},
        404: {"description": "Comment not found"},
    },
)
def delete_comment(
    comment_id: UUID, user: CurrentUser, service: ReviewServiceDep
) -> ReviewCommentResponse:
    comment = service.get_comment(user, comment_id)
    deleted = service.delete_comment(user, comment)
    return _comment_response(deleted)
