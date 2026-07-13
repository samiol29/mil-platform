/**
 * LOS Integration entities (spec 005-enterprise-platform §2, Wave 2).
 * Matches `src/mil/api/v1/schemas.py`'s `LOSConnectionResponse`/
 * `LOSSyncEventResponse` exactly.
 */

import { z } from 'zod';

export const losConnectionSchema = z.object({
  id: z.uuid(),
  tenantId: z.uuid(),
  vendorType: z.string(),
  status: z.enum(['ACTIVE', 'PAUSED']),
  createdByUserId: z.uuid(),
  createdAt: z.iso.datetime(),
});

export type LOSConnection = z.infer<typeof losConnectionSchema>;

export const losSyncEventSchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  direction: z.enum(['INBOUND', 'OUTBOUND']),
  outcome: z.enum(['SUCCESS', 'FAILURE']),
  detail: z.record(z.string(), z.unknown()),
  errorMessage: z.string().nullable(),
  initiatedByUserId: z.uuid(),
  occurredAt: z.iso.datetime(),
});

export type LOSSyncEvent = z.infer<typeof losSyncEventSchema>;
