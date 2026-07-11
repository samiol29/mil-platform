/**
 * Business Analytics entities (spec 005-enterprise-platform §11, Wave 3).
 * Matches `src/mil/api/v1/schemas.py`'s `BusinessAnalyticsSnapshotResponse`
 * exactly. A current-state snapshot only — no historical trend field
 * exists anywhere here, since none is computed on the backend (disclosed
 * honestly in the UI rather than fabricated).
 */

import { z } from 'zod';

export const applicationStatusCountSchema = z.object({
  status: z.string(),
  count: z.number(),
});

export const findingOutcomeRowSchema = z.object({
  lifecycleState: z.string(),
  count: z.number(),
});

export const policyOutcomeRowSchema = z.object({
  policyVersion: z.string(),
  outcome: z.string(),
  count: z.number(),
});

export const businessAnalyticsSnapshotSchema = z.object({
  applicationCountsByStatus: z.array(applicationStatusCountSchema),
  findingOutcomes: z.array(findingOutcomeRowSchema),
  policyOutcomes: z.array(policyOutcomeRowSchema),
  documentCount: z.number(),
  evidenceCount: z.number(),
  averageReviewDurationSeconds: z.number().nullable(),
});

export type BusinessAnalyticsSnapshot = z.infer<typeof businessAnalyticsSnapshotSchema>;
