/**
 * Operational Dashboard query hooks (spec 005-enterprise-platform §10, Wave 3).
 */

import { z } from 'zod';

import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import {
  applicationFunnelRowSchema,
  jobQueueHealthSchema,
  poisonJobSchema,
  queueDepthRowSchema,
} from './types';

export function useQueueDepth() {
  return useEntityQuery({
    queryKey: ['operational', 'queueDepth'],
    url: '/operational/queue-depth',
    schema: z.object({ items: z.array(queueDepthRowSchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export function usePoisonJobs() {
  return useEntityQuery({
    queryKey: ['operational', 'poisonJobs'],
    url: '/operational/poison-jobs',
    schema: z.object({ items: z.array(poisonJobSchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export function useApplicationFunnel() {
  return useEntityQuery({
    queryKey: ['operational', 'funnel'],
    url: '/operational/funnel',
    schema: z.object({ items: z.array(applicationFunnelRowSchema) }),
    staleTime: STALE_TIME.informational,
  });
}

export function useJobQueueHealth() {
  return useEntityQuery({
    queryKey: ['operational', 'jobQueueHealth'],
    url: '/operational/job-queue-health',
    schema: jobQueueHealthSchema,
    staleTime: STALE_TIME.informational,
  });
}
