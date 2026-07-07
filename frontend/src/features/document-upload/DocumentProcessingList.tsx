/**
 * Document Processing list (Product Experience phase, Phase 4) — the
 * persistent, always-visible source of truth for "what's the state of
 * every document on this application." Distinct from `UploadSection`'s own
 * per-row status (Phase 3), which only exists for the current upload
 * session and disappears on reload — this panel reads every real document
 * from `useDocumentsForApplication` (Phase 3's polling hook, unchanged
 * here) so a reviewer sees accurate state on any visit, not only mid-upload.
 *
 * A `FAILED` document never implies the whole application is broken
 * (Principle 4) — it renders its own real `ingestionError` and an honest
 * recovery instruction. There is no backend "retry ingestion" endpoint
 * (confirmed: only a fresh upload creates a new `Document` row), so the
 * copy points at the real remedy — re-uploading — rather than a fake
 * in-place Retry button implying a backend capability that doesn't exist.
 */

import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { ProcessingPipeline } from '@design-system/components/ProcessingPipeline';
import { useDocumentsForApplication } from '@entities/document/queries';

import { deriveDocumentStages } from './deriveDocumentStages';

export interface DocumentProcessingListProps {
  readonly applicationId: string;
}

export function DocumentProcessingList({ applicationId }: DocumentProcessingListProps) {
  const documentsQuery = useDocumentsForApplication(applicationId);

  if (documentsQuery.isPending) return <LoadingState label="Loading document processing status…" />;
  if (documentsQuery.isError) {
    return (
      <ErrorState
        title="Could not load document processing status"
        onRetry={() => {
          void documentsQuery.refetch();
        }}
      />
    );
  }
  if (documentsQuery.data.length === 0) return null;

  return (
    <section
      aria-label="Document processing"
      className="border-border-subtle bg-surface-raised rounded-container flex flex-col gap-3 border p-4"
    >
      <h3 className="text-heading-section text-text-primary">Document Processing</h3>
      <ul className="flex flex-col gap-3">
        {documentsQuery.data.map((document) => (
          <li key={document.id} className="border-border-subtle border-b pb-3 last:border-b-0 last:pb-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-body text-text-primary truncate" title={document.filename}>
                {document.filename}
              </span>
              <ProcessingPipeline steps={deriveDocumentStages(document)} size="sm" />
            </div>
            {document.ingestionStatus === 'FAILED' && (
              <p className="text-caption text-feedback-error-fg mt-1">
                {document.ingestionError ?? 'Processing failed.'} — Upload this document again to
                retry.
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
