/**
 * Application query hooks (spec 002 tasks.md T053).
 *
 * Single-record read is the only *feature* query here — the paginated/
 * filtered/sorted Application Queue is tasks.md T075 (User Story 2), built
 * once the backend's search/queue endpoint (T073) exists.
 *
 * `useApplications` below is NOT that queue query: it calls the existing
 * bare `GET /v1/applications` (no filters, no sorting, no pagination, no
 * queue-row aggregate fields) solely so the `/` route has a real entry
 * point instead of a static placeholder. It is deliberately not exported
 * for reuse outside `routes/index.tsx` — do not build queue UI against it.
 */

import { z } from 'zod';

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

/**
 * `GET /v1/applications`'s actual response shape
 * (`src/mil/api/v1/schemas.py::ApplicationListResponse`) — a paginated
 * envelope, not a bare array. Only `items` is used here; `total`/`page`/
 * `page_size` belong to the eventual queue view (tasks.md T075), not this
 * bootstrap redirect.
 */
const applicationListResponseSchema = z.object({
  items: z.array(applicationSchema),
});

/**
 * Fetch the bare application list (see module docstring — bootstrap use
 * only, for the `/` route's entry-point redirect, not a queue view).
 */
export function useApplications() {
  return useEntityQuery({
    queryKey: ['applications', 'bootstrap-entry-point'],
    url: '/applications',
    schema: applicationListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export type { Application };
