/**
 * Document query hooks (spec 002 tasks.md T055).
 *
 * Caching tier (data-model.md): "informational" (short staleTime, active
 * polling) while `ingestionStatus` is not yet `"COMPLETED"`/`"FAILED"`;
 * effectively long-lived once it reaches either terminal state. This hook
 * expresses that directly via TanStack Query's `refetchInterval` — no
 * separate polling mechanism is layered on top.
 */

import { useQuery } from '@tanstack/react-query';
import type { Query } from '@tanstack/react-query';

import { STALE_TIME } from '@app/queryClient';
import { httpClient } from '@app/auth/httpClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { documentSchema, type Document } from './types';

const POLL_WHILE_INGESTING_MS = 3_000;

function staleTimeFor(document: Document | undefined): number {
  if (document === undefined) return STALE_TIME.informational;
  return document.ingestionStatus === 'COMPLETED' || document.ingestionStatus === 'FAILED'
    ? STALE_TIME.longLived
    : STALE_TIME.informational;
}

export function useDocument(applicationId: string, documentId: string) {
  return useEntityQuery({
    queryKey: ['document', documentId],
    url: `/applications/${applicationId}/documents/${documentId}`,
    schema: documentSchema,
    staleTime: STALE_TIME.informational,
  });
}

/** List every document for an application, polling while any are still ingesting. */
export function useDocumentsForApplication(applicationId: string) {
  return useQuery({
    queryKey: ['documents', 'byApplication', applicationId],
    queryFn: async () => {
      const response = await httpClient.get<unknown>(`/applications/${applicationId}/documents`);
      return documentSchema.array().parse(response.data);
    },
    staleTime: STALE_TIME.informational,
    refetchInterval: (query: Query<Document[]>) => {
      const documents = query.state.data;
      if (documents === undefined) return false;
      const stillIngesting = documents.some(
        (d) => d.ingestionStatus === 'PENDING' || d.ingestionStatus === 'IN_PROGRESS',
      );
      return stillIngesting ? POLL_WHILE_INGESTING_MS : false;
    },
  });
}

export type { Document };
export { staleTimeFor };
