/**
 * Notification entities (spec 005-enterprise-platform §13, Wave 2).
 * Matches `src/mil/api/v1/schemas.py`'s `NotificationResponse` exactly —
 * `eventType`/`eventData`/`occurredAt` are resolved from the referenced
 * `AuditEvent` at read time, never a duplicated event model.
 */

import { z } from 'zod';

export const notificationSchema = z.object({
  id: z.uuid(),
  recipientUserId: z.uuid(),
  auditEventId: z.uuid(),
  eventType: z.string(),
  eventData: z.record(z.string(), z.unknown()),
  occurredAt: z.iso.datetime(),
  readAt: z.iso.datetime().nullable(),
  createdAt: z.iso.datetime(),
});

export type Notification = z.infer<typeof notificationSchema>;
