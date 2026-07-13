/**
 * Customer Portal entities (spec 005-enterprise-platform §12, Wave 4).
 * Matches `src/mil/api/v1/schemas.py`'s `ChecklistItemResponse`/
 * `PortalStatusResponse`/`PortalSessionResponse` exactly.
 */

import { z } from 'zod';

export const checklistItemSchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  partyId: z.uuid().nullable(),
  label: z.string(),
  documentType: z.string(),
  status: z.enum(['REQUESTED', 'RECEIVED', 'WAIVED']),
  requestedByUserId: z.uuid(),
  fulfilledDocumentId: z.uuid().nullable(),
  requestedAt: z.iso.datetime(),
});

export type ChecklistItem = z.infer<typeof checklistItemSchema>;

export const portalStatusSchema = z.object({
  statusLabel: z.string(),
});

export const portalSessionSchema = z.object({
  sessionToken: z.string(),
});
