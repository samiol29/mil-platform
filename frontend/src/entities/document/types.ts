/**
 * Document entity (spec 002 tasks.md T054; data-model.md).
 *
 * Matches `src/mil/api/v1/schemas.py::DocumentResponse` exactly.
 * `ingestionError` is present only when `ingestionStatus === "failed"`
 * (002 Edge Cases) but is typed as always-optional rather than
 * conditionally required — Zod cannot express "required if sibling field
 * has value X" without a `.refine`, and the UI already treats its absence
 * as "no error" regardless of status.
 */

import { z } from 'zod';

export const documentSchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  partyId: z.uuid().nullable(),
  filename: z.string(),
  documentType: z.string(),
  ingestionStatus: z.enum(['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED']),
  contentHash: z.string(),
  uploadedAt: z.iso.datetime(),
  uploadedBy: z.uuid(),
  evidenceItemCount: z.number().int().nonnegative(),
  pageCount: z.number().int().nonnegative().nullable(),
  ingestionCompletedAt: z.iso.datetime().nullable(),
  ingestionError: z.string().nullable(),
  /**
   * Number of times ingestion has been retried after a FAILED state (final
   * product polish sprint) — real, additive column, defaults to 0 for every
   * document that has never been retried.
   */
  retryCount: z.number().int().nonnegative().default(0),
});

export type Document = z.infer<typeof documentSchema>;
export type IngestionStatus = Document['ingestionStatus'];
