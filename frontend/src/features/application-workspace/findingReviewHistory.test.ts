import { describe, expect, it } from 'vitest';

import type { AuditTrailEntry } from '@entities/audit/types';

import { buildFindingReviewHistory, groupReviewHistoryByFinding } from './findingReviewHistory';

const FINDING_ID = '44444444-4444-4444-a444-444444444444';
const OTHER_FINDING_ID = '55555555-5555-4555-a555-555555555555';

function makeEntry(overrides: Partial<AuditTrailEntry> = {}): AuditTrailEntry {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    eventType: 'REVIEW_FINDING_APPROVED',
    entityType: 'REVIEW_SESSION',
    entityId: '33333333-3333-4333-a333-333333333333',
    actorId: null,
    actorType: 'USER',
    eventData: { findingId: FINDING_ID },
    occurredAt: '2026-06-22T09:00:00Z',
    sequenceNumber: 1,
    ...overrides,
  };
}

describe('buildFindingReviewHistory', () => {
  it('includes only entries whose eventData.findingId matches this finding', () => {
    const entries = [
      makeEntry({ id: 'a', eventData: { findingId: FINDING_ID } }),
      makeEntry({ id: 'b', eventData: { findingId: OTHER_FINDING_ID } }),
    ];
    const history = buildFindingReviewHistory(entries, FINDING_ID);
    expect(history.map((h) => h.id)).toEqual(['a']);
  });

  it('ignores audit entries unrelated to a review decision', () => {
    const entries = [
      makeEntry({ id: 'a', eventType: 'DOCUMENT_UPLOADED', eventData: { findingId: FINDING_ID } }),
    ];
    expect(buildFindingReviewHistory(entries, FINDING_ID)).toEqual([]);
  });

  it('normalizes a verify (approved) event with no reason', () => {
    const history = buildFindingReviewHistory(
      [makeEntry({ eventType: 'REVIEW_FINDING_APPROVED', eventData: { findingId: FINDING_ID } })],
      FINDING_ID,
    );
    expect(history).toEqual([
      {
        id: '11111111-1111-4111-a111-111111111111',
        occurredAt: '2026-06-22T09:00:00Z',
        actorType: 'USER',
        kind: 'verified',
        reason: null,
        previousValue: null,
        newValue: null,
        targetRole: null,
      },
    ]);
  });

  it('normalizes an override event with its real reason and previous/new values', () => {
    const history = buildFindingReviewHistory(
      [
        makeEntry({
          eventType: 'REVIEW_FINDING_OVERRIDDEN',
          eventData: {
            findingId: FINDING_ID,
            reason: 'Borrower confirmed a raise.',
            previousValue: '6200.00',
            newValue: '6500.00',
          },
        }),
      ],
      FINDING_ID,
    );
    expect(history[0]).toMatchObject({
      kind: 'overridden',
      reason: 'Borrower confirmed a raise.',
      previousValue: '6200.00',
      newValue: '6500.00',
    });
  });

  it('normalizes an escalate event with its real reason and target role', () => {
    const history = buildFindingReviewHistory(
      [
        makeEntry({
          eventType: 'REVIEW_FINDING_ESCALATED',
          eventData: {
            findingId: FINDING_ID,
            reason: 'Needs compliance sign-off.',
            targetRole: 'COMPLIANCE_OFFICER',
          },
        }),
      ],
      FINDING_ID,
    );
    expect(history[0]).toMatchObject({
      kind: 'escalated',
      reason: 'Needs compliance sign-off.',
      targetRole: 'COMPLIANCE_OFFICER',
    });
  });

  it('sorts entries chronologically', () => {
    const entries = [
      makeEntry({ id: 'later', occurredAt: '2026-06-23T09:00:00Z' }),
      makeEntry({ id: 'earlier', occurredAt: '2026-06-20T09:00:00Z' }),
    ];
    const history = buildFindingReviewHistory(entries, FINDING_ID);
    expect(history.map((h) => h.id)).toEqual(['earlier', 'later']);
  });
});

describe('groupReviewHistoryByFinding', () => {
  it('groups every finding\'s history in a single pass, equivalent to calling buildFindingReviewHistory per finding', () => {
    const entries = [
      makeEntry({ id: 'a', eventData: { findingId: FINDING_ID } }),
      makeEntry({ id: 'b', eventData: { findingId: OTHER_FINDING_ID } }),
      makeEntry({
        id: 'c',
        eventType: 'REVIEW_FINDING_OVERRIDDEN',
        eventData: { findingId: FINDING_ID, reason: 'r', previousValue: 'p', newValue: 'n' },
      }),
    ];
    const grouped = groupReviewHistoryByFinding(entries);

    expect(grouped.get(FINDING_ID)?.map((h) => h.id)).toEqual(['a', 'c']);
    expect(grouped.get(OTHER_FINDING_ID)?.map((h) => h.id)).toEqual(['b']);
    expect(grouped.get(FINDING_ID)).toEqual(buildFindingReviewHistory(entries, FINDING_ID));
  });

  it('returns undefined for a finding with no review history', () => {
    const grouped = groupReviewHistoryByFinding([makeEntry({ eventData: { findingId: FINDING_ID } })]);
    expect(grouped.get(OTHER_FINDING_ID)).toBeUndefined();
  });

  it('sorts each finding\'s group chronologically independently', () => {
    const entries = [
      makeEntry({ id: 'later', occurredAt: '2026-06-23T09:00:00Z', eventData: { findingId: FINDING_ID } }),
      makeEntry({ id: 'earlier', occurredAt: '2026-06-20T09:00:00Z', eventData: { findingId: FINDING_ID } }),
    ];
    const grouped = groupReviewHistoryByFinding(entries);
    expect(grouped.get(FINDING_ID)?.map((h) => h.id)).toEqual(['earlier', 'later']);
  });
});
