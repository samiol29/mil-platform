/**
 * Document query hooks (spec 002 tasks.md T055).
 *
 * Caching tier (data-model.md): "informational" (short staleTime, active
 * polling) while `ingestionStatus` is not yet `"COMPLETED"`/`"FAILED"`;
 * effectively long-lived once it reaches either terminal state. This hook
 * expresses that directly via TanStack Query's `refetchInterval` — no
 * separate polling mechanism is layered on top.
 *
 * **WebSocket/SSE extension point** (Product Experience phase, Phase 4 —
 * no such endpoint exists in the backend today, confirmed by a full search):
 * `useDocumentsForApplication` is the single seam between "how document
 * status data arrives" and every consumer of it (`deriveDocumentStages.ts`,
 * `DocumentProcessingList.tsx`, `ApplicationWorkspace.tsx`'s Overview
 * pipeline summary). None of those consumers read `refetchInterval` or
 * anything else fetch-mechanism-specific — they only read this hook's
 * returned data. If a future backend change adds a push channel, only this
 * hook's internals change (swap `refetchInterval` polling for a
 * subscription that calls `queryClient.setQueryData`/`invalidateQueries`
 * on push); no other file in this chain needs to change.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Query } from '@tanstack/react-query';

import { STALE_TIME } from '@app/queryClient';
import { httpClient } from '@app/auth/httpClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { documentSchema, type Document } from './types';

const POLL_WHILE_INGESTING_MS = 3_000;

function documentsQueryKey(applicationId: string) {
  return ['documents', 'byApplication', applicationId] as const;
}

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
    queryKey: documentsQueryKey(applicationId),
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

export interface UploadDocumentInput {
  readonly file: File;
  readonly documentType: string;
  readonly partyId?: string;
  /** Forwarded straight to axios — drives the per-file progress bar (Product Experience phase, Phase 3). */
  readonly onUploadProgress?: (progressEvent: { loaded: number; total?: number }) => void;
}

/**
 * Upload a document (Product Experience phase, Phase 3). Invalidates the
 * exact query key `useDocumentsForApplication` uses — the newly-uploaded
 * document (status `PENDING`) then flows through that hook's *existing*
 * polling with no separate mechanism, which is what makes the Upload →
 * Processing transition feel like one continuous screen rather than a
 * hand-off to a different view.
 */
export function useUploadDocument(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: UploadDocumentInput) => {
      const formData = new FormData();
      formData.append('file', input.file);
      formData.append('document_type', input.documentType);
      if (input.partyId !== undefined) {
        formData.append('party_id', input.partyId);
      }
      const response = await httpClient.post<unknown>(
        `/applications/${applicationId}/documents`,
        formData,
        {
          onUploadProgress: input.onUploadProgress,
          // The `fetch` API has no upload-progress event at all — forcing the
          // `xhr` adapter is what makes `onUploadProgress` actually fire, not
          // just a test-environment workaround.
          adapter: 'xhr',
        },
      );
      return documentSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: documentsQueryKey(applicationId) });
    },
  });
}

export type { Document };
export { staleTimeFor };
