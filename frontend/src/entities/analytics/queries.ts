/**
 * Business Analytics query hooks (spec 005-enterprise-platform §11, Wave 3).
 */

import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { businessAnalyticsSnapshotSchema } from './types';

export function useBusinessAnalyticsSnapshot() {
  return useEntityQuery({
    queryKey: ['analytics', 'snapshot'],
    url: '/analytics/snapshot',
    schema: businessAnalyticsSnapshotSchema,
    staleTime: STALE_TIME.informational,
  });
}
