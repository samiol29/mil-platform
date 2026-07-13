import { describe, expect, it } from 'vitest';

import type { Document } from '@entities/document/queries';

import { duplicateDocumentIds, findDuplicateGroups } from './findDuplicateGroups';

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    partyId: null,
    filename: 'bank-statement.pdf',
    documentType: 'BANK_STATEMENT',
    ingestionStatus: 'COMPLETED',
    contentHash: 'a'.repeat(64),
    uploadedAt: '2026-01-01T00:00:00Z',
    uploadedBy: '33333333-3333-4333-a333-333333333333',
    evidenceItemCount: 0,
    pageCount: 1,
    ingestionCompletedAt: '2026-01-01T00:05:00Z',
    ingestionError: null,
    retryCount: 0,
    ...overrides,
  };
}

describe('findDuplicateGroups', () => {
  it('returns no groups when every document has a unique contentHash', () => {
    const groups = findDuplicateGroups([
      makeDocument({ id: 'a', contentHash: 'a'.repeat(64) }),
      makeDocument({ id: 'b', contentHash: 'b'.repeat(64) }),
    ]);
    expect(groups.size).toBe(0);
  });

  it('groups two documents sharing the same contentHash', () => {
    const groups = findDuplicateGroups([
      makeDocument({ id: 'a', contentHash: 'a'.repeat(64) }),
      makeDocument({ id: 'b', contentHash: 'a'.repeat(64) }),
      makeDocument({ id: 'c', contentHash: 'c'.repeat(64) }),
    ]);
    expect(groups.size).toBe(1);
    expect(
      groups
        .get('a'.repeat(64))
        ?.map((d) => d.id)
        .sort(),
    ).toEqual(['a', 'b']);
  });

  it('a single document with a unique hash is never flagged as a duplicate group', () => {
    const groups = findDuplicateGroups([makeDocument({ id: 'a', contentHash: 'a'.repeat(64) })]);
    expect(groups.size).toBe(0);
  });
});

describe('duplicateDocumentIds', () => {
  it('returns the ids of every document in a duplicate group', () => {
    const ids = duplicateDocumentIds([
      makeDocument({ id: 'a', contentHash: 'a'.repeat(64) }),
      makeDocument({ id: 'b', contentHash: 'a'.repeat(64) }),
      makeDocument({ id: 'c', contentHash: 'c'.repeat(64) }),
    ]);
    expect(ids).toEqual(new Set(['a', 'b']));
  });

  it('returns an empty set when there are no duplicates', () => {
    const ids = duplicateDocumentIds([makeDocument({ id: 'a' })]);
    expect(ids.size).toBe(0);
  });
});
