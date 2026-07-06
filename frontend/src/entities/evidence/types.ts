/**
 * EvidenceItem entity (spec 002 tasks.md T056; data-model.md).
 *
 * Matches `src/mil/api/v1/schemas.py::EvidenceItemResponse` exactly.
 *
 * Two data-model.md fields are deliberately absent, both out of this
 * session's scope (User Story 1) and belonging to later work:
 *
 * - `verificationStatus` — the backend's Review bounded context reviews
 *   *Findings*, not individual evidence items; no per-evidence-item
 *   verification concept exists in the domain model today. If/when one is
 *   added, it belongs here.
 * - `conflictsWith` — evidence-conflict detection (User Story 4, Evidence
 *   Explorer, tasks.md T093+) is a distinct, narrower relationship than the
 *   `supersedesId` field that already exists (a directional "this item
 *   supersedes an older one," not a symmetric conflict flag).
 *
 * `extractionVersion` is named to match the backend's actual field,
 * `extraction_model_version` (camelCased by the response interceptor to
 * `extractionModelVersion`) — data-model.md's guessed name predates this
 * endpoint's implementation; Constitution Principle VII requires matching
 * the real backend name, not a pre-implementation guess.
 */

import { z } from 'zod';

export const evidenceItemSchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  documentId: z.uuid(),
  partyId: z.uuid().nullable(),
  evidenceType: z.string(),
  valueText: z.string().nullable(),
  valueNumeric: z.string().nullable(),
  currency: z.string().nullable(),
  pageNumber: z.number().int().positive().nullable(),
  fieldLocation: z.record(z.string(), z.unknown()).nullable(),
  confidence: z.enum(['high', 'medium', 'low']),
  extractionMethod: z.string(),
  extractionModelVersion: z.string(),
  extractedAt: z.iso.datetime(),
  supersedesId: z.uuid().nullable(),
  createdAt: z.iso.datetime(),
});

export type EvidenceItem = z.infer<typeof evidenceItemSchema>;
export type ConfidenceLevel = EvidenceItem['confidence'];
