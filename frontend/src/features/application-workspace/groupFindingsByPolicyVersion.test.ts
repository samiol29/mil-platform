import { describe, expect, it } from 'vitest';

import type { Finding } from '@entities/finding/queries';

import { groupFindingsByPolicyVersion } from './groupFindingsByPolicyVersion';

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
    policyVersion: 'policy-pack-2026.2',
    escalatedToRole: null,
    escalatedToUserId: null,
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

describe('groupFindingsByPolicyVersion', () => {
  it('groups findings sharing the same real policyVersion', () => {
    const groups = groupFindingsByPolicyVersion([
      makeFinding({ id: 'a', policyVersion: 'policy-pack-2026.2' }),
      makeFinding({ id: 'b', policyVersion: 'policy-pack-2026.2' }),
      makeFinding({ id: 'c', policyVersion: 'policy-pack-2026.1' }),
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0]?.policyVersion).toBe('policy-pack-2026.1');
    expect(groups[1]?.policyVersion).toBe('policy-pack-2026.2');
    expect(groups[1]?.findings.map((f) => f.id)).toEqual(['a', 'b']);
  });

  it('puts findings with a null policyVersion in their own "not yet evaluated" bucket, always last', () => {
    const groups = groupFindingsByPolicyVersion([
      makeFinding({ id: 'a', policyVersion: null }),
      makeFinding({ id: 'b', policyVersion: 'policy-pack-2026.2' }),
    ]);
    expect(groups.at(-1)?.policyVersion).toBeNull();
    expect(groups.at(-1)?.findings.map((f) => f.id)).toEqual(['a']);
  });

  it('counts findings awaiting judgment (unreviewed/escalated) separately from resolved (verified/overridden)', () => {
    const groups = groupFindingsByPolicyVersion([
      makeFinding({ id: 'a', state: 'unreviewed' }),
      makeFinding({ id: 'b', state: 'escalated' }),
      makeFinding({ id: 'c', state: 'verified' }),
      makeFinding({ id: 'd', state: 'overridden' }),
    ]);
    expect(groups[0]?.awaitingJudgmentCount).toBe(2);
    expect(groups[0]?.resolvedCount).toBe(2);
  });

  it('returns no groups for an empty finding list', () => {
    expect(groupFindingsByPolicyVersion([])).toEqual([]);
  });
});
