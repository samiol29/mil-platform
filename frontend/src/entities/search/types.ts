/**
 * Universal Search entities (spec 005-enterprise-platform §7, Wave 2).
 * Matches `src/mil/api/v1/schemas.py`'s `SearchResponse`/discriminated
 * `SearchResult` union exactly.
 */

import { z } from 'zod';

import { applicationSchema } from '@entities/application/types';

export const applicationSearchResultSchema = z.object({
  kind: z.literal('application'),
  application: applicationSchema,
});

export const documentSearchResultSchema = z.object({
  kind: z.literal('document'),
  documentId: z.uuid(),
  applicationId: z.uuid(),
  filename: z.string(),
  uploadedAt: z.iso.datetime(),
});

export const searchResultSchema = z.discriminatedUnion('kind', [
  applicationSearchResultSchema,
  documentSearchResultSchema,
]);

export type SearchResult = z.infer<typeof searchResultSchema>;

export const searchResponseSchema = z.object({
  query: z.string(),
  results: z.array(searchResultSchema),
});

export type SearchResponse = z.infer<typeof searchResponseSchema>;
