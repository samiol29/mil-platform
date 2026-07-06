/**
 * EvidenceItem query hooks (spec 002 tasks.md T057).
 */

import { useQuery } from '@tanstack/react-query';

import { STALE_TIME } from '@app/queryClient';
import { httpClient } from '@app/auth/httpClient';

import { evidenceItemSchema, type EvidenceItem, type FieldLocation } from './types';

/**
 * List every evidence item for an application.
 *
 * Caching tier: "informational" while browsing; the caller must re-check
 * freshness (`STALE_TIME.auditCritical`) once a finding referencing this
 * evidence is being verified/overridden (data-model.md's EvidenceItem
 * caching-tier rule).
 */
export function useEvidenceForApplication(applicationId: string) {
  return useQuery({
    queryKey: ['evidence', 'byApplication', applicationId],
    queryFn: async () => {
      const response = await httpClient.get<unknown>(`/applications/${applicationId}/evidence`);
      return evidenceItemSchema.array().parse(response.data);
    },
    staleTime: STALE_TIME.informational,
  });
}

export type { EvidenceItem, FieldLocation };
