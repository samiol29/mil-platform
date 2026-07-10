import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { computeHighlightRect, type PdfPageBox } from './coordinateMapping';
import { EvidenceHighlightOverlay } from './EvidenceHighlightOverlay';

/**
 * An independent re-implementation of `pdfjs-dist`'s own
 * `PageViewport`/`convertToViewportPoint` formula (`src/display/api.js`),
 * used here as a reference oracle rather than importing the real class —
 * `pdfjs-dist`'s bundle references `DOMMatrix` at module scope, which
 * jsdom (this project's unit-test environment) does not implement. The
 * production code (`PdfRenderer.tsx`) calls the real library method
 * directly; this is purely a test-side stand-in with the identical,
 * documented math, so `computeHighlightRect` is verified against a
 * faithful transform, not a hand-wavy approximation.
 */
function pdfjsViewportTransform(viewBox: PdfPageBox, scale: number, rotation: number) {
  const [x0, y0, x1, y1] = viewBox;
  const centerX = (x1 + x0) / 2;
  const centerY = (y1 + y0) / 2;
  const normalizedRotation = ((rotation % 360) + 360) % 360;

  let rotateA: number, rotateB: number, rotateC: number, rotateD: number;
  switch (normalizedRotation) {
    case 180:
      [rotateA, rotateB, rotateC, rotateD] = [-1, 0, 0, 1];
      break;
    case 90:
      [rotateA, rotateB, rotateC, rotateD] = [0, 1, 1, 0];
      break;
    case 270:
      [rotateA, rotateB, rotateC, rotateD] = [0, -1, -1, 0];
      break;
    default:
      [rotateA, rotateB, rotateC, rotateD] = [1, 0, 0, -1];
  }

  const offsetCanvasX =
    rotateA === 0 ? Math.abs(centerY - y0) * scale : Math.abs(centerX - x0) * scale;
  const offsetCanvasY =
    rotateA === 0 ? Math.abs(centerX - x0) * scale : Math.abs(centerY - y0) * scale;

  const transform: readonly [number, number, number, number, number, number] = [
    rotateA * scale,
    rotateB * scale,
    rotateC * scale,
    rotateD * scale,
    offsetCanvasX - rotateA * scale * centerX - rotateC * scale * centerY,
    offsetCanvasY - rotateB * scale * centerX - rotateD * scale * centerY,
  ];

  const width = rotateA === 0 ? (y1 - y0) * scale : (x1 - x0) * scale;
  const height = rotateA === 0 ? (x1 - x0) * scale : (y1 - y0) * scale;

  return {
    width,
    height,
    toViewportPoint: (x: number, y: number): readonly [number, number] => [
      x * transform[0] + y * transform[2] + transform[4],
      x * transform[1] + y * transform[3] + transform[5],
    ],
  };
}

/** A standard US Letter page in PDF points, unrotated: 612 x 792. */
const LETTER_PAGE: PdfPageBox = [0, 0, 612, 792];

