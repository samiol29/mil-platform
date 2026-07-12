/**
 * AI Case Copilot query/mutation hooks (spec 005-enterprise-platform §8).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';

import { copilotHistorySchema, copilotResponseSchema, copilotSessionSchema } from './types';
import type { CopilotHistory, CopilotSession } from './types';

/**
 * The latest Copilot session for an application, or `null` if none exists
 * yet (`GET /v1/applications/{id}/copilot` returns a real 404 in that case
 * — the honest "no conversation yet" state, not an error to surface).
 */
export function useLatestCopilotSession(applicationId: string) {
  return useQuery<CopilotSession | null>({
    queryKey: ['copilot', 'latestSession', applicationId],
    queryFn: async () => {
      try {
        const response = await httpClient.get<unknown>(`/applications/${applicationId}/copilot`);
        return copilotSessionSchema.parse(response.data);
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return null;
        }
        throw error;
      }
    },
    staleTime: STALE_TIME.informational,
  });
}

export function useCopilotHistory(sessionId: string | null) {
  return useQuery<CopilotHistory>({
    queryKey: ['copilot', 'history', sessionId],
    queryFn: async () => {
      const response = await httpClient.get<unknown>(
        `/copilot/sessions/${sessionId ?? ''}/history`,
      );
      return copilotHistorySchema.parse(response.data);
    },
    staleTime: STALE_TIME.informational,
    enabled: sessionId !== null,
  });
}

export interface SubmitCopilotQueryInput {
  readonly applicationId: string;
  readonly sessionId?: string;
  readonly question: string;
}

export function useSubmitCopilotQuery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SubmitCopilotQueryInput) => {
      const response = await httpClient.post<unknown>('/copilot/query', {
        application_id: input.applicationId,
        session_id: input.sessionId,
        question: input.question,
      });
      return copilotResponseSchema.parse(response.data);
    },
    onSuccess: async (data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ['copilot', 'latestSession', variables.applicationId],
      });
      await queryClient.invalidateQueries({ queryKey: ['copilot', 'history', data.sessionId] });
    },
  });
}
