/**
 * Evidence grouped by source document (Product Experience phase, Phase 5,
 * extracted in Phase 8 so `EvidenceRegion` and `DocumentInspector`
 * — `features/document-viewer/DocumentInspector.tsx` — share one
 * implementation instead of two copies of the same reduction).
 */

import type { EvidenceItem } from '@entities/evidence/queries';

export function groupEvidenceByDocument(
  evidenceItems: readonly EvidenceItem[],
): ReadonlyMap<string, readonly EvidenceItem[]> {
  const groups = new Map<string, EvidenceItem[]>();
  for (const item of evidenceItems) {
    const existing = groups.get(item.documentId);
    if (existing) existing.push(item);
    else groups.set(item.documentId, [item]);
  }
  return groups;
}
