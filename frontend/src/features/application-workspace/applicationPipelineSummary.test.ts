import { describe, expect, it } from 'vitest';

import type { EvaluationStatus } from '@entities/application/types';
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
    retryCount: 0,
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

function makeEvaluationStatus(overrides: Partial<EvaluationStatus> = {}): EvaluationStatus {
  return {
    status: 'NOT_TRIGGERED',
    errorMessage: null,
    retryable: false,
    startedAt: null,
    completedAt: null,
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
  it('is "not-submitted" for a DRAFT application, regardless of document status', () => {
    expect(
      zeroFindingsOutcome(
        [makeDocument({ ingestionStatus: 'COMPLETED' })],
        'DRAFT',
        makeEvaluationStatus(),
      ),
    ).toBe('not-submitted');
  });

  it('is "evaluation-failed" when the last FINDING_GENERATION run FAILED', () => {
    expect(
      zeroFindingsOutcome(
        [makeDocument({ ingestionStatus: 'COMPLETED' })],
        'SUBMITTED',
        makeEvaluationStatus({ status: 'FAILED', errorMessage: 'Gemini API returned HTTP 429' }),
      ),
    ).toBe('evaluation-failed');
  });

  it('is "pending" while any document is still processing', () => {
    expect(
      zeroFindingsOutcome(
        [makeDocument({ ingestionStatus: 'COMPLETED' }), makeDocument({ ingestionStatus: 'IN_PROGRESS' })],
        'SUBMITTED',
        makeEvaluationStatus({ status: 'RUNNING' }),
      ),
    ).toBe('pending');
  });

  it('is "pending" with zero documents', () => {
    expect(zeroFindingsOutcome([], 'SUBMITTED', makeEvaluationStatus())).toBe('pending');
  });

  it('is "clean" when every document is COMPLETED — the only honest "no material issues" case', () => {
    expect(
      zeroFindingsOutcome(
        [makeDocument({ ingestionStatus: 'COMPLETED' }), makeDocument({ ingestionStatus: 'COMPLETED' })],
        'SUBMITTED',
        makeEvaluationStatus({ status: 'COMPLETED' }),
      ),
    ).toBe('clean');
  });

  it('is "failures" when documents are terminal but at least one FAILED — never reported as a clean pass', () => {
    expect(
      zeroFindingsOutcome(
        [makeDocument({ ingestionStatus: 'COMPLETED' }), makeDocument({ ingestionStatus: 'FAILED' })],
        'SUBMITTED',
        makeEvaluationStatus({ status: 'COMPLETED' }),
      ),
    ).toBe('failures');
  });

  it('is "failures" when every document FAILED', () => {
    expect(
      zeroFindingsOutcome(
        [makeDocument({ ingestionStatus: 'FAILED' }), makeDocument({ ingestionStatus: 'FAILED' })],
        'SUBMITTED',
        makeEvaluationStatus({ status: 'COMPLETED' }),
      ),
    ).toBe('failures');
  });
});

describe('deriveApplicationStages', () => {
  it('DRAFT application: Submitted active, everything else pending', () => {
    const steps = deriveApplicationStages([], 'DRAFT', makeEvaluationStatus());
    expect(statusOf(steps, 'submitted')).toBe('active');
    expect(statusOf(steps, 'findings')).toBe('pending');
    expect(statusOf(steps, 'policy')).toBe('pending');
  });

  it('submitted with no findings yet: Submitted complete, Findings/Policy pending, Evaluation active', () => {
    const steps = deriveApplicationStages([], 'SUBMITTED', makeEvaluationStatus({ status: 'RUNNING' }));
    expect(statusOf(steps, 'submitted')).toBe('complete');
    expect(statusOf(steps, 'evaluation')).toBe('active');
    expect(statusOf(steps, 'findings')).toBe('active');
    expect(statusOf(steps, 'policy')).toBe('pending');
  });

  it('findings exist but not all policy-evaluated: Policy active', () => {
    const steps = deriveApplicationStages(
      [makeFinding({ policyVersion: null })],
      'SUBMITTED',
      makeEvaluationStatus({ status: 'RUNNING' }),
    );
    expect(statusOf(steps, 'findings')).toBe('complete');
    expect(statusOf(steps, 'policy')).toBe('active');
  });

  it('every finding policy-evaluated: Policy complete', () => {
    const steps = deriveApplicationStages(
      [makeFinding({ policyVersion: 'v1' })],
      'SUBMITTED',
      makeEvaluationStatus({ status: 'COMPLETED' }),
    );
    expect(statusOf(steps, 'evaluation')).toBe('complete');
    expect(statusOf(steps, 'policy')).toBe('complete');
  });

  it('a FAILED evaluation run renders the Evaluation step as failed, with the real error message', () => {
    const steps = deriveApplicationStages(
      [],
      'SUBMITTED',
      makeEvaluationStatus({ status: 'FAILED', errorMessage: 'Gemini API returned HTTP 429' }),
    );
    expect(statusOf(steps, 'evaluation')).toBe('failed');
    const evaluationStep = steps.find((step) => step.id === 'evaluation');
    expect(evaluationStep?.detail).toBe('Gemini API returned HTTP 429');
  });

  it('handles an undefined evaluation status (query still loading) without throwing', () => {
    const steps = deriveApplicationStages([], 'SUBMITTED', undefined);
    expect(statusOf(steps, 'evaluation')).toBe('active');
  });
});
