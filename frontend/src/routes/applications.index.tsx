/**
 * Application Queue route (Product Experience phase, Phase 1) — `/applications`,
 * the detailed operational view. `status` is URL search-param state so a
 * Dashboard workload card or a bookmarked link can land directly on a
 * filtered queue, matching the same "active tab/filter is URL state"
 * convention `applications.$applicationId.tsx` already uses for its region.
 */

import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';

import {
  ApplicationQueueTable,
  type AttentionFilterKey,
} from '@features/application-queue/ApplicationQueueTable';
import type { ApplicationStatus } from '@entities/application/types';

const searchSchema = z.object({
  status: z.enum(['DRAFT', 'SUBMITTED', 'IN_REVIEW', 'REVIEW_COMPLETE', 'WITHDRAWN']).optional(),
  assignedToMe: z.boolean().optional(),
  escalated: z.boolean().optional(),
});

export const Route = createFileRoute('/applications/')({
  validateSearch: searchSchema,
  component: ApplicationQueueRoute,
});

function ApplicationQueueRoute() {
  const { status, assignedToMe, escalated } = Route.useSearch();
  const navigate = Route.useNavigate();
  const attentionFilterActive: Record<AttentionFilterKey, boolean> = {
    assignedToMe: assignedToMe ?? false,
    escalated: escalated ?? false,
  };

  return (
    <ApplicationQueueTable
      status={status ?? null}
      onStatusChange={(next: ApplicationStatus | null) => {
        void navigate({ search: (prev) => ({ ...prev, status: next ?? undefined }) });
      }}
      assignedToMe={attentionFilterActive.assignedToMe}
      escalated={attentionFilterActive.escalated}
      onAttentionFilterToggle={(key: AttentionFilterKey) => {
        const next = !attentionFilterActive[key];
        void navigate({ search: (prev) => ({ ...prev, [key]: next ? true : undefined }) });
      }}
    />
  );
}
