/**
 * Evidence Search Sprint — scoped only to the Evidence region's already-
 * fetched `EvidenceItem[]` (`useEvidenceForApplication` returns every item
 * for the application in one request, confirmed against
 * `GET /v1/applications/{id}/evidence`, which is unpaginated). No backend
 * change: this is a pure client-side predicate over data already in memory.
 *
 * Matches across every field an underwriter would plausibly search by:
 * the extracted field name (`evidenceType`), the extracted value (text or
 * numeric+currency), the source document's filename, the extraction
 * method/model, and the confidence label. `EvidenceItem` has no dedicated
 * "category" or supporting-text/snippet field (confirmed against
 * `entities/evidence/types.ts`) — nothing is fabricated to search against.
 */

import type { EvidenceItem } from '@entities/evidence/queries';

function formattedEvidenceType(evidenceType: string): string {
  return evidenceType.replaceAll('_', ' ');
}

function formattedValue(item: EvidenceItem): string {
  if (item.valueNumeric !== null) {
    return item.currency !== null ? `${item.currency} ${item.valueNumeric}` : item.valueNumeric;
  }
  return item.valueText ?? '';
}

/** The exact set of strings a match highlights within an `EvidenceCard`. */
export function evidenceSearchFields(item: EvidenceItem, filename: string): readonly string[] {
  return [
    item.evidenceType,
    formattedEvidenceType(item.evidenceType),
    formattedValue(item),
    filename,
    item.extractionMethod,
    item.extractionModelVersion,
    item.confidence,
  ];
}

export function matchesEvidenceSearch(item: EvidenceItem, filename: string, query: string): boolean {
  const normalizedQuery = query.trim().toLowerCase();
  if (normalizedQuery === '') return true;
  return evidenceSearchFields(item, filename).some((field) =>
    field.toLowerCase().includes(normalizedQuery),
  );
}