describe('computeHighlightRect', () => {
  it('places a box at the top-left of the page at the top-left of the viewport', () => {
    const { toViewportPoint } = pdfjsViewportTransform(LETTER_PAGE, 1, 0);
    const rect = computeHighlightRect(LETTER_PAGE, [0, 0, 0.1, 0.05], toViewportPoint);
    expect(rect.left).toBeCloseTo(0);
    expect(rect.top).toBeCloseTo(0);
    expect(rect.width).toBeCloseTo(61.2);
    expect(rect.height).toBeCloseTo(39.6);
  });

  it('places a box at the bottom-right of the page at the bottom-right of the viewport', () => {
    const { toViewportPoint, width, height } = pdfjsViewportTransform(LETTER_PAGE, 1, 0);
    const rect = computeHighlightRect(LETTER_PAGE, [0.9, 0.95, 0.1, 0.05], toViewportPoint);
    expect(rect.left + rect.width).toBeCloseTo(width);
    expect(rect.top + rect.height).toBeCloseTo(height);
  });

  it('scales the highlight proportionally with zoom', () => {
    const boundingBox: readonly [number, number, number, number] = [0.1, 0.2, 0.2, 0.1];
    const at1x = pdfjsViewportTransform(LETTER_PAGE, 1, 0);
    const at2x = pdfjsViewportTransform(LETTER_PAGE, 2, 0);

    const rectAt1x = computeHighlightRect(LETTER_PAGE, boundingBox, at1x.toViewportPoint);
    const rectAt2x = computeHighlightRect(LETTER_PAGE, boundingBox, at2x.toViewportPoint);

    expect(rectAt2x.left).toBeCloseTo(rectAt1x.left * 2);
    expect(rectAt2x.top).toBeCloseTo(rectAt1x.top * 2);
    expect(rectAt2x.width).toBeCloseTo(rectAt1x.width * 2);
    expect(rectAt2x.height).toBeCloseTo(rectAt1x.height * 2);
  });

  it.each([0, 90, 180, 270])(
    'keeps the highlight within the rotated viewport bounds at %i degrees',
    (rotation) => {
      const { toViewportPoint, width, height } = pdfjsViewportTransform(LETTER_PAGE, 1, rotation);
      const rect = computeHighlightRect(LETTER_PAGE, [0.1, 0.1, 0.3, 0.2], toViewportPoint);

      expect(rect.width).toBeGreaterThan(0);
      expect(rect.height).toBeGreaterThan(0);
      expect(rect.left).toBeGreaterThanOrEqual(-0.01);
      expect(rect.top).toBeGreaterThanOrEqual(-0.01);
      expect(rect.left + rect.width).toBeLessThanOrEqual(width + 0.01);
      expect(rect.top + rect.height).toBeLessThanOrEqual(height + 0.01);
    },
  );

  it('rotating 180 degrees moves a top-left box to the opposite corner', () => {
    const upright = pdfjsViewportTransform(LETTER_PAGE, 1, 0);
    const flipped = pdfjsViewportTransform(LETTER_PAGE, 1, 180);
    const boundingBox: readonly [number, number, number, number] = [0, 0, 0.1, 0.05];

    const uprightRect = computeHighlightRect(LETTER_PAGE, boundingBox, upright.toViewportPoint);
    const flippedRect = computeHighlightRect(LETTER_PAGE, boundingBox, flipped.toViewportPoint);

    // Upright: top-left corner. Rotated 180: bottom-right corner.
    expect(uprightRect.left).toBeCloseTo(0);
    expect(uprightRect.top).toBeCloseTo(0);
    expect(flippedRect.left + flippedRect.width).toBeCloseTo(flipped.width);
    expect(flippedRect.top + flippedRect.height).toBeCloseTo(flipped.height);
  });

  it('rotating 90 degrees swaps which page axis maps to viewport width', () => {
    const rotated90 = pdfjsViewportTransform(LETTER_PAGE, 1, 90);
    // Page width (612) becomes the viewport's height at a 90-degree rotation.
    expect(rotated90.width).toBeCloseTo(792);
    expect(rotated90.height).toBeCloseTo(612);
  });
});

describe('EvidenceHighlightOverlay', () => {
  const identityTransform = (x: number, y: number): readonly [number, number] => [x, y];

  it('renders nothing when boundingBox is null', () => {
    const { container } = render(
      <EvidenceHighlightOverlay
        pageView={LETTER_PAGE}
        boundingBox={null}
        toViewportPoint={identityTransform}
        label="Gross monthly income"
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders a positioned, decorative highlight when boundingBox is present', () => {
    const { container } = render(
      <EvidenceHighlightOverlay
        pageView={LETTER_PAGE}
        boundingBox={[0.1, 0.1, 0.2, 0.05]}
        toViewportPoint={identityTransform}
        label="Gross monthly income"
      />,
    );
    const highlight = container.firstElementChild;
    expect(highlight).not.toBeNull();
    expect(highlight).toHaveAttribute('aria-hidden', 'true');
    expect(highlight).toHaveAttribute('title', 'Gross monthly income');
  });
});
