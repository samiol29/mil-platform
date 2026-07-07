/**
 * Evidence → Findings reverse index (Product Experience phase, Phase 5).
 *
 * Nothing today maps an `EvidenceItem.id` back to the `Finding`(s) citing
 * it — `Finding.evidenceRefs` only points forward (finding → evidence).
 * This is the client-side reverse of that same real field, not a new
 * backend capability: "used in N finding(s)" on an evidence card is exactly
 * as honest as the forward-direction evidence chips `FindingCard` already
 * renders.
 */

import type { Finding } from '@entities/finding/queries';

export function buildEvidenceToFindingsIndex(
  findings: readonly Finding[],
): ReadonlyMap<string, readonly Finding[]> {
  const index = new Map<string, Finding[]>();
  for (const finding of findings) {
    for (const evidenceId of finding.evidenceRefs) {
      const existing = index.get(evidenceId);
      if (existing) existing.push(finding);
      else index.set(evidenceId, [finding]);
    }
  }
  return index;
}
