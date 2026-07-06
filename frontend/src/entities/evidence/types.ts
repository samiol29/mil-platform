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
 *
 * `fieldLocation.boundingBox` matches `mil.kernel.providers.extraction
 * .FieldLocation.bounding_box` exactly: an `[x, y, width, height]` tuple,
 * each a fraction of the page's dimensions in `[0.0, 1.0]` — not pixels,
 * so it is independent of zoom/render scale (tasks.md T065's coordinate
 * mapping only has to place it, never rescale it against a stored pixel
 * size).
 */

import { z } from 'zod';

export const fieldLocationSchema = z.object({
  pageNumber: z.number().int().positive(),
  fieldName: z.string(),
  boundingBox: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullable(),
});

export type FieldLocation = z.infer<typeof fieldLocationSchema>;

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
  fieldLocation: fieldLocationSchema.nullable(),
  confidence: z.enum(['high', 'medium', 'low']),
  extractionMethod: z.string(),
  extractionModelVersion: z.string(),
  extractedAt: z.iso.datetime(),
  supersedesId: z.uuid().nullable(),
  createdAt: z.iso.datetime(),
});

export type EvidenceItem = z.infer<typeof evidenceItemSchema>;
export type ConfidenceLevel = EvidenceItem['confidence'];
