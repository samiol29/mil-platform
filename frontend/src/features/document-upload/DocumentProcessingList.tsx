/**
 * Document package list (Product Experience phase, Phase 4.5 — evolved
 * from Phase 4's "Document Processing" list). The single, unified,
 * clickable source of truth for browsing every document on this
 * application — replacing two previously redundant, unconnected surfaces:
 * this list (display-only before this phase) and `DocumentViewer.tsx`'s
 * own internal document-switcher (removed in this phase). Selecting a row
 * drives `DocumentViewer` via `onSelectDocument`/`selectedDocumentId`.
 *
 * Guiding principle: **a document remains a document regardless of whether
 * AI processing succeeds.** A `FAILED` document is never presented as
 * inaccessible — it's still previewable (the viewer no longer gates on
 * ingestion status) and downloadable here, with its real `ingestionError`
 * shown plainly rather than implying the file itself is broken. A real
 * "Retry" action (final product polish sprint) re-runs OCR -> Extraction ->
 * Evidence for the exact same stored bytes via `POST .../documents/{id}/retry`
 * — no re-upload needed (ADR-006: documents are immutable, so retry only
 * re-runs the pipeline). This is distinct from "Retry evaluation" in the
 * Findings/Policy regions, which re-runs Finding Generation, not OCR — the
 * two must never be conflated (R3): a document still failing ingestion has
 * no evidence yet, so retrying evaluation for it would be a no-op.
 *
 * The package-level summary (ready/processing/failed counts, Phase 4's
 * `summarizeDocuments`) plus a new **possible-duplicates** signal
 * (`findDuplicateGroups`, grouping already-persisted documents by their
 * real `contentHash` — distinct from `UploadSection`'s pre-upload check)
 * frame this as "the whole borrower package," not a processing log.
 */

import { AlertTriangle, Copy, Download, FileText, RotateCw } from 'lucide-react';
import { useState } from 'react';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { ProcessingPipeline } from '@design-system/components/ProcessingPipeline';
import { cn } from '@design-system/lib/cn';
import { useDocumentsForApplication, useRetryDocument } from '@entities/document/queries';
import { downloadDocument } from '@entities/document/download';
import { usePartiesForApplication } from '@entities/party/queries';
import { PARTY_TYPE_LABEL } from '@entities/party/types';
import { summarizeDocuments } from '@features/application-workspace/applicationPipelineSummary';
import { extractErrorMessage } from '@shared/api/extractErrorMessage';

import { deriveDocumentStages } from './deriveDocumentStages';
import { duplicateDocumentIds } from './findDuplicateGroups';

export interface DocumentProcessingListProps {
  readonly applicationId: string;
  readonly selectedDocumentId: string | null;
  readonly onSelectDocument: (documentId: string) => void;
  /** Product Experience phase, Phase 5 — navigates to the Evidence region with this document's evidence group focused (`ApplicationWorkspace`'s `focusDocumentId`). */
  readonly onViewEvidence: (documentId: string) => void;
}

