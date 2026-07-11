/**
 * Security & Compliance query/mutation hooks (spec 005-enterprise-platform
 * §16, Wave 4).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { retentionPolicySchema } from './types';
import type { RetentionPolicy } from './types';

export function useRetentionPolicies() {
  return useEntityQuery({
    queryKey: ['compliance', 'retentionPolicies'],
    url: '/compliance/retention-policies',
    schema: z.object({ items: z.array(retentionPolicySchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export interface SetRetentionPolicyInput {
  readonly dataCategory: string;
  readonly retentionPeriodDays: number;
  readonly action: 'ARCHIVE' | 'DELETE';
}

export function useSetRetentionPolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SetRetentionPolicyInput): Promise<RetentionPolicy> => {
      const response = await httpClient.put<unknown>('/compliance/retention-policies', {
        data_category: input.dataCategory,
        retention_period_days: input.retentionPeriodDays,
        action: input.action,
      });
      return retentionPolicySchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['compliance', 'retentionPolicies'] });
    },
  });
}
