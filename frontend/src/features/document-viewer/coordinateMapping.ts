/**
 * Evidence-highlight coordinate mapping (spec 002 tasks.md T065).
 *
 * The novel engineering work plan.md's Risks & Mitigations names explicitly:
 * mapping a stored, page-relative evidence location into PDF.js's rendered
 * coordinate space, correct across zoom level and page rotation.
 *
 * `FieldLocation.boundingBox` (`mil.kernel.providers.extraction
 * .FieldLocation`) is `[x, y, width, height]`, each a fraction of the
 * page's *unrotated* dimensions in `[0.0, 1.0]`, in top-left-origin,
 * y-increases-downward image/OCR convention — this is an assumption (no
 * production extraction provider populates real coordinates yet; only
 * `mock_extraction.py`'s synthetic fixture does, and its incrementing-y
 * rows are consistent only with a top-left origin). If a future real OCR
 * provider turns out to use PDF-native bottom-left origin instead, only
 * `imageFractionToPdfPoint` below needs to change — everything past it
 * (the PDF.js viewport transform) is convention-independent.
 *
 * The transform is deliberately built on `PDFPageViewport
 * .convertToViewportPoint`, PDF.js's own public, documented API for this
 * exact purpose, rather than a hand-rolled rotation matrix — it is already
 * correct for all four rotations (0/90/180/270) and any scale, which is
 * exactly the "correct across zoom and rotation" requirement. Taking the
 * min/max of the two transformed corners (rather than assuming a fixed
 * corner order) is what makes this rotation-agnostic: PDF.js's transform
 * can return the corners in a different screen-space order depending on
 * rotation, and reading `left`/`top`/`width`/`height` off unordered corners
 * would silently mis-place or negatively-size the box at 90/270 degrees.
 */

/** [x0, y0, x1, y1] — a PDF page's default (unrotated, unscaled) user-space box, from `page.view`. */
export type PdfPageBox = readonly [number, number, number, number];

/** [x, y, width, height] fractions of the page, top-left origin — `FieldLocation.boundingBox`. */
export type FractionalBoundingBox = readonly [number, number, number, number];

export interface ViewportRect {
  readonly left: number;
  readonly top: number;
  readonly width: number;
  readonly height: number;
}

function imageFractionToPdfPoint(
  pageView: PdfPageBox,
  fx: number,
  fy: number,
): readonly [number, number] {
  const [x0, y0, x1, y1] = pageView;
  const pageWidth = x1 - x0;
  const pageHeight = y1 - y0;
  // y is flipped: fy = 0 (image top) is the page's maximum PDF y (y1).
  return [x0 + fx * pageWidth, y1 - fy * pageHeight];
}

/**
 * Compute the on-canvas rectangle for a fractional bounding box, given the
 * page's unrotated box and a viewport-point transform (normally
 * `PDFPageViewport.convertToViewportPoint`, injected as a plain function so
 * this math is testable without a real PDF.js viewport instance).
 */
export function computeHighlightRect(
  pageView: PdfPageBox,
  boundingBox: FractionalBoundingBox,
  toViewportPoint: (x: number, y: number) => readonly [number, number],
): ViewportRect {
  const [fx, fy, fw, fh] = boundingBox;

  const [pdfX1, pdfY1] = imageFractionToPdfPoint(pageView, fx, fy);
  const [pdfX2, pdfY2] = imageFractionToPdfPoint(pageView, fx + fw, fy + fh);

  const [vx1, vy1] = toViewportPoint(pdfX1, pdfY1);
  const [vx2, vy2] = toViewportPoint(pdfX2, pdfY2);

  return {
    left: Math.min(vx1, vx2),
    top: Math.min(vy1, vy2),
    width: Math.abs(vx2 - vx1),
    height: Math.abs(vy2 - vy1),
  };
}
