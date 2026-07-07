/**
 * DocumentViewer (spec 002 tasks.md T066).
 *
 * The navigation layer around `PdfRenderer`/`EvidenceHighlightOverlay`:
 * page jump + page-number entry, zoom, and rendering whichever document is
 * currently selected (FR-039, FR-041, FR-042).
 *
 * **Document selection is owned by the caller, not this component**
 * (Product Experience phase, Phase 4.5). Before this phase, this component
 * had its own internal document-switcher button row — fully redundant
 * with `DocumentProcessingList.tsx`'s list, which enumerated the same
 * documents with none of the wiring to actually drive this viewer. That
 * switcher is removed; `DocumentProcessingList` is now the single place a
 * reviewer browses/selects a document, via the `selectedDocumentId` prop
 * below.
 *
 * **Processing status no longer gates rendering** (Phase 4.5 — "a document
 * remains a document regardless of whether AI processing succeeds").
 * Confirmed against the real backend: `GET .../documents/{id}/content`
 * serves raw bytes independent of `ingestionStatus`, and a `Document` row
 * only ever exists once its bytes are already durably stored — there is no
 * backend state where a `FAILED`/`PENDING`/`IN_PROGRESS` document's bytes
 * are missing. `PdfRenderer` itself has zero awareness of ingestion status.
 * So the viewer always attempts to render the active document; processing
 * status renders as a non-blocking banner above the (still-visible) PDF,
 * not a full-screen replacement of it.
 *
 * FR-042 ("via both pointer and keyboard"): every control here is a
 * native `<button>`/`<input type="number">`, both natively keyboard
 * operable without extra handling.
 *
 * `PdfRenderer` is lazy-loaded (Product Experience phase, Phase 10 audit —
 * `pdfjs-dist`, a multi-hundred-KB dependency, was being bundled eagerly
 * into the Application Workspace's route chunk even though five of the six
 * Workspace regions never touch it). It's only fetched once a reviewer
 * actually has an active document to view.
 */

import { AlertTriangle } from 'lucide-react';
import { Suspense, lazy, useEffect, useState } from 'react';

import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { ProcessingPipeline } from '@design-system/components/ProcessingPipeline';
import { cn } from '@design-system/lib/cn';
import type { Document } from '@entities/document/queries';
import { useDocumentsForApplication } from '@entities/document/queries';
import { deriveDocumentStages } from '@features/document-upload/deriveDocumentStages';

import type { PdfHighlight } from './PdfRenderer';

const PdfRenderer = lazy(() =>
  import('./PdfRenderer').then((module) => ({ default: module.PdfRenderer })),
);

const MIN_SCALE = 0.6;
const MAX_SCALE = 3.0;
const SCALE_STEP = 0.2;

export interface DocumentJumpTarget {
  readonly documentId: string;
  readonly pageNumber: number;
  readonly boundingBox: readonly [number, number, number, number] | null;
  readonly label: string;
}

export interface DocumentViewerProps {
  readonly applicationId: string;
  /** Set by another region (e.g. an evidence chip click) to jump directly to a page/highlight — FR-039. */
  readonly jumpTarget?: DocumentJumpTarget | null;
  /** Set when a reviewer clicks a row in `DocumentProcessingList` — a plain "view this document" request, no page/highlight. */
  readonly selectedDocumentId?: string | null;
  /** Product Experience phase, Phase 3 — expands the inline `UploadSection` mounted above this component. Omit to render the empty state with no action. */
  readonly onRequestUpload?: () => void;
  /** Product Experience phase, Phase 8 — fires whenever this viewer's own already-computed active document changes, so a caller (e.g. `DocumentsRegion`'s inspector panel) can scope its own content without duplicating this component's `jumpTarget`/`selectedDocumentId` precedence logic. */
  readonly onActiveDocumentChange?: (document: Document | null) => void;
}

