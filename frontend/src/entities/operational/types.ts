/**
 * Operational Dashboard entities (spec 005-enterprise-platform §10, Wave 3).
 * Matches `src/mil/api/v1/schemas.py`'s `QueueDepthRowResponse`/
 * `PoisonJobResponse`/`ApplicationFunnelRowResponse` exactly. All three are
 * computed on demand from real, already-persisted data — no fabricated
 * historical trend, no time-series (see spec §10's implementation
 * correction note).
 */

import { z } from 'zod';

export const queueDepthRowSchema = z.object({
  workflowType: z.string(),
  status: z.string(),
  count: z.number(),
});

export type QueueDepthRow = z.infer<typeof queueDepthRowSchema>;

export const poisonJobSchema = z.object({
  id: z.uuid(),
  workflowRunId: z.uuid(),
  stepName: z.string(),
  status: z.string(),
  retryCount: z.number(),
  maxRetries: z.number(),
  errorCode: z.string().nullable(),
  errorMessage: z.string().nullable(),
  updatedAt: z.iso.datetime(),
});

export type PoisonJob = z.infer<typeof poisonJobSchema>;

export const applicationFunnelRowSchema = z.object({
  status: z.string(),
  count: z.number(),
  avgSecondsSinceUpdated: z.number(),
});

export type ApplicationFunnelRow = z.infer<typeof applicationFunnelRowSchema>;

/** Real, process-wide job queue counters (spec 005 §14, Wave 4). */
export const jobQueueHealthSchema = z.object({
  pendingCount: z.number(),
  processingCount: z.number(),
  deadLetterCount: z.number(),
});

export type JobQueueHealth = z.infer<typeof jobQueueHealthSchema>;
