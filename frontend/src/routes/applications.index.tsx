/**
 * Application Queue route (Product Experience phase, Phase 1) — `/applications`,
 * the detailed operational view. `status` is URL search-param state so a
 * Dashboard workload card or a bookmarked link can land directly on a
 * filtered queue, matching the same "active tab/filter is URL state"
 * convention `applications.$applicationId.tsx` already uses for its region.
 */

import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';

import { ApplicationQueueTable } from '@features/application-queue/ApplicationQueueTable';
import type { ApplicationStatus } from '@entities/application/types';

const searchSchema = z.object({
  status: z.enum(['DRAFT', 'SUBMITTED', 'IN_REVIEW', 'REVIEW_COMPLETE', 'WITHDRAWN']).optional(),
});

export const Route = createFileRoute('/applications/')({
  validateSearch: searchSchema,
  component: ApplicationQueueRoute,
});

function ApplicationQueueRoute() {
  const { status } = Route.useSearch();
  const navigate = Route.useNavigate();

  return (
    <ApplicationQueueTable
      status={status ?? null}
      onStatusChange={(next: ApplicationStatus | null) => {
        void navigate({ search: { status: next ?? undefined } });
      }}
    />
  );
}
