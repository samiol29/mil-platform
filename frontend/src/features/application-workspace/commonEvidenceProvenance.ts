/**
 * Common extraction provenance across a document's evidence items (final
 * polish sprint). Every item in a group is almost always extracted by the
 * same pipeline run (one OCR/extraction pass per document), so
 * `extractionMethod`/`extractionModelVersion` are identical across the
 * whole group in practice — `EvidenceCard` repeating "Extracted via X ·
 * model Y · <date>" on every single card (sometimes a dozen+ per document)
 * was pure noise, the same sentence duplicated verbatim down the page.
 *
 * Returns the shared provenance line once for the group's header when every
 * item genuinely agrees, or `null` when they don't (a real, if rare,
 * divergence — e.g. a superseding re-extraction on a different model) so
 * `EvidenceCard` falls back to showing its own line rather than hiding a
 * real difference.
 */

import type { EvidenceItem } from '@entities/evidence/queries';

export function commonEvidenceProvenance(
  items: readonly EvidenceItem[],
): { readonly method: string; readonly modelVersion: string; readonly extractedAt: string } | null {
  if (items.length === 0) return null;
  const [first, ...rest] = items;
  const agrees = rest.every(
    (item) =>
      item.extractionMethod === first.extractionMethod &&
      item.extractionModelVersion === first.extractionModelVersion,
  );
  if (!agrees) return null;
  return {
    method: first.extractionMethod,
    modelVersion: first.extractionModelVersion,
    extractedAt: first.extractedAt,
  };
}
