/**
 * Collaboration query/mutation hooks (spec 005-enterprise-platform §9).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { reviewCommentSchema } from './types';
import type { ReviewComment } from './types';

const reviewCommentListResponseSchema = z.object({ items: z.array(reviewCommentSchema) });

export function useCommentsForFinding(findingId: string) {
  return useEntityQuery({
    queryKey: ['comments', 'byFinding', findingId],
    url: `/findings/${findingId}/comments`,
    schema: reviewCommentListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export interface PostCommentInput {
  readonly findingId: string;
  readonly commentText: string;
  readonly mentionedUserIds?: readonly string[];
}

export function usePostComment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PostCommentInput): Promise<ReviewComment> => {
      const response = await httpClient.post<unknown>(`/findings/${input.findingId}/comments`, {
        comment_text: input.commentText,
        mentioned_user_ids: input.mentionedUserIds ?? [],
      });
      return reviewCommentSchema.parse(response.data);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ['comments', 'byFinding', variables.findingId],
      });
    },
  });
}

export interface EditCommentInput {
  readonly findingId: string;
  readonly commentId: string;
  readonly commentText: string;
}

export function useEditComment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: EditCommentInput): Promise<ReviewComment> => {
      const response = await httpClient.patch<unknown>(`/comments/${input.commentId}`, {
        comment_text: input.commentText,
      });
      return reviewCommentSchema.parse(response.data);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ['comments', 'byFinding', variables.findingId],
      });
    },
  });
}

export interface DeleteCommentInput {
  readonly findingId: string;
  readonly commentId: string;
}

export function useDeleteComment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: DeleteCommentInput): Promise<ReviewComment> => {
      const response = await httpClient.delete<unknown>(`/comments/${input.commentId}`);
      return reviewCommentSchema.parse(response.data);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ['comments', 'byFinding', variables.findingId],
      });
    },
  });
}
