/**
 * AI Case Copilot entities (spec 005-enterprise-platform §8).
 *
 * The backend for this module was already fully built, routed, and mounted
 * before this wave (`src/mil/api/v1/copilot.py`, `src/mil/copilot/*`) — this
 * is the first frontend to consume it. Matches
 * `src/mil/api/v1/schemas.py`'s `CopilotResponseSchema`/`CitationSchema`/
 * `CopilotSessionResponse`/`CopilotHistoryResponse` exactly.
 */

import { z } from 'zod';

export const citationSchema = z.object({
  kind: z.string(),
  ref: z.string(),
  locator: z.string().nullable(),
});

export type Citation = z.infer<typeof citationSchema>;

export const copilotResponseSchema = z.object({
  id: z.uuid(),
  queryId: z.uuid(),
  sessionId: z.uuid(),
  answer: z.string(),
  promptVersion: z.string(),
  modelVersion: z.string(),
  citations: z.array(citationSchema),
  createdAt: z.iso.datetime(),
});

export type CopilotResponse = z.infer<typeof copilotResponseSchema>;

export const copilotSessionSchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  tenantId: z.uuid(),
  createdByUserId: z.uuid(),
  correlationId: z.string(),
  createdAt: z.iso.datetime(),
});

export type CopilotSession = z.infer<typeof copilotSessionSchema>;

export const copilotHistoryItemSchema = z.object({
  queryId: z.uuid(),
  question: z.string(),
  askedByUserId: z.uuid(),
  askedAt: z.iso.datetime(),
  response: copilotResponseSchema.nullable(),
});

export type CopilotHistoryItem = z.infer<typeof copilotHistoryItemSchema>;

export const copilotHistorySchema = z.object({
  sessionId: z.uuid(),
  items: z.array(copilotHistoryItemSchema),
});

export type CopilotHistory = z.infer<typeof copilotHistorySchema>;
