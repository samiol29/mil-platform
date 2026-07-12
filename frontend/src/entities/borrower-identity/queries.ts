/**
 * Borrower Identity Resolution query/mutation hooks (spec 005-enterprise-
 * platform §5, Wave 3).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import {
  borrowerIdentityMemberSchema,
  borrowerIdentitySchema,
  crossApplicationObservationSchema,
  identityMatchCandidateSchema,
} from './types';
import type { BorrowerIdentity, IdentityMatchCandidate } from './types';

export function useMatchCandidatesForParty(partyId: string) {
  return useEntityQuery({
    queryKey: ['borrowerIdentity', 'matchCandidates', partyId],
    url: `/parties/${partyId}/match-candidates`,
    schema: z.object({ items: z.array(identityMatchCandidateSchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export function useBorrowerIdentityForParty(partyId: string) {
  return useEntityQuery({
    queryKey: ['borrowerIdentity', 'forParty', partyId],
    url: `/parties/${partyId}/borrower-identity`,
    schema: borrowerIdentitySchema.nullable(),
    staleTime: STALE_TIME.informational,
  });
}

export function useBorrowerIdentity(identityId: string) {
  return useEntityQuery({
    queryKey: ['borrowerIdentity', identityId],
    url: `/borrower-identities/${identityId}`,
    schema: borrowerIdentitySchema,
    staleTime: STALE_TIME.informational,
  });
}

export function useBorrowerIdentityMembers(identityId: string) {
  return useEntityQuery({
    queryKey: ['borrowerIdentity', identityId, 'members'],
    url: `/borrower-identities/${identityId}/members`,
    schema: z.object({ items: z.array(borrowerIdentityMemberSchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export function useCrossApplicationSignals(identityId: string) {
  return useEntityQuery({
    queryKey: ['borrowerIdentity', identityId, 'crossApplicationSignals'],
    url: `/borrower-identities/${identityId}/cross-application-signals`,
    schema: z.object({ items: z.array(crossApplicationObservationSchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export function useComputeMatchCandidates() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (partyId: string): Promise<IdentityMatchCandidate[]> => {
      const response = await httpClient.post<unknown>(
        `/parties/${partyId}/compute-match-candidates`,
      );
      return z.object({ items: z.array(identityMatchCandidateSchema) }).parse(response.data).items;
    },
    onSuccess: async (_data, partyId) => {
      await queryClient.invalidateQueries({
        queryKey: ['borrowerIdentity', 'matchCandidates', partyId],
      });
    },
  });
}

export function useConfirmMatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (candidateId: string): Promise<BorrowerIdentity> => {
      const response = await httpClient.post<unknown>(`/match-candidates/${candidateId}/confirm`);
      return borrowerIdentitySchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['borrowerIdentity'] });
    },
  });
}

export interface RejectMatchInput {
  readonly candidateId: string;
  readonly reason?: string;
}

export function useRejectMatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: RejectMatchInput): Promise<IdentityMatchCandidate> => {
      const response = await httpClient.post<unknown>(
        `/match-candidates/${input.candidateId}/reject`,
        { reason: input.reason },
      );
      return identityMatchCandidateSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['borrowerIdentity'] });
    },
  });
}
