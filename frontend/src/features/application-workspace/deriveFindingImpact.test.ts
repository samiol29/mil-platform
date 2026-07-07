import { describe, expect, it } from 'vitest';

import type { Finding } from '@entities/finding/queries';

import { deriveFindingImpact } from './deriveFindingImpact';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    what: 'Income mismatch',
    why: 'Reported income differs from the pay stub.',
    evidenceRefs: ['e1'],
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

describe('deriveFindingImpact', () => {
  it('describes a high-confidence finding with its real evidence count', () => {
    expect(deriveFindingImpact(makeFinding({ confidence: 'high', evidenceRefs: ['e1', 'e2'] }))).toBe(
      'High confidence, supported by 2 evidence items.',
    );
  });

  it('uses singular "item" for exactly one piece of evidence', () => {
    expect(deriveFindingImpact(makeFinding({ confidence: 'medium', evidenceRefs: ['e1'] }))).toBe(
      'Medium confidence, supported by 1 evidence item.',
    );
  });

  it('recommends independent verification for low-confidence findings', () => {
    expect(deriveFindingImpact(makeFinding({ confidence: 'low', evidenceRefs: ['e1'] }))).toBe(
      'Low confidence — recommend independent verification (supported by 1 evidence item).',
    );
  });
});
