import { describe, expect, it } from 'vitest';

import type { Finding } from '@entities/finding/queries';

import { buildEvidenceToFindingsIndex } from './evidenceFindingIndex';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    what: 'Income mismatch',
    why: 'Reported income differs from the pay stub.',
    evidenceRefs: ['33333333-3333-4333-a333-333333333333'],
    confidence: 'high',
    recommendedAction: 'Confirm with borrower.',
    state: 'unreviewed',
    modelVersion: 'v1',
    promptVersion: 'v1',
    extractionVersion: 'v1',
    policyVersion: null,
    escalatedToRole: null,
    escalatedToUserId: null,
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

describe('buildEvidenceToFindingsIndex', () => {
  it('maps an evidence id to every finding that cites it', () => {
    const findingA = makeFinding({ id: 'a', evidenceRefs: ['e1'] });
    const findingB = makeFinding({ id: 'b', evidenceRefs: ['e1', 'e2'] });
    const index = buildEvidenceToFindingsIndex([findingA, findingB]);

    expect(index.get('e1')?.map((f) => f.id)).toEqual(['a', 'b']);
    expect(index.get('e2')?.map((f) => f.id)).toEqual(['b']);
  });

  it('returns undefined for an evidence id no finding cites', () => {
    const index = buildEvidenceToFindingsIndex([makeFinding({ evidenceRefs: ['e1'] })]);
    expect(index.get('e2')).toBeUndefined();
  });

  it('returns an empty index for no findings', () => {
    const index = buildEvidenceToFindingsIndex([]);
    expect(index.size).toBe(0);
  });
});