function formatUploadedAt(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function DocumentProcessingList({
  applicationId,
  selectedDocumentId,
  onSelectDocument,
  onViewEvidence,
}: DocumentProcessingListProps) {
  const documentsQuery = useDocumentsForApplication(applicationId);
  const partiesQuery = usePartiesForApplication(applicationId);
  const retryDocument = useRetryDocument(applicationId);
  const addToast = useUiStore((state) => state.addToast);
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(new Set());
  const [retryingIds, setRetryingIds] = useState<ReadonlySet<string>>(new Set());

  function retryOne(documentId: string) {
    setRetryingIds((prev) => new Set(prev).add(documentId));
    retryDocument.mutate(documentId, {
      onSettled: () => {
        setRetryingIds((prev) => {
          const next = new Set(prev);
          next.delete(documentId);
          return next;
        });
      },
      onError: (error: unknown) => {
        addToast({
          title: 'Could not retry this document',
          description: extractErrorMessage(error, 'Please try again.'),
          variant: 'error',
        });
      },
    });
  }

  if (documentsQuery.isPending) return <LoadingState label="Loading the document package…" />;
  if (documentsQuery.isError) {
    return (
      <ErrorState
        title="Could not load the document package"
        onRetry={() => {
          void documentsQuery.refetch();
        }}
      />
    );
  }
  if (documentsQuery.data.length === 0) return null;

  const documents = documentsQuery.data;
  const counts = summarizeDocuments(documents);
  const duplicateIds = duplicateDocumentIds(documents);
  const parties = partiesQuery.data ?? [];
  const failedDocumentIds = documents
    .filter((document) => document.ingestionStatus === 'FAILED')
    .map((document) => document.id);

  function toggleExpanded(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <section
      aria-label="Document package"
      className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-3 p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-heading-section text-text-primary">Document Package</h3>
        <div className="flex items-center gap-3">
          <p className="text-caption text-text-secondary">
            {counts.total} document{counts.total === 1 ? '' : 's'} · {counts.ready} ready
            {counts.processing > 0 && ` · ${String(counts.processing)} processing`}
            {counts.failed > 0 && (
              <span className="text-feedback-error-fg"> · {counts.failed} failed</span>
            )}
            {duplicateIds.size > 0 && (
              <span className="text-feedback-warning-fg">
                {' '}
                · {duplicateIds.size} possible duplicate{duplicateIds.size === 1 ? '' : 's'}
              </span>
            )}
          </p>
          {failedDocumentIds.length > 1 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                for (const documentId of failedDocumentIds) retryOne(documentId);
              }}
            >
              Retry all failed ({failedDocumentIds.length})
            </Button>
          )}
        </div>
      </div>

      <ul className="divide-border-subtle flex flex-col divide-y">
        {documents.map((document) => {
          const isSelected = document.id === selectedDocumentId;
          const isExpanded = expandedIds.has(document.id);
          const isDuplicate = duplicateIds.has(document.id);
          const isFailed = document.ingestionStatus === 'FAILED';
          const assignedParty =
            document.partyId !== null
              ? parties.find((party) => party.id === document.partyId)
              : undefined;

          return (
            <li
              key={document.id}
              className={cn(
                'border-l-2 border-l-transparent',
                isSelected && 'border-l-interactive-primary-default bg-surface-secondary',
              )}
            >
              <div className="flex items-center gap-3 py-2 pr-3 pl-2">
                <button
                  type="button"
                  aria-current={isSelected}
                  onClick={() => {
                    onSelectDocument(document.id);
                  }}
                  className={cn(
                    'flex min-w-0 flex-1 items-center gap-2 text-left',
                    'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2 rounded-interactive',
                  )}
                >
                  <FileText className="text-text-tertiary size-3.5 shrink-0" aria-hidden="true" />
                  <span
                    className="text-body-emphasis text-text-primary truncate"
                    title={document.filename}
                  >
                    {document.filename}
                  </span>
                  <span className="text-caption bg-surface-secondary text-text-tertiary rounded-chip shrink-0 px-1.5 py-0.5">
                    {document.documentType}
                  </span>
                  <span className="text-caption text-text-tertiary shrink-0">
                    {document.pageCount ?? '—'} page{document.pageCount === 1 ? '' : 's'}
                  </span>
                  {isDuplicate && (
                    <span className="text-feedback-warning-fg inline-flex shrink-0 items-center gap-1">
                      <Copy className="size-3.5" aria-hidden="true" />
                    </span>
                  )}
                  {isFailed && (
                    <span className="text-feedback-error-fg inline-flex shrink-0 items-center gap-1">
                      <AlertTriangle className="size-3.5" aria-hidden="true" />
                    </span>
                  )}
                </button>
                <ProcessingPipeline steps={deriveDocumentStages(document)} size="sm" />
                <span className="text-caption text-text-tertiary w-28 shrink-0 text-right tabular-nums">
                  {formatUploadedAt(document.uploadedAt)}
                </span>
              </div>

              <div className="text-caption flex flex-wrap items-center gap-3 py-1.5 pr-3 pl-9">
                <button
                  type="button"
                  onClick={() => {
                    void downloadDocument(applicationId, document.id, document.filename);
                  }}
                  className="text-text-tertiary hover:text-text-primary inline-flex items-center gap-1 outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                >
                  <Download className="size-3.5" aria-hidden="true" />
                  Download
                </button>
                <button
                  type="button"
                  onClick={() => {
                    toggleExpanded(document.id);
                  }}
                  className="text-text-tertiary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                >
                  {isExpanded ? 'Hide details' : 'Details'}
                </button>
                {document.evidenceItemCount > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      onViewEvidence(document.id);
                    }}
                    className="text-text-tertiary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                  >
                    View {document.evidenceItemCount} evidence item
                    {document.evidenceItemCount === 1 ? '' : 's'} →
                  </button>
                )}
                {isFailed && (
                  <button
                    type="button"
                    disabled={retryingIds.has(document.id)}
                    onClick={() => {
                      retryOne(document.id);
                    }}
                    className="text-feedback-error-fg hover:text-feedback-error-fg inline-flex items-center gap-1 outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2 disabled:opacity-50"
                  >
                    <RotateCw
                      className={cn('size-3.5', retryingIds.has(document.id) && 'animate-spin')}
                      aria-hidden="true"
                    />
                    {retryingIds.has(document.id) ? 'Retrying…' : 'Retry'}
                    {document.retryCount > 0 && ` (attempt ${String(document.retryCount + 1)})`}
                  </button>
                )}
                {isDuplicate && (
                  <span className="text-feedback-warning-fg">Possible duplicate</span>
                )}
              </div>

              {isExpanded && (
                <dl className="text-caption text-text-secondary grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 py-2 pr-3 pl-9">
                  <dt className="text-text-tertiary">Content hash</dt>
                  <dd className="truncate font-mono" title={document.contentHash}>
                    {document.contentHash.slice(0, 16)}…
                  </dd>
                  <dt className="text-text-tertiary">Assigned to</dt>
                  <dd>
                    {assignedParty !== undefined
                      ? `${PARTY_TYPE_LABEL[assignedParty.partyType]} — ${assignedParty.displayName}`
                      : 'Unassigned'}
                  </dd>
                  {isFailed && (
                    <>
                      <dt className="text-feedback-error-fg">Processing failed</dt>
                      <dd className="text-feedback-error-fg">
                        {document.ingestionError ?? 'Processing failed.'}
                        {document.retryCount > 0 &&
                          ` — retried ${String(document.retryCount)} time${document.retryCount === 1 ? '' : 's'} already.`}
                      </dd>
                    </>
                  )}
                </dl>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
