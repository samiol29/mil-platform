/**
 * Notification query/mutation hooks (spec 005-enterprise-platform §13,
 * Wave 2).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { STALE_TIME } from '@app/queryClient';
import { httpClient } from '@app/auth/httpClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { notificationSchema } from './types';

const notificationListResponseSchema = z.object({
  items: z.array(notificationSchema),
  unreadCount: z.number().int().nonnegative(),
});

export function useNotifications() {
  return useEntityQuery({
    queryKey: ['notifications'],
    url: '/notifications',
    schema: notificationListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (notificationId: string) => {
      const response = await httpClient.post<unknown>(`/notifications/${notificationId}/read`);
      return notificationSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}
