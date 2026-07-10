import { describe, expect, it } from 'vitest';

import type { Document } from '@entities/document/queries';
import type { Finding } from '@entities/finding/queries';

import {
  allDocumentsTerminal,
  deriveApplicationStages,
  summarizeDocuments,
  zeroFindingsOutcome,
} from './applicationPipelineSummary';

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
    evidenceItemCount: 1,
    pageCount: 1,
    ingestionCompletedAt: '2026-01-01T00:05:00Z',
    ingestionError: null,
    ...overrides,
  };
}

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: '44444444-4444-4444-a444-444444444444',
    applicationId: '22222222-2222-4222-a222-222222222222',
    what: 'Income mismatch',
    why: 'Stated income does not match pay stub',
    evidenceRefs: ['55555555-5555-4555-a555-555555555555'],
    confidence: 'high',
    recommendedAction: 'Review pay stub',
    state: 'unreviewed',
    modelVersion: 'v1',
    promptVersion: 'v1',
    extractionVersion: 'v1',
    policyVersion: null,
    escalatedToRole: null,
    escalatedToUserId: null,
    createdAt: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function statusOf(steps: ReturnType<typeof deriveApplicationStages>, id: string) {
  return steps.find((step) => step.id === id)?.status;
}

describe('summarizeDocuments', () => {
  it('counts by ingestion status', () => {
    const counts = summarizeDocuments([
      makeDocument({ ingestionStatus: 'COMPLETED' }),
      makeDocument({ ingestionStatus: 'COMPLETED' }),
      makeDocument({ ingestionStatus: 'IN_PROGRESS' }),
      makeDocument({ ingestionStatus: 'PENDING' }),
      makeDocument({ ingestionStatus: 'FAILED' }),
    ]);
    expect(counts).toEqual({ total: 5, ready: 2, processing: 2, failed: 1 });
  });
});

describe('allDocumentsTerminal', () => {
  it('is false for zero documents', () => {
    expect(allDocumentsTerminal([])).toBe(false);
  });

  it('is true when every document is COMPLETED or FAILED', () => {
    expect(
      allDocumentsTerminal([
        makeDocument({ ingestionStatus: 'COMPLETED' }),
        makeDocument({ ingestionStatus: 'FAILED' }),
      ]),
    ).toBe(true);
  });

  it('is false while any document is still PENDING or IN_PROGRESS', () => {
    expect(
      allDocumentsTerminal([
        makeDocument({ ingestionStatus: 'COMPLETED' }),
        makeDocument({ ingestionStatus: 'IN_PROGRESS' }),
      ]),
    ).toBe(false);
  });
});

describe('zeroFindingsOutcome', () => {
  it('is "pending" while any document is still processing', () => {
    expect(
      zeroFindingsOutcome([
        makeDocument({ ingestionStatus: 'COMPLETED' }),
        makeDocument({ ingestionStatus: 'IN_PROGRESS' }),
      ]),
    ).toBe('pending');
  });

  it('is "pending" with zero documents', () => {
    expect(zeroFindingsOutcome([])).toBe('pending');
  });

  it('is "clean" when every document is COMPLETED — the only honest "no material issues" case', () => {
    expect(
      zeroFindingsOutcome([
        makeDocument({ ingestionStatus: 'COMPLETED' }),
        makeDocument({ ingestionStatus: 'COMPLETED' }),
      ]),
    ).toBe('clean');
  });

  it('is "failures" when documents are terminal but at least one FAILED — never reported as a clean pass', () => {
    expect(
      zeroFindingsOutcome([
        makeDocument({ ingestionStatus: 'COMPLETED' }),
        makeDocument({ ingestionStatus: 'FAILED' }),
      ]),
    ).toBe('failures');
  });

  it('is "failures" when every document FAILED', () => {
    expect(
      zeroFindingsOutcome([
        makeDocument({ ingestionStatus: 'FAILED' }),
        makeDocument({ ingestionStatus: 'FAILED' }),
      ]),
    ).toBe('failures');
  });
});

describe('deriveApplicationStages', () => {
  it('no findings yet: Findings/Policy pending, Ready for Review active', () => {
    const steps = deriveApplicationStages([makeDocument()], []);
    expect(statusOf(steps, 'findings')).toBe('pending');
    expect(statusOf(steps, 'policy')).toBe('pending');
    expect(statusOf(steps, 'ready-for-review')).toBe('active');
  });

  it('findings exist but not all policy-evaluated: Policy active', () => {
    const steps = deriveApplicationStages(
      [makeDocument()],
      [makeFinding({ policyVersion: null })],
    );
    expect(statusOf(steps, 'findings')).toBe('complete');
    expect(statusOf(steps, 'policy')).toBe('active');
  });

  it('every finding policy-evaluated and every document terminal: Ready for Review complete', () => {
    const steps = deriveApplicationStages(
      [makeDocument({ ingestionStatus: 'COMPLETED' })],
      [makeFinding({ policyVersion: 'v1' })],
    );
    expect(statusOf(steps, 'policy')).toBe('complete');
    expect(statusOf(steps, 'ready-for-review')).toBe('complete');
  });

  it('a FAILED document does not block Ready for Review — it counts as terminal, not a blocker', () => {
    const steps = deriveApplicationStages(
      [
        makeDocument({ ingestionStatus: 'COMPLETED' }),
        makeDocument({ ingestionStatus: 'FAILED', ingestionError: 'Gemini API error' }),
      ],
      [makeFinding({ policyVersion: 'v1' })],
    );
    expect(statusOf(steps, 'ready-for-review')).toBe('complete');
  });

  it('a still-processing document blocks Ready for Review', () => {
    const steps = deriveApplicationStages(
      [
        makeDocument({ ingestionStatus: 'COMPLETED' }),
        makeDocument({ ingestionStatus: 'IN_PROGRESS' }),
      ],
      [makeFinding({ policyVersion: 'v1' })],
    );
    expect(statusOf(steps, 'ready-for-review')).toBe('active');
  });

  it('zero documents never reports Ready for Review as complete', () => {
    const steps = deriveApplicationStages([], []);
    expect(statusOf(steps, 'ready-for-review')).toBe('active');
  });

  it('labels Ready for Review as an estimate, never a backend guarantee', () => {
    const steps = deriveApplicationStages([makeDocument()], [makeFinding({ policyVersion: 'v1' })]);
    const readyStep = steps.find((step) => step.id === 'ready-for-review');
    expect(readyStep?.label).toContain('estimated');
    expect(readyStep?.detail).toContain('not a backend-verified readiness check');
  });
});
