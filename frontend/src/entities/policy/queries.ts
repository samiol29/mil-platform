/**
 * Policy Engine / Policy Administration query/mutation hooks
 * (spec 005-enterprise-platform §3/§4).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import {
  policyPackApprovalSchema,
  policyPackSchema,
  policyResultSchema,
  policyRuleSchema,
} from './types';
import type { PolicyPack, PolicyPackApproval, PolicyRule } from './types';

const policyResultListResponseSchema = z.object({ items: z.array(policyResultSchema) });
const policyPackListResponseSchema = z.object({ items: z.array(policyPackSchema) });
const policyPackApprovalListResponseSchema = z.object({
  items: z.array(policyPackApprovalSchema),
});

export function useApplicationPolicyResults(applicationId: string) {
  return useEntityQuery({
    queryKey: ['policy-results', 'byApplication', applicationId],
    url: `/applications/${applicationId}/policy-results`,
    schema: policyResultListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export function usePolicyPacks() {
  return useEntityQuery({
    queryKey: ['policy-packs'],
    url: '/policy-packs',
    schema: policyPackListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export function usePolicyPackRules(policyPackId: string | null) {
  return useEntityQuery({
    queryKey: ['policy-packs', policyPackId, 'rules'],
    url: `/policy-packs/${policyPackId ?? ''}/rules`,
    schema: z.array(policyRuleSchema),
    staleTime: STALE_TIME.informational,
    enabled: policyPackId !== null,
  });
}

export function usePolicyPackApprovals(policyPackId: string | null) {
  return useEntityQuery({
    queryKey: ['policy-packs', policyPackId, 'approvals'],
    url: `/policy-packs/${policyPackId ?? ''}/approvals`,
    schema: policyPackApprovalListResponseSchema,
    staleTime: STALE_TIME.informational,
    enabled: policyPackId !== null,
  });
}

export interface CreatePolicyPackInput {
  readonly version: string;
  readonly name: string;
  readonly contentHash: string;
  readonly jurisdiction?: string;
}

export function useCreatePolicyPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreatePolicyPackInput): Promise<PolicyPack> => {
      const response = await httpClient.post<unknown>('/policy-packs', {
        version: input.version,
        name: input.name,
        content_hash: input.contentHash,
        jurisdiction: input.jurisdiction,
      });
      return policyPackSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['policy-packs'] });
    },
  });
}

export interface AddPolicyRuleInput {
  readonly policyPackId: string;
  readonly ruleKey: string;
  readonly name: string;
  readonly description: string;
  readonly severity: string;
}

export function useAddPolicyRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: AddPolicyRuleInput): Promise<PolicyRule> => {
      const response = await httpClient.post<unknown>(`/policy-packs/${input.policyPackId}/rules`, {
        rule_key: input.ruleKey,
        name: input.name,
        description: input.description,
        severity: input.severity,
      });
      return policyRuleSchema.parse(response.data);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ['policy-packs', variables.policyPackId, 'rules'],
      });
    },
  });
}

export function useSubmitPolicyPackForApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (policyPackId: string): Promise<PolicyPackApproval> => {
      const response = await httpClient.post<unknown>(
        `/policy-packs/${policyPackId}/submit-for-approval`,
      );
      return policyPackApprovalSchema.parse(response.data);
    },
    onSuccess: async (_data, policyPackId) => {
      await queryClient.invalidateQueries({ queryKey: ['policy-packs', policyPackId, 'approvals'] });
    },
  });
}

export function useApprovePolicyPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (approvalId: string): Promise<PolicyPackApproval> => {
      const response = await httpClient.post<unknown>(
        `/policy-pack-approvals/${approvalId}/approve`,
      );
      return policyPackApprovalSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['policy-packs'] });
    },
  });
}

export interface RejectPolicyPackInput {
  readonly approvalId: string;
  readonly reason: string;
}

export function useRejectPolicyPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: RejectPolicyPackInput): Promise<PolicyPackApproval> => {
      const response = await httpClient.post<unknown>(
        `/policy-pack-approvals/${input.approvalId}/reject`,
        { reason: input.reason },
      );
      return policyPackApprovalSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['policy-packs'] });
    },
  });
}

export function useActivatePolicyPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (policyPackId: string): Promise<PolicyPack> => {
      const response = await httpClient.post<unknown>(`/policy-packs/${policyPackId}/activate`);
      return policyPackSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['policy-packs'] });
    },
  });
}
