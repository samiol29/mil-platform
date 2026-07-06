/**
 * PdfRenderer (spec 002 tasks.md T064; evidence-highlight wiring T065) —
 * the PDF.js rendering layer.
 *
 * Renders only the requested page (default: the first) to a canvas —
 * "first-page-usable-first, no full-document wait" (002 FR-038): loading a
 * PDF's metadata via `pdf.js` does not require rendering every page, and
 * this component never does so. Multi-page/zoom navigation is tasks.md
 * T066, still out of scope here — this component renders exactly one page
 * at a time and optionally overlays one evidence highlight on it.
 *
 * Fetches the document's raw bytes through the shared `httpClient` (so the
 * bearer-token interceptor applies) rather than letting `pdf.js` fetch a
 * bare URL itself, which would bypass authentication entirely.
 */

import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import workerSrc from 'pdfjs-dist/build/pdf.worker.mjs?url';
import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { cn } from '@design-system/lib/cn';

import { type FractionalBoundingBox, type PdfPageBox } from './coordinateMapping';
import { EvidenceHighlightOverlay } from './EvidenceHighlightOverlay';

GlobalWorkerOptions.workerSrc = workerSrc;

export interface PdfHighlight {
  /** The evidence's page (1-indexed) — the overlay only renders when this matches the currently-rendered page. */
  readonly pageNumber: number;
  readonly boundingBox: FractionalBoundingBox | null;
  readonly label: string;
}

export interface PdfRendererProps {
  readonly applicationId: string;
  readonly documentId: string;
  readonly pageNumber?: number;
  readonly scale?: number;
  readonly highlight?: PdfHighlight | null;
  readonly className?: string;
}

interface RenderedPageInfo {
  readonly pageView: PdfPageBox;
  readonly toViewportPoint: (x: number, y: number) => readonly [number, number];
}

export function PdfRenderer({
  applicationId,
  documentId,
  pageNumber = 1,
  scale = 1.2,
  highlight = null,
  className,
}: PdfRendererProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [renderedPage, setRenderedPage] = useState<RenderedPageInfo | null>(null);

  const contentQuery = useQuery({
    queryKey: ['document-content', documentId],
    queryFn: async () => {
      const response = await httpClient.get<ArrayBuffer>(
        `/applications/${applicationId}/documents/${documentId}/content`,
        { responseType: 'arraybuffer' },
      );
      return response.data;
    },
    staleTime: STALE_TIME.longLived,
  });

  const documentBytes = contentQuery.data;

  useEffect(() => {
    if (documentBytes === undefined) return;
    const bytes = documentBytes;

    const cancellation = { cancelled: false };
    // A function call, not a direct property read: TypeScript narrows a
    // property read to a literal across the whole function body, unaware
    // that an `await` yields to the effect's cleanup (which sets this same
    // flag). Reading it through a call sidesteps that false narrowing.
    const isCancelled = () => cancellation.cancelled;

    async function renderPage() {
      setRenderError(null);
      setRenderedPage(null);
      const pdf = await getDocument({ data: bytes.slice(0) }).promise;
      const page = await pdf.getPage(pageNumber);
      if (isCancelled()) return;

      const viewport = page.getViewport({ scale });
      const canvas = canvasRef.current;
      if (canvas === null) return;
      const context = canvas.getContext('2d');
      if (context === null) return;

      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: context, viewport, canvas }).promise;
      if (isCancelled()) return;

      const [x0, y0, x1, y1] = page.view;
      setRenderedPage({
        pageView: [x0, y0, x1, y1],
        toViewportPoint: (x, y) => {
          const point: unknown[] = viewport.convertToViewportPoint(x, y);
          return [Number(point[0]), Number(point[1])];
        },
      });
    }

    renderPage().catch((error: unknown) => {
      if (!cancellation.cancelled) {
        setRenderError(error instanceof Error ? error.message : 'Failed to render document.');
      }
    });

    return () => {
      cancellation.cancelled = true;
    };
  }, [documentBytes, pageNumber, scale]);

  if (contentQuery.isPending) return <LoadingState label="Loading document…" />;
  if (contentQuery.isError) {
    return (
      <ErrorState
        title="Could not load this document"
        onRetry={() => {
          void contentQuery.refetch();
        }}
      />
    );
  }
  if (renderError !== null) {
    return <ErrorState title="Could not render this document" details={renderError} />;
  }

  const showHighlight =
    highlight !== null && renderedPage !== null && highlight.pageNumber === pageNumber;

  return (
    <div
      role="img"
      aria-label={`Document page ${String(pageNumber)}`}
      className={cn('relative inline-block', className)}
    >
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="border-border-subtle rounded-container border"
      />
      {showHighlight && (
        <EvidenceHighlightOverlay
          pageView={renderedPage.pageView}
          boundingBox={highlight.boundingBox}
          toViewportPoint={renderedPage.toViewportPoint}
          label={highlight.label}
        />
      )}
    </div>
  );
}
