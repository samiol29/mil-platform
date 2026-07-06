/**
 * Application query hooks (spec 002 tasks.md T053).
 *
 * Single-record read only — the paginated/filtered/sorted list query for
 * the Application Queue is tasks.md T075 (User Story 2), built once the
 * backend's search/queue endpoint (T073) exists.
 */

import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { applicationSchema, type Application } from './types';

/**
 * Fetch one application by id.
 *
 * Caching tier: "informational" while browsing, but the caller must treat
 * it as audit-critical (re-check freshness, `STALE_TIME.auditCritical`)
 * once a finding on this application is being verified/overridden
 * (data-model.md's Application caching-tier rule; 002 FR-036).
 */
export function useApplication(applicationId: string) {
  return useEntityQuery({
    queryKey: ['application', applicationId],
    url: `/applications/${applicationId}`,
    schema: applicationSchema,
    staleTime: STALE_TIME.informational,
  });
}

export type { Application };
