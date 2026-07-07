/**
 * Party query + mutation hooks (Product Experience phase, Phase 2).
 *
 * Follows `entities/finding/queries.ts`'s established convention exactly:
 * `useMutation`/`useQuery` + `httpClient` + parse the response through the
 * entity's Zod schema + `queryClient.invalidateQueries` on success. No
 * optimistic updates — same Principle-I-derived rule `entities/finding/
 * queries.ts` documents: a party is only "added" once the server confirms
 * it, never assumed from the client's own input.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';

import { partySchema, type Party, type PartyType } from './types';

function partiesQueryKey(applicationId: string) {
  return ['parties', 'byApplication', applicationId] as const;
}

/** List every party registered against an application — feeds the Workspace Overview's `SummaryGrid`. */
export function usePartiesForApplication(applicationId: string, enabled = true) {
  return useQuery({
    queryKey: partiesQueryKey(applicationId),
    queryFn: async () => {
      const response = await httpClient.get<unknown>(`/applications/${applicationId}/parties`);
      return partySchema.array().parse(response.data);
    },
    staleTime: STALE_TIME.informational,
    enabled,
  });
}

export interface AddPartyInput {
  /**
   * Deliberately part of the mutate-time input rather than bound at
   * `useAddParty()` call time (contrast `useVerifyFinding(applicationId)`):
   * the intake wizard's application isn't created yet when this hook is
   * instantiated — it's only known once step 3's `useCreateApplication`
   * call resolves, mid-flow, so it must travel with each `.mutate()` call.
   */
  readonly applicationId: string;
  readonly partyType: PartyType;
  readonly displayName: string;
}

export function useAddParty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: AddPartyInput) => {
      const response = await httpClient.post<unknown>(
        `/applications/${input.applicationId}/parties`,
        { party_type: input.partyType, display_name: input.displayName },
      );
      return partySchema.parse(response.data);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: partiesQueryKey(variables.applicationId) });
    },
  });
}

export type { Party, PartyType };
