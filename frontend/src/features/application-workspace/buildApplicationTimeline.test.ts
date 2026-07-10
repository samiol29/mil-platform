import { describe, expect, it } from 'vitest';

import type { AuditTrailEntry } from '@entities/audit/types';
import type { Document } from '@entities/document/queries';
import type { Finding } from '@entities/finding/queries';

import { buildApplicationTimeline } from './buildApplicationTimeline';

const DOCUMENT_ID = '33333333-3333-4333-a333-333333333333';
const FINDING_ID = '66666666-6666-4666-a666-666666666666';

function makeAuditEntry(overrides: Partial<AuditTrailEntry> = {}): AuditTrailEntry {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    eventType: 'APPLICATION_CREATED',
    entityType: 'APPLICATION',
    entityId: '22222222-2222-4222-a222-222222222222',
    actorId: null,
    actorType: 'USER',
    eventData: {},
    occurredAt: '2026-06-20T09:00:00Z',
    sequenceNumber: 1,
    ...overrides,
  };
}

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: DOCUMENT_ID,
    applicationId: '22222222-2222-4222-a222-222222222222',
    partyId: null,
    filename: 'bank-statement.pdf',
    documentType: 'BANK_STATEMENT',
    ingestionStatus: 'COMPLETED',
    contentHash: 'a'.repeat(64),
    uploadedAt: '2026-06-20T09:00:00Z',
    uploadedBy: '44444444-4444-4444-a444-444444444444',
    evidenceItemCount: 1,
    pageCount: 3,
    ingestionCompletedAt: '2026-06-20T09:05:00Z',
    ingestionError: null,
    ...overrides,
  };
}

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: FINDING_ID,
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

describe('buildApplicationTimeline', () => {
  it('labels APPLICATION_STATE_CHANGED using real from/to status fields', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({
          eventType: 'APPLICATION_STATE_CHANGED',
          eventData: { fromStatus: 'DRAFT', toStatus: 'SUBMITTED' },
        }),
      ],
      [],
      [],
    );
    expect(timeline[0]?.label).toBe('Status changed from DRAFT to SUBMITTED');
  });

  it('labels DOCUMENT_UPLOADED with a document trace pointing at the real document id', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({
          eventType: 'DOCUMENT_UPLOADED',
          entityType: 'DOCUMENT',
          entityId: DOCUMENT_ID,
          eventData: { originalFilename: 'bank-statement.pdf' },
        }),
      ],
      [makeDocument()],
      [],
    );
    expect(timeline[0]?.label).toBe('Document uploaded: bank-statement.pdf');
    expect(timeline[0]?.trace).toEqual({ kind: 'document', documentId: DOCUMENT_ID });
  });

  it('resolves the real document filename for DOCUMENT_INGESTION_COMPLETED with page/evidence counts', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({
          eventType: 'DOCUMENT_INGESTION_COMPLETED',
          entityType: 'DOCUMENT',
          entityId: DOCUMENT_ID,
          eventData: { pageCount: 3, evidenceItemCount: 2 },
        }),
      ],
      [makeDocument()],
      [],
    );
    expect(timeline[0]?.label).toBe(
      'Processing completed: bank-statement.pdf (3 pages, 2 evidence items)',
    );
  });

  it('resolves the real finding text for FINDING_GENERATED via entityId', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({
          eventType: 'FINDING_GENERATED',
          entityType: 'FINDING',
          entityId: FINDING_ID,
        }),
      ],
      [],
      [makeFinding()],
    );
    expect(timeline[0]?.label).toBe('Finding generated: Income mismatch');
    expect(timeline[0]?.trace).toEqual({ kind: 'finding', findingId: FINDING_ID });
  });

  it('resolves the real finding via eventData.findingId for REVIEW_FINDING_OVERRIDDEN (entityId is the session, not the finding)', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({
          eventType: 'REVIEW_FINDING_OVERRIDDEN',
          entityType: 'REVIEW_SESSION',
          entityId: 'some-session-id',
          eventData: {
            findingId: FINDING_ID,
            reason: 'Borrower confirmed a raise.',
            previousValue: '6200.00',
            newValue: '6500.00',
          },
        }),
      ],
      [],
      [makeFinding()],
    );
    expect(timeline[0]?.label).toBe(
      'Finding overridden: Income mismatch — "Borrower confirmed a raise." (was 6200.00 → 6500.00)',
    );
    expect(timeline[0]?.trace).toEqual({ kind: 'finding', findingId: FINDING_ID });
  });

  it('labels POLICY_EVALUATED with the real policy version and outcome, tied to the finding', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({
          eventType: 'POLICY_EVALUATED',
          entityType: 'POLICY_RESULT',
          entityId: 'result-id',
          eventData: {
            findingId: FINDING_ID,
            policyVersion: 'policy-pack-2026.2',
            outcome: 'flagged',
          },
        }),
      ],
      [],
      [makeFinding()],
    );
    expect(timeline[0]?.label).toBe(
      'Policy evaluated (vpolicy-pack-2026.2) for Income mismatch: flagged',
    );
  });

  it('silently omits unrecognized event types (e.g. Copilot activity) rather than showing a raw fallback', () => {
    const timeline = buildApplicationTimeline(
      [makeAuditEntry({ eventType: 'COPILOT_QUERY_RECORDED', entityType: 'COPILOT_QUERY' })],
      [],
      [],
    );
    expect(timeline).toEqual([]);
  });

  it('sorts entries chronologically, ascending', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({ id: 'later', occurredAt: '2026-06-23T09:00:00Z' }),
        makeAuditEntry({ id: 'earlier', occurredAt: '2026-06-20T09:00:00Z' }),
      ],
      [],
      [],
    );
    expect(timeline.map((entry) => entry.id)).toEqual(['earlier', 'later']);
  });

  it('never fabricates a reason for events that carry none (APPLICATION_STATE_CHANGED)', () => {
    const timeline = buildApplicationTimeline(
      [
        makeAuditEntry({
          eventType: 'APPLICATION_STATE_CHANGED',
          eventData: { fromStatus: 'SUBMITTED', toStatus: 'IN_REVIEW' },
        }),
      ],
      [],
      [],
    );
    expect(timeline[0]?.label).not.toMatch(/because|reason/i);
  });
});
