/**
 * Assignment entities (spec 005-enterprise-platform §1, Wave 2 — RM/Banker
 * Workspace). Matches `src/mil/api/v1/schemas.py`'s `AssignmentResponse`/
 * `AssignmentHistoryResponse` exactly.
 */

import { z } from 'zod';

export const assignmentSchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  ownerUserId: z.uuid(),
  reviewerUserId: z.uuid().nullable(),
  assignedByUserId: z.uuid(),
  assignedAt: z.iso.datetime(),
});

export type Assignment = z.infer<typeof assignmentSchema>;

export const assignmentHistorySchema = assignmentSchema.extend({
  createdAt: z.iso.datetime(),
});

export type AssignmentHistoryEntry = z.infer<typeof assignmentHistorySchema>;
