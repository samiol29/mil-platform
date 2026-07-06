/**
 * Finding query + mutation hooks (spec 002 tasks.md T059).
 *
 * Confirmed writes only — no optimistic update, per this task's own
 * instruction and Constitution Principle I (a verification/override is a
 * human decision of record; the UI must reflect the server's confirmed
 * result, never an assumed one). `useEscalateFinding` follows the same
 * confirmed-write pattern.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { STALE_TIME } from '@app/queryClient';
import { httpClient } from '@app/auth/httpClient';

import { findingSchema, type Finding } from './types';

function findingsQueryKey(applicationId: string) {
  return ['findings', 'byApplication', applicationId] as const;
}

/**
 * List every finding for an application.
 *
 * Caching tier: audit-critical — a Finding is never rendered from a cache
 * that cannot supply all five explainability fields (data-model.md); Zod
 * parsing enforces this structurally, not just by convention.
 */
export function useFindingsForApplication(applicationId: string) {
  return useQuery({
    queryKey: findingsQueryKey(applicationId),
    queryFn: async () => {
      const response = await httpClient.get<unknown>(`/applications/${applicationId}/findings`);
      return findingSchema.array().parse(response.data);
    },
    staleTime: STALE_TIME.auditCritical,
  });
}

export function useVerifyFinding(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (findingId: string) => {
      const response = await httpClient.post<unknown>(`/findings/${findingId}/verify`);
      return findingSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: findingsQueryKey(applicationId) });
    },
  });
}

export interface OverrideFindingInput {
  readonly findingId: string;
  readonly reason: string;
  readonly previousValue: string;
  readonly newValue: string;
}

export function useOverrideFinding(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: OverrideFindingInput) => {
      const response = await httpClient.post<unknown>(`/findings/${input.findingId}/override`, {
        reason: input.reason,
        previous_value: input.previousValue,
        new_value: input.newValue,
      });
      return findingSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: findingsQueryKey(applicationId) });
    },
  });
}

export interface EscalateFindingInput {
  readonly findingId: string;
  readonly reason: string;
  readonly targetRole: string;
  readonly targetUserId?: string;
}

/**
 * Escalate a finding to another role's (or, optionally, a specific
 * person's) queue (spec 002 FR-054). Non-terminal on the server: the
 * escalated finding remains resolvable via `useVerifyFinding`/
 * `useOverrideFinding`, restricted server-side to the target role/person.
 */
export function useEscalateFinding(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: EscalateFindingInput) => {
      const response = await httpClient.post<unknown>(`/findings/${input.findingId}/escalate`, {
        reason: input.reason,
        target_role: input.targetRole,
        target_user_id: input.targetUserId ?? null,
      });
      return findingSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: findingsQueryKey(applicationId) });
    },
  });
}

export type { Finding };
