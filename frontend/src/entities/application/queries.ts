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
 *
 * `useApplicationSearch` (Product Experience phase, Phase 1) IS the queue/
 * search query: it consumes the backend's new optional `search` and
 * existing `status` query params on `GET /v1/applications`. This is the
 * hook the Application Queue table and Global Search both build on.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
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
export const applicationListResponseSchema = z.object({
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

export interface ApplicationSearchParams {
  /** Case-insensitive substring match against LOS reference, loan number, application ID, or borrower display name. */
  readonly search?: string;
  readonly status?: Application['status'];
  /** Set `false` to skip the request entirely (e.g. Global Search below a minimum query length). Defaults to `true`. */
  readonly enabled?: boolean;
}

/**
 * Queue/search query (Product Experience phase, Phase 1) — `GET
 * /v1/applications` with the optional `search`/`status` query params. Both
 * are omitted from the request entirely when not provided, so this hook
 * degrades to the same bare list request `useApplications` makes. Also
 * powers the Command Palette's Global Search (Phase 1) via `enabled`.
 */
export function useApplicationSearch(params: ApplicationSearchParams = {}) {
  const query = new URLSearchParams();
  if (params.search !== undefined && params.search.length > 0) {
    query.set('search', params.search);
  }
  if (params.status !== undefined) {
    query.set('status', params.status);
  }
  const queryString = query.toString();
  const url = queryString.length > 0 ? `/applications?${queryString}` : '/applications';

  return useEntityQuery({
    queryKey: ['applications', 'search', params.search ?? null, params.status ?? null],
    url,
    schema: applicationListResponseSchema,
    staleTime: STALE_TIME.informational,
    enabled: params.enabled ?? true,
  });
}

export interface CreateApplicationInput {
  readonly losReference: string;
  readonly loanNumber?: string;
}

/**
 * Create a new application (Product Experience phase, Phase 2's intake
 * wizard). Invalidates every `['applications', ...]`-prefixed query — the
 * Dashboard, Queue, and Global Search queries all key off that same
 * prefix, so one predicate invalidation refreshes all of them.
 */
export function useCreateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateApplicationInput) => {
      const response = await httpClient.post<unknown>('/applications', {
        los_reference: input.losReference,
        loan_number: input.loanNumber,
      });
      return applicationSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['applications'] });
    },
  });
}

export type { Application };