export function DocumentViewer({
  applicationId,
  jumpTarget = null,
  selectedDocumentId = null,
  onRequestUpload,
  onActiveDocumentChange,
}: DocumentViewerProps) {
  const documentsQuery = useDocumentsForApplication(applicationId);
  // Lazy initializers: an initial jumpTarget (present on first mount, e.g.
  // a deep link) must take effect immediately, not only on later changes.
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(
    () => jumpTarget?.documentId ?? selectedDocumentId ?? null,
  );
  const [pageNumber, setPageNumber] = useState(() => jumpTarget?.pageNumber ?? 1);
  const [scale, setScale] = useState(1.2);

  const documents = documentsQuery.data ?? [];

  // FR-039: a jump target from another region always wins, overriding
  // whatever document/page is currently open — it carries a more specific
  // request (page + highlight) than a plain row click. Adjusting state in
  // response to a changed prop during render (react.dev's own pattern for
  // this case) rather than in an effect avoids an extra post-commit render.
  const [previousJumpTarget, setPreviousJumpTarget] = useState(jumpTarget);
  if (jumpTarget !== previousJumpTarget) {
    setPreviousJumpTarget(jumpTarget);
    if (jumpTarget !== null) {
      setActiveDocumentId(jumpTarget.documentId);
      setPageNumber(jumpTarget.pageNumber);
    }
  }

  // A plain "select this document" request from `DocumentProcessingList` —
  // lower priority than `jumpTarget` (handled above); only applied when it
  // changes and isn't simultaneously satisfied by a jumpTarget change.
  const [previousSelectedDocumentId, setPreviousSelectedDocumentId] = useState(selectedDocumentId);
  if (selectedDocumentId !== previousSelectedDocumentId) {
    setPreviousSelectedDocumentId(selectedDocumentId);
    if (selectedDocumentId !== null && jumpTarget === previousJumpTarget) {
      setActiveDocumentId(selectedDocumentId);
      setPageNumber(1);
    }
  }

  // Default to the first document once data arrives, without an effect: a
  // pure derivation with a fallback, not a case of "adjusting" committed
  // state. Prefers a COMPLETED document (immediately viewable) but falls
  // back to the first document of any status — FR-041 requires a
  // still-processing or failed document's state be visible without
  // leaving the viewer, which requires it to become "active" at all.
  const completedDocument = documents.find((doc) => doc.ingestionStatus === 'COMPLETED');
  const firstDocument = documents[0];
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition -- `Array.prototype.find`/index access on `Document[]` are genuinely `Document | undefined`; this appears to be a typescript-eslint false positive on chained `??`, confirmed by restructuring the same logic multiple ways without resolving it.
  const defaultDocumentId = completedDocument?.id ?? firstDocument?.id ?? null;
  const effectiveActiveDocumentId = activeDocumentId ?? defaultDocumentId;
  const activeDocument = documents.find((doc) => doc.id === effectiveActiveDocumentId) ?? null;

  useEffect(() => {
    onActiveDocumentChange?.(activeDocument);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `onActiveDocumentChange` is intentionally excluded: callers pass an inline callback, and this effect should only fire when the resolved active document itself changes, not on every parent re-render.
  }, [activeDocument]);

  if (documentsQuery.isPending) return <LoadingState label="Loading documents…" />;
  if (documentsQuery.isError) {
    return (
      <ErrorState
        title="Could not load documents"
        onRetry={() => {
          void documentsQuery.refetch();
        }}
      />
    );
  }
  if (documents.length === 0) {
    return (
      <EmptyState
        title="No documents uploaded yet"
        action={
          onRequestUpload !== undefined ? (
            <Button variant="primary" onClick={onRequestUpload}>
              Upload documents
            </Button>
          ) : undefined
        }
      />
    );
  }

  const pageCount = activeDocument?.pageCount ?? null;

  const highlight: PdfHighlight | null =
    jumpTarget !== null && jumpTarget.documentId === effectiveActiveDocumentId
      ? {
          pageNumber: jumpTarget.pageNumber,
          boundingBox: jumpTarget.boundingBox,
          label: jumpTarget.label,
        }
      : null;

  return (
    <div className="flex flex-col gap-4">
      {activeDocument === null && <EmptyState title="No document ready to view yet" />}

      {activeDocument !== null && activeDocument.ingestionStatus !== 'COMPLETED' && (
        <div
          className={cn(
            'flex items-center gap-3 rounded-container border p-3',
            activeDocument.ingestionStatus === 'FAILED'
              ? 'border-feedback-error-fg bg-feedback-error-bg'
              : 'border-border-subtle bg-surface-secondary',
          )}
        >
          <ProcessingPipeline steps={deriveDocumentStages(activeDocument)} size="sm" />
          {activeDocument.ingestionStatus === 'FAILED' && (
            <span className="text-caption text-feedback-error-fg flex items-center gap-1.5">
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
              {activeDocument.ingestionError ?? 'Processing failed.'}
            </span>
          )}
        </div>
      )}

      {activeDocument !== null && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="secondary"
              size="sm"
              disabled={pageNumber <= 1}
              onClick={() => {
                setPageNumber((current) => Math.max(1, current - 1));
              }}
            >
              Previous page
            </Button>
            <label className="flex items-center gap-2">
              <span className="text-label text-text-secondary">Page</span>
              <input
                type="number"
                min={1}
                max={pageCount ?? undefined}
                value={pageNumber}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  if (Number.isInteger(next) && next >= 1) setPageNumber(next);
                }}
                className="border-border-default rounded-interactive text-body bg-surface-background w-16 border px-2 py-1"
              />
              {pageCount !== null && (
                <span className="text-caption text-text-tertiary">of {pageCount}</span>
              )}
            </label>
            <Button
              variant="secondary"
              size="sm"
              disabled={pageCount !== null && pageNumber >= pageCount}
              onClick={() => {
                setPageNumber((current) =>
                  pageCount !== null ? Math.min(pageCount, current + 1) : current + 1,
                );
              }}
            >
              Next page
            </Button>

            <Button
              variant="secondary"
              size="sm"
              disabled={scale <= MIN_SCALE}
              onClick={() => {
                setScale((current) =>
                  Math.max(MIN_SCALE, Number((current - SCALE_STEP).toFixed(2))),
                );
              }}
            >
              Zoom out
            </Button>
            <span className="text-caption text-text-tertiary">{Math.round(scale * 100)}%</span>
            <Button
              variant="secondary"
              size="sm"
              disabled={scale >= MAX_SCALE}
              onClick={() => {
                setScale((current) =>
                  Math.min(MAX_SCALE, Number((current + SCALE_STEP).toFixed(2))),
                );
              }}
            >
              Zoom in
            </Button>
          </div>

          <Suspense fallback={<LoadingState label="Loading document viewer…" />}>
            <PdfRenderer
              applicationId={applicationId}
              documentId={activeDocument.id}
              pageNumber={pageNumber}
              scale={scale}
              highlight={highlight}
            />
          </Suspense>
        </>
      )}
    </div>
  );
}
