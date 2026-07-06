/**
 * AuditTrailEntry query hook (spec 002 tasks.md T060).
 *
 * Read-only, by design: no mutation hook exists in this module, and none
 * should ever be added (data-model.md: an audit trail entry never changes
 * once written).
 */

import { useQuery } from '@tanstack/react-query';

import { STALE_TIME } from '@app/queryClient';
import { httpClient } from '@app/auth/httpClient';

import { auditTrailEntrySchema, type AuditTrailEntry } from './types';

/** List the full, chronologically-ordered audit trail for an application. */
export function useAuditTrail(applicationId: string) {
  return useQuery({
    queryKey: ['audit', 'byApplication', applicationId],
    queryFn: async () => {
      const response = await httpClient.get<unknown>(`/applications/${applicationId}/audit`);
      return auditTrailEntrySchema.array().parse(response.data);
    },
    // Long-lived: an append-only log never changes once written for the
    // events already fetched; new events arriving are a separate concern
    // (a future SSE/polling mechanism, out of this task's scope).
    staleTime: STALE_TIME.longLived,
  });
}

export type { AuditTrailEntry };
