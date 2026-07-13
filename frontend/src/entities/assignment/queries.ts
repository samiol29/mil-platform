/**
 * Assignment query/mutation hooks (spec 005-enterprise-platform §1, Wave 2).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { applicationListResponseSchema } from '@entities/application/queries';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { assignmentHistorySchema, assignmentSchema } from './types';
import type { Assignment } from './types';

export function useAssignment(applicationId: string) {
  return useEntityQuery({
    queryKey: ['assignment', applicationId],
    url: `/applications/${applicationId}/assignment`,
    schema: assignmentSchema.nullable(),
    staleTime: STALE_TIME.informational,
  });
}

export function useAssignmentHistory(applicationId: string) {
  return useEntityQuery({
    queryKey: ['assignment', applicationId, 'history'],
    url: `/applications/${applicationId}/assignment-history`,
    schema: z.object({ items: z.array(assignmentHistorySchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export function useRmPortfolio() {
  return useEntityQuery({
    queryKey: ['rm', 'portfolio'],
    url: '/rm/portfolio',
    schema: applicationListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export interface SetAssignmentInput {
  readonly applicationId: string;
  readonly ownerUserId: string;
  readonly reviewerUserId?: string;
}

export function useSetAssignment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SetAssignmentInput): Promise<Assignment> => {
      const response = await httpClient.put<unknown>(
        `/applications/${input.applicationId}/assignment`,
        { owner_user_id: input.ownerUserId, reviewer_user_id: input.reviewerUserId },
      );
      return assignmentSchema.parse(response.data);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['assignment', variables.applicationId] });
      await queryClient.invalidateQueries({ queryKey: ['rm', 'portfolio'] });
    },
  });
}
