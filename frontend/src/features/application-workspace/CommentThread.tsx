/**
 * Comment thread for a Finding's review (Collaboration, spec 005-enterprise-
 * platform §9). Mounted as a third FindingCard disclosure, alongside the
 * existing "AI details"/"Review history" — same collapsed-by-default
 * pattern, not a new UI primitive.
 *
 * Scoped to one Finding's Review Session (`ReviewComment.review_session_id`)
 * — ground truth confirmed against the backend before this was built: this
 * is discussion about this specific finding's review, not an application-
 * wide thread.
 */

import { useState } from 'react';

import { useAuthUser } from '@app/auth/authProvider';
import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import { Textarea } from '@design-system/components/Textarea';
import {
  useCommentsForFinding,
  useDeleteComment,
  useEditComment,
  usePostComment,
} from '@entities/comment/queries';
import type { ReviewComment } from '@entities/comment/types';

const EDIT_WINDOW_MS = 5 * 60 * 1000;

function canStillEdit(comment: ReviewComment): boolean {
  return Date.now() - new Date(comment.createdAt).getTime() < EDIT_WINDOW_MS;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown error';
}

function CommentRow({ comment, findingId }: { comment: ReviewComment; findingId: string }) {
  const currentUser = useAuthUser();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(comment.commentText);
  const editComment = useEditComment();
  const deleteComment = useDeleteComment();
  const addToast = useUiStore((state) => state.addToast);

  if (comment.deletedAt !== null) {
    return <li className="text-caption text-text-tertiary italic">Comment deleted.</li>;
  }

  const isAuthor = currentUser !== null && currentUser.userId === comment.authorUserId;

  return (
    <li className="flex flex-col gap-1">
      {editing ? (
        <div className="flex flex-col gap-1.5">
          <Textarea value={draft} onChange={(e) => { setDraft(e.target.value); }} rows={2} />
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              loading={editComment.isPending}
              onClick={() => {
                editComment.mutate(
                  { findingId, commentId: comment.id, commentText: draft },
                  {
                    onSuccess: () => { setEditing(false); },
                    onError: (error: unknown) =>
                      addToast({
                        title: 'Failed to save edit',
                        description: errorMessage(error),
                        variant: 'error',
                      }),
                  },
                );
              }}
            >
              Save
            </Button>
            <Button variant="secondary" size="sm" onClick={() => { setEditing(false); }}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-body text-text-primary">{comment.commentText}</p>
          <div className="flex items-center gap-2">
            <span className="text-caption text-text-tertiary">
              {new Date(comment.createdAt).toLocaleString()}
              {comment.editedAt !== null && ' (edited)'}
            </span>
            {isAuthor && canStillEdit(comment) && (
              <button
                type="button"
                onClick={() => { setEditing(true); }}
                className="text-caption text-text-secondary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
              >
                Edit
              </button>
            )}
            {isAuthor && (
              <button
                type="button"
                onClick={() => {
                  deleteComment.mutate(
                    { findingId, commentId: comment.id },
                    {
                      onError: (error: unknown) =>
                        addToast({
                          title: 'Failed to delete comment',
                          description: errorMessage(error),
                          variant: 'error',
                        }),
                    },
                  );
                }}
                className="text-caption text-text-secondary hover:text-feedback-error-fg outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
              >
                Delete
              </button>
            )}
          </div>
        </>
      )}
    </li>
  );
}

export function CommentThread({ findingId }: { findingId: string }) {
  const commentsQuery = useCommentsForFinding(findingId);
  const postComment = usePostComment();
  const addToast = useUiStore((state) => state.addToast);
  const [draft, setDraft] = useState('');

  if (commentsQuery.isPending) {
    return <Skeleton className="h-12 w-full" />;
  }
  if (commentsQuery.isError) {
    return (
      <ErrorState
        title="Could not load comments"
        description={errorMessage(commentsQuery.error)}
        onRetry={() => void commentsQuery.refetch()}
      />
    );
  }

  const comments = commentsQuery.data.items;

  return (
    <div className="flex flex-col gap-3">
      {comments.length === 0 ? (
        <p className="text-caption text-text-tertiary">No comments yet on this finding.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {comments.map((comment) => (
            <CommentRow key={comment.id} comment={comment} findingId={findingId} />
          ))}
        </ul>
      )}
      <div className="flex flex-col gap-1.5">
        <Textarea
          aria-label="Add a comment"
          value={draft}
          onChange={(e) => { setDraft(e.target.value); }}
          placeholder="Ask a question or leave a note about this finding…"
          rows={2}
        />
        <Button
          variant="secondary"
          size="sm"
          className="self-end"
          disabled={draft.trim().length === 0}
          loading={postComment.isPending}
          onClick={() => {
            postComment.mutate(
              { findingId, commentText: draft },
              {
                onSuccess: () => { setDraft(''); },
                onError: (error: unknown) =>
                  addToast({
                    title: 'Failed to post comment',
                    description: errorMessage(error),
                    variant: 'error',
                  }),
              },
            );
          }}
        >
          Comment
        </Button>
      </div>
    </div>
  );
}
