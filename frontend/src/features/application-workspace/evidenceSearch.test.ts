import { describe, expect, it } from 'vitest';

import type { EvidenceItem } from '@entities/evidence/queries';

import { matchesEvidenceSearch } from './evidenceSearch';

function makeItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    documentId: '33333333-3333-4333-a333-333333333333',
    partyId: null,
    evidenceType: 'gross_monthly_income',
    valueText: null,
    valueNumeric: '6200.00',
    currency: 'USD',
    pageNumber: 3,
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

describe('matchesEvidenceSearch', () => {
  it('matches an empty/whitespace query against anything', () => {
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', '')).toBe(true);
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', '   ')).toBe(true);
  });

  it('matches on the field name (evidenceType), including with underscores replaced', () => {
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', 'income')).toBe(true);
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', 'monthly income')).toBe(true);
  });

  it('matches on numeric value and currency', () => {
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', '6200')).toBe(true);
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', 'USD')).toBe(true);
  });

  it('matches on free-text value when present instead of a numeric value', () => {
    const item = makeItem({
      evidenceType: 'borrower_name',
      valueNumeric: null,
      currency: null,
      valueText: 'Daniel Carter',
    });
    expect(matchesEvidenceSearch(item, 'payslip.pdf', 'Daniel')).toBe(true);
    expect(matchesEvidenceSearch(item, 'payslip.pdf', 'carter')).toBe(true);
  });

  it('matches on the source document filename', () => {
    expect(matchesEvidenceSearch(makeItem(), '05_Payslip_January.pdf', 'payslip')).toBe(true);
  });

  it('matches on extraction method, model version, and confidence label', () => {
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', 'LLM_EXTRACTION_V1')).toBe(true);
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', '2026.06.1')).toBe(true);
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', 'high')).toBe(true);
  });

  it('is case-insensitive', () => {
    expect(matchesEvidenceSearch(makeItem(), 'Payslip.pdf', 'PAYSLIP')).toBe(true);
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', 'InCoMe')).toBe(true);
  });

  it('does not match unrelated text', () => {
    expect(matchesEvidenceSearch(makeItem(), 'payslip.pdf', 'liabilities')).toBe(false);
  });
});
