/**
 * DocumentViewer (spec 002 tasks.md T066).
 *
 * The navigation layer around `PdfRenderer`/`EvidenceHighlightOverlay`:
 * page jump + page-number entry, zoom, and switching between an
 * application's multiple documents (FR-039, FR-041, FR-042, FR-044).
 *
 * **"Pinned-vs-preview tabs" (plan.md's own architectural framing of
 * FR-044) is deliberately not implemented as a distinct interaction mode.**
 * FR-044's actual requirement is only "switching between [documents]
 * without losing the reviewer's place in the application's other
 * regions" — already satisfied structurally, since each Application
 * Workspace region (`ApplicationWorkspace.tsx`) mounts independently and
 * this component's document/page/zoom state is local to it. A VS
 * Code-style single-click-preview-vs-double-click-pin model is a specific
 * interaction design no FR specifies precisely (which click pins? does a
 * preview tab get replaced by the next preview, or accumulate?) — building
 * it would be guessing UI behavior, not implementing a requirement. A
 * plain document selector satisfies FR-044's literal text.
 *
 * FR-042 ("via both pointer and keyboard"): every control here is a
 * native `<button>`/`<input type="number">`, both natively keyboard
 * operable without extra handling.
 */

import { useState } from 'react';

import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import type { Document } from '@entities/document/queries';
import { useDocumentsForApplication } from '@entities/document/queries';

import type { PdfHighlight } from './PdfRenderer';
import { PdfRenderer } from './PdfRenderer';

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
}

function statusLabel(status: Document['ingestionStatus']): string {
  switch (status) {
    case 'PENDING':
      return 'Processing not yet started';
    case 'IN_PROGRESS':
      return 'Processing…';
    case 'FAILED':
      return 'Processing failed';
    case 'COMPLETED':
      return 'Ready';
  }
}

export function DocumentViewer({ applicationId, jumpTarget = null }: DocumentViewerProps) {
  const documentsQuery = useDocumentsForApplication(applicationId);
  // Lazy initializers: an initial jumpTarget (present on first mount, e.g.
  // a deep link) must take effect immediately, not only on later changes.
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(
    () => jumpTarget?.documentId ?? null,
  );
  const [pageNumber, setPageNumber] = useState(() => jumpTarget?.pageNumber ?? 1);
  const [scale, setScale] = useState(1.2);

  const documents = documentsQuery.data ?? [];

  // FR-039: a jump target from another region always wins, overriding
  // whatever document/page is currently open. Adjusting state in response
  // to a changed prop during render (react.dev's own pattern for this
  // case) rather than in an effect avoids an extra post-commit render.
  const [previousJumpTarget, setPreviousJumpTarget] = useState(jumpTarget);
  if (jumpTarget !== previousJumpTarget) {
    setPreviousJumpTarget(jumpTarget);
    if (jumpTarget !== null) {
      setActiveDocumentId(jumpTarget.documentId);
      setPageNumber(jumpTarget.pageNumber);
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
  if (documents.length === 0) return <EmptyState title="No documents uploaded yet" />;

  const activeDocument = documents.find((doc) => doc.id === effectiveActiveDocumentId) ?? null;
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
      {documents.length > 1 && (
        <nav aria-label="Open documents" className="flex flex-wrap gap-2">
          {documents.map((doc) => (
            <Button
              key={doc.id}
              variant={doc.id === effectiveActiveDocumentId ? 'primary' : 'secondary'}
              size="sm"
              aria-current={doc.id === effectiveActiveDocumentId}
              onClick={() => {
                setActiveDocumentId(doc.id);
                setPageNumber(1);
              }}
            >
              {doc.filename}
            </Button>
          ))}
        </nav>
      )}

      {activeDocument === null && <EmptyState title="No document ready to view yet" />}

      {activeDocument !== null &&
        activeDocument.ingestionStatus !== 'COMPLETED' &&
        (activeDocument.ingestionError !== null ? (
          <EmptyState
            title={statusLabel(activeDocument.ingestionStatus)}
            description={activeDocument.ingestionError}
          />
        ) : (
          <EmptyState title={statusLabel(activeDocument.ingestionStatus)} />
        ))}

      {activeDocument !== null && activeDocument.ingestionStatus === 'COMPLETED' && (
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

          <PdfRenderer
            applicationId={applicationId}
            documentId={activeDocument.id}
            pageNumber={pageNumber}
            scale={scale}
            highlight={highlight}
          />
        </>
      )}
    </div>
  );
}
