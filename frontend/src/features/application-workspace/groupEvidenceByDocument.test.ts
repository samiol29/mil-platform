import { describe, expect, it } from 'vitest';

import type { EvidenceItem } from '@entities/evidence/queries';

import { groupEvidenceByDocument } from './groupEvidenceByDocument';

function makeItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    documentId: '33333333-3333-4333-a333-333333333333',
    partyId: null,
    evidenceType: 'gross_monthly_income',
    valueText: '6200.00',
    valueNumeric: null,
    currency: null,
    pageNumber: 1,
    fieldLocation: null,
    confidence: 'high',
    extractionMethod: 'LLM_EXTRACTION_V1',
    extractionModelVersion: '2026.06.1',
    extractedAt: '2026-06-21T10:15:00Z',
    supersedesId: null,
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

describe('groupEvidenceByDocument', () => {
  it('groups evidence items by their real documentId', () => {
    const groups = groupEvidenceByDocument([
      makeItem({ id: 'a', documentId: 'doc-1' }),
      makeItem({ id: 'b', documentId: 'doc-1' }),
      makeItem({ id: 'c', documentId: 'doc-2' }),
    ]);
    expect(groups.get('doc-1')?.map((item) => item.id)).toEqual(['a', 'b']);
    expect(groups.get('doc-2')?.map((item) => item.id)).toEqual(['c']);
  });

  it('returns undefined for a document with no evidence', () => {
    const groups = groupEvidenceByDocument([makeItem({ id: 'a', documentId: 'doc-1' })]);
    expect(groups.get('doc-2')).toBeUndefined();
  });

  it('returns an empty map for no evidence', () => {
    expect(groupEvidenceByDocument([]).size).toBe(0);
  });
});
