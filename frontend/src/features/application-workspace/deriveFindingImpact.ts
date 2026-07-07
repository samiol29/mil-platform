/**
 * Finding impact synthesis (Product Experience phase, Phase 6 —
 * "Findings should answer 'so what?'"). There is no severity/impact/
 * priority field on `Finding` anywhere — not the frontend type, not the
 * backend model (`src/mil/finding/models.py`), not the API schema
 * (confirmed by direct inspection). This composes a plain-language line
 * entirely from two real, already-present fields (`confidence` and
 * `evidenceRefs.length`) — a UI-only synthesis, never presented as a
 * backend-assigned severity (the caption rendered alongside this in
 * `FindingCard.tsx` says so explicitly, matching Phase 4's "Ready for
 * Review (estimated)" honesty precedent).
 */

import type { Finding } from '@entities/finding/queries';

const CONFIDENCE_LABEL: Record<Finding['confidence'], string> = {
  high: 'High confidence',
  medium: 'Medium confidence',
  low: 'Low confidence',
};

export function deriveFindingImpact(finding: Finding): string {
  const evidenceCount = finding.evidenceRefs.length;
  const evidenceClause = `supported by ${String(evidenceCount)} evidence item${evidenceCount === 1 ? '' : 's'}`;

  if (finding.confidence === 'low') {
    return `${CONFIDENCE_LABEL.low} — recommend independent verification (${evidenceClause}).`;
  }
  return `${CONFIDENCE_LABEL[finding.confidence]}, ${evidenceClause}.`;
}
