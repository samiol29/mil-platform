/**
 * Finding query + mutation hooks (spec 002 tasks.md T059).
 *
 * Confirmed writes only — no optimistic update, per this task's own
 * instruction and Constitution Principle I (a verification/override is a
 * human decision of record; the UI must reflect the server's confirmed
 * result, never an assumed one).
 *
 * **No `useEscalateFinding` hook exists here.** `POST /v1/findings/{id}
 * /escalate` does not exist on the backend yet (see `findings.py`'s module
 * docstring and `HANDOFF.md` for the full analysis) — a hook calling a
 * nonexistent endpoint would be exactly the kind of guessed, unreviewed
 * assumption this task was told to avoid. Add it here once that decision
 * is made and the endpoint exists.
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

export type { Finding };
