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
 * shown plainly rather than implying the file itself is broken. There is
 * no backend "retry ingestion" endpoint (confirmed: only a fresh upload
 * creates a new `Document` row), so the copy points at the real remedy —
 * re-uploading — rather than a fake in-place Retry button.
 *
 * The package-level summary (ready/processing/failed counts, Phase 4's
 * `summarizeDocuments`) plus a new **possible-duplicates** signal
 * (`findDuplicateGroups`, grouping already-persisted documents by their
 * real `contentHash` — distinct from `UploadSection`'s pre-upload check)
 * frame this as "the whole borrower package," not a processing log.
 */

import { AlertTriangle, Copy, Download, FileText } from 'lucide-react';
import { useState } from 'react';

import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { ProcessingPipeline } from '@design-system/components/ProcessingPipeline';
import { cn } from '@design-system/lib/cn';
import { useDocumentsForApplication } from '@entities/document/queries';
import { downloadDocument } from '@entities/document/download';
import { usePartiesForApplication } from '@entities/party/queries';
import { PARTY_TYPE_LABEL } from '@entities/party/types';
import { summarizeDocuments } from '@features/application-workspace/applicationPipelineSummary';

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
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(new Set());

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
      <div className="flex items-center justify-between">
        <h3 className="text-heading-section text-text-primary">Document Package</h3>
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
      </div>

      <ul className="flex flex-col gap-1">
        {documents.map((document) => {
          const isSelected = document.id === selectedDocumentId;
          const isExpanded = expandedIds.has(document.id);
          const isDuplicate = duplicateIds.has(document.id);
          const assignedParty =
            document.partyId !== null ? parties.find((party) => party.id === document.partyId) : undefined;

          return (
            <li
              key={document.id}
              className={cn(
                'rounded-container flex flex-col gap-1.5 border p-3',
                isSelected ? 'border-interactive-primary-default bg-surface-secondary' : 'border-border-subtle',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <button
                  type="button"
                  aria-current={isSelected}
                  onClick={() => {
                    onSelectDocument(document.id);
                  }}
                  className={cn(
                    'flex min-w-0 flex-1 flex-col gap-0.5 text-left',
                    'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2 rounded-interactive',
                  )}
                >
                  <span className="text-body-emphasis text-text-primary flex items-center gap-1.5 truncate" title={document.filename}>
                    <FileText className="text-text-tertiary size-3.5 shrink-0" aria-hidden="true" />
                    {document.filename}
                  </span>
                  <span className="text-caption text-text-tertiary">
                    {document.documentType} · Uploaded {formatUploadedAt(document.uploadedAt)} ·{' '}
                    {document.pageCount ?? '—'} page{document.pageCount === 1 ? '' : 's'}
                  </span>
                </button>
                <ProcessingPipeline steps={deriveDocumentStages(document)} size="sm" />
              </div>

              <div className="text-caption flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    void downloadDocument(applicationId, document.id, document.filename);
                  }}
                  className="text-text-secondary hover:text-text-primary inline-flex items-center gap-1 outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                >
                  <Download className="size-3.5" aria-hidden="true" />
                  Download
                </button>
                <button
                  type="button"
                  onClick={() => {
                    toggleExpanded(document.id);
                  }}
                  className="text-text-secondary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                >
                  {isExpanded ? 'Hide details' : 'Details'}
                </button>
                {document.evidenceItemCount > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      onViewEvidence(document.id);
                    }}
                    className="text-text-secondary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                  >
                    View {document.evidenceItemCount} evidence item
                    {document.evidenceItemCount === 1 ? '' : 's'} →
                  </button>
                )}
                {isDuplicate && (
                  <span className="text-feedback-warning-fg inline-flex items-center gap-1">
                    <Copy className="size-3.5" aria-hidden="true" />
                    Possible duplicate
                  </span>
                )}
              </div>

              {isExpanded && (
                <dl className="text-caption border-border-subtle text-text-secondary grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t pt-2">
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
                </dl>
              )}

              {document.ingestionStatus === 'FAILED' && (
                <p className="text-caption text-feedback-error-fg flex items-start gap-1.5">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  {document.ingestionError ?? 'Processing failed.'} — Upload this document again to
                  retry.
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
