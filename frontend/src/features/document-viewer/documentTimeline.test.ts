import { describe, expect, it } from 'vitest';

import type { AuditTrailEntry } from '@entities/audit/types';
import type { EvidenceItem } from '@entities/evidence/queries';
import type { Finding } from '@entities/finding/queries';

import { buildDocumentTimeline } from './documentTimeline';

const DOCUMENT_ID = '33333333-3333-4333-a333-333333333333';
const OTHER_DOCUMENT_ID = '44444444-4444-4444-a444-444444444444';
const EVIDENCE_ID = '55555555-5555-4555-a555-555555555555';
const FINDING_ID = '66666666-6666-4666-a666-666666666666';

function makeAuditEntry(overrides: Partial<AuditTrailEntry> = {}): AuditTrailEntry {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    eventType: 'DOCUMENT_UPLOADED',
    entityType: 'DOCUMENT',
    entityId: DOCUMENT_ID,
    actorId: null,
    actorType: 'USER',
    eventData: {},
    occurredAt: '2026-06-20T09:00:00Z',
    sequenceNumber: 1,
    ...overrides,
  };
}

function makeEvidenceItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: EVIDENCE_ID,
    applicationId: '22222222-2222-4222-a222-222222222222',
    documentId: DOCUMENT_ID,
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

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: FINDING_ID,
    applicationId: '22222222-2222-4222-a222-222222222222',
    what: 'Income mismatch',
    why: 'Reported income differs from the pay stub.',
    evidenceRefs: [EVIDENCE_ID],
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

describe('buildDocumentTimeline', () => {
  it('includes a DOCUMENT_UPLOADED event matched by entityType/entityId, not eventData', () => {
    const timeline = buildDocumentTimeline(
      [
        makeAuditEntry({
          eventType: 'DOCUMENT_UPLOADED',
          entityType: 'DOCUMENT',
          entityId: DOCUMENT_ID,
        }),
      ],
      DOCUMENT_ID,
      [],
      [],
    );
    expect(timeline).toHaveLength(1);
    expect(timeline[0]?.label).toBe('Document uploaded');
  });

  it('excludes a DOCUMENT_UPLOADED event for a different document', () => {
    const timeline = buildDocumentTimeline(
      [makeAuditEntry({ entityId: OTHER_DOCUMENT_ID })],
      DOCUMENT_ID,
      [],
      [],
    );
    expect(timeline).toEqual([]);
  });

  it('includes an EVIDENCE_CREATED event matched by eventData.documentId', () => {
    const timeline = buildDocumentTimeline(
      [
        makeAuditEntry({
          eventType: 'EVIDENCE_CREATED',
          entityType: 'EVIDENCE_ITEM',
          entityId: EVIDENCE_ID,
          eventData: { documentId: DOCUMENT_ID },
        }),
      ],
      DOCUMENT_ID,
      [],
      [],
    );
    expect(timeline[0]?.label).toBe('Evidence extracted from this document');
  });

  it("includes a REVIEW_FINDING_OVERRIDDEN event only when its finding cites this document's evidence", () => {
    const evidenceItems = [makeEvidenceItem({ documentId: DOCUMENT_ID })];
    const findings = [makeFinding({ evidenceRefs: [EVIDENCE_ID] })];
    const timeline = buildDocumentTimeline(
      [
        makeAuditEntry({
          eventType: 'REVIEW_FINDING_OVERRIDDEN',
          entityType: 'REVIEW_SESSION',
          entityId: 'some-session-id',
          eventData: { findingId: FINDING_ID, reason: 'Confirmed with borrower' },
        }),
      ],
      DOCUMENT_ID,
      evidenceItems,
      findings,
    );
    expect(timeline[0]?.label).toBe('A finding on this document was overridden');
  });

  it("excludes a REVIEW_FINDING_* event whose finding cites a different document's evidence", () => {
    const evidenceItems = [makeEvidenceItem({ documentId: OTHER_DOCUMENT_ID })];
    const findings = [makeFinding({ evidenceRefs: [EVIDENCE_ID] })];
    const timeline = buildDocumentTimeline(
      [
        makeAuditEntry({
          eventType: 'REVIEW_FINDING_APPROVED',
          eventData: { findingId: FINDING_ID },
        }),
      ],
      DOCUMENT_ID,
      evidenceItems,
      findings,
    );
    expect(timeline).toEqual([]);
  });

  it('ignores unrecognized event types', () => {
    const timeline = buildDocumentTimeline(
      [makeAuditEntry({ eventType: 'APPLICATION_STATUS_CHANGED', entityType: 'APPLICATION' })],
      DOCUMENT_ID,
      [],
      [],
    );
    expect(timeline).toEqual([]);
  });

  it('sorts entries chronologically', () => {
    const timeline = buildDocumentTimeline(
      [
        makeAuditEntry({ id: 'later', occurredAt: '2026-06-23T09:00:00Z' }),
        makeAuditEntry({ id: 'earlier', occurredAt: '2026-06-20T09:00:00Z' }),
      ],
      DOCUMENT_ID,
      [],
      [],
    );
    expect(timeline.map((entry) => entry.id)).toEqual(['earlier', 'later']);
  });
});
