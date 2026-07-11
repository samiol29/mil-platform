/**
 * Security & Compliance entities (spec 005-enterprise-platform §16, Wave 4).
 * Matches `src/mil/api/v1/schemas.py`'s `RetentionPolicyResponse` exactly.
 */

import { z } from 'zod';

export const RETENTION_ACTIONS = ['ARCHIVE', 'DELETE'] as const;

export const retentionPolicySchema = z.object({
  id: z.uuid(),
  tenantId: z.uuid(),
  dataCategory: z.string(),
  retentionPeriodDays: z.number(),
  action: z.enum(RETENTION_ACTIONS),
});

export type RetentionPolicy = z.infer<typeof retentionPolicySchema>;

/** Categories for which DELETE is structurally disallowed (mirrors the backend's own CHECK constraint). */
export const NEVER_DELETABLE_CATEGORIES = new Set(['AUDIT_EVENT', 'EVIDENCE']);
