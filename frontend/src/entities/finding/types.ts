/**
 * Finding entity (spec 002 tasks.md T058; data-model.md; Constitution
 * Principles I/III/XII).
 *
 * Matches `src/mil/api/v1/schemas.py::FindingResponse` exactly. All five
 * explainability fields (`what`, `why`, `evidenceRefs`, `confidence`,
 * `recommendedAction`) and all four attribution fields (`modelVersion`,
 * `promptVersion`, `extractionVersion`, `policyVersion`) are required at
 * the type level, not optional — a Finding parsed from a response missing
 * any of them is a Zod parse failure (a loud contract break), never a
 * silently-rendered partial Finding (plan.md: "a partial cache hit is
 * treated as a cache miss for this entity specifically").
 *
 * `policyVersion` is nullable (not merely optional): no Policy evaluation
 * may exist yet for a given finding, a real and expected state, distinct
 * from a missing/broken attribution chain.
 *
 * `state` includes `"escalated"` at the type level, per data-model.md,
 * even though the backend cannot produce it yet — see HANDOFF.md for the
 * open question on the Finding lifecycle's escalate action. The type is
 * written to the spec's eventual shape; only the escalate mutation
 * (tasks.md T059) is withheld pending that decision.
 */

import { z } from 'zod';

export const findingSchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  what: z.string().min(1),
  why: z.string().min(1),
  evidenceRefs: z.array(z.uuid()).min(1),
  confidence: z.enum(['high', 'medium', 'low']),
  recommendedAction: z.string().min(1),
  state: z.enum(['unreviewed', 'verified', 'overridden', 'escalated']),
  modelVersion: z.string().min(1),
  promptVersion: z.string().min(1),
  extractionVersion: z.string().min(1),
  policyVersion: z.string().nullable(),
  createdAt: z.iso.datetime(),
});

export type Finding = z.infer<typeof findingSchema>;
export type FindingState = Finding['state'];
