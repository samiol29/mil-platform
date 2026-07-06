/**
 * EvidenceHighlightOverlay (spec 002 tasks.md T065; 003 FR-058).
 *
 * Renders the highlight computed by `coordinateMapping.ts` — see that
 * module for the coordinate-mapping design rationale.
 */

import {
  computeHighlightRect,
  type FractionalBoundingBox,
  type PdfPageBox,
} from './coordinateMapping';

export interface EvidenceHighlightOverlayProps {
  readonly pageView: PdfPageBox;
  readonly boundingBox: FractionalBoundingBox | null;
  readonly toViewportPoint: (x: number, y: number) => readonly [number, number];
  readonly label: string;
}

/**
 * Absolutely-positioned highlight rect over a rendered PDF page. Renders
 * nothing when `boundingBox` is `null` (an evidence item with no
 * determinable location — a real, expected state, not an error).
 *
 * `aria-hidden`: the highlight is a visual affordance duplicating
 * information already available as text (the evidence's value and the
 * Finding's `why`) — it carries no information a screen-reader user would
 * otherwise miss.
 */
export function EvidenceHighlightOverlay({
  pageView,
  boundingBox,
  toViewportPoint,
  label,
}: EvidenceHighlightOverlayProps) {
  if (boundingBox === null) return null;

  const rect = computeHighlightRect(pageView, boundingBox, toViewportPoint);

  return (
    <div
      aria-hidden="true"
      title={label}
      className="border-feedback-warning-fg bg-feedback-warning-bg pointer-events-none absolute rounded-sm border-2 opacity-70"
      style={{
        left: `${String(rect.left)}px`,
        top: `${String(rect.top)}px`,
        width: `${String(rect.width)}px`,
        height: `${String(rect.height)}px`,
      }}
    />
  );
}
