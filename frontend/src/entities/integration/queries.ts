/**
 * LOS Integration query/mutation hooks (spec 005-enterprise-platform §2,
 * Wave 2).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { losConnectionSchema, losSyncEventSchema } from './types';
import type { LOSConnection, LOSSyncEvent } from './types';

const losConnectionListResponseSchema = z.object({ items: z.array(losConnectionSchema) });
const losSyncEventListResponseSchema = z.object({ items: z.array(losSyncEventSchema) });

export function useLOSConnections() {
  return useEntityQuery({
    queryKey: ['integration', 'connections'],
    url: '/integrations/los/connections',
    schema: losConnectionListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export function useLOSSyncFailures() {
  return useEntityQuery({
    queryKey: ['integration', 'sync-events', 'failures'],
    url: '/integrations/los/sync-events?outcome=FAILURE',
    schema: losSyncEventListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export function useApplicationSyncEvents(applicationId: string) {
  return useEntityQuery({
    queryKey: ['integration', 'sync-events', 'byApplication', applicationId],
    url: `/applications/${applicationId}/los-sync-events`,
    schema: losSyncEventListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export function useCreateLOSConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (vendorType: string): Promise<LOSConnection> => {
      const response = await httpClient.post<unknown>('/integrations/los/connections', {
        vendor_type: vendorType,
      });
      return losConnectionSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['integration', 'connections'] });
    },
  });
}

export function useSyncApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (applicationId: string): Promise<LOSSyncEvent> => {
      const response = await httpClient.post<unknown>(`/applications/${applicationId}/los-sync`);
      return losSyncEventSchema.parse(response.data);
    },
    onSuccess: async (_data, applicationId) => {
      await queryClient.invalidateQueries({
        queryKey: ['integration', 'sync-events', 'byApplication', applicationId],
      });
    },
  });
}

export interface PushReadinessInput {
  readonly applicationId: string;
  readonly isReady: boolean;
  readonly summary: string;
  readonly missingItems?: readonly string[];
}

export function usePushReadiness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PushReadinessInput): Promise<LOSSyncEvent> => {
      const response = await httpClient.post<unknown>(
        `/applications/${input.applicationId}/los-push`,
        {
          is_ready: input.isReady,
          summary: input.summary,
          missing_items: input.missingItems ?? [],
        },
      );
      return losSyncEventSchema.parse(response.data);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ['integration', 'sync-events', 'byApplication', variables.applicationId],
      });
    },
  });
}
