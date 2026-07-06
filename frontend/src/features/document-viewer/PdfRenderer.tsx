/**
 * PdfRenderer (spec 002 tasks.md T064) — the PDF.js rendering layer.
 *
 * Renders only the requested page (default: the first) to a canvas —
 * "first-page-usable-first, no full-document wait" (002 FR-038): loading a
 * PDF's metadata via `pdf.js` does not require rendering every page, and
 * this component never does so; the coordinate-mapping evidence-highlight
 * overlay and multi-page/zoom navigation are tasks.md T065/T066,
 * explicitly out of scope for this session — this component is the
 * rendering primitive those will be built on top of, not a full document
 * viewer itself.
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

GlobalWorkerOptions.workerSrc = workerSrc;

export interface PdfRendererProps {
  readonly applicationId: string;
  readonly documentId: string;
  readonly pageNumber?: number;
  readonly className?: string;
}

export function PdfRenderer({
  applicationId,
  documentId,
  pageNumber = 1,
  className,
}: PdfRendererProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

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

    let cancelled = false;

    async function renderPage() {
      setRenderError(null);
      const pdf = await getDocument({ data: bytes.slice(0) }).promise;
      const page = await pdf.getPage(pageNumber);
      if (cancelled) return;

      const viewport = page.getViewport({ scale: 1.2 });
      const canvas = canvasRef.current;
      if (canvas === null) return;
      const context = canvas.getContext('2d');
      if (context === null) return;

      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: context, viewport, canvas }).promise;
    }

    renderPage().catch((error: unknown) => {
      if (!cancelled) {
        setRenderError(error instanceof Error ? error.message : 'Failed to render document.');
      }
    });

    return () => {
      cancelled = true;
    };
  }, [documentBytes, pageNumber]);

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

  return (
    <div
      role="img"
      aria-label={`Document page ${String(pageNumber)}`}
      className={cn('inline-block', className)}
    >
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="border-border-subtle rounded-container border"
      />
    </div>
  );
}
