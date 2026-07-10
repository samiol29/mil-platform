import { describe, expect, it } from 'vitest';

import type { Document } from '@entities/document/queries';

import { deriveDocumentStages } from './deriveDocumentStages';

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    partyId: null,
    filename: 'bank-statement.pdf',
    documentType: 'BANK_STATEMENT',
    ingestionStatus: 'PENDING',
    contentHash: 'a'.repeat(64),
    uploadedAt: '2026-01-01T00:00:00Z',
    uploadedBy: '33333333-3333-4333-a333-333333333333',
    evidenceItemCount: 0,
    pageCount: null,
    ingestionCompletedAt: null,
    ingestionError: null,
    ...overrides,
  };
}

function statusOf(steps: ReturnType<typeof deriveDocumentStages>, id: string) {
  return steps.find((step) => step.id === id)?.status;
}

describe('deriveDocumentStages', () => {
  it('Upload is always complete once a Document row exists', () => {
    const steps = deriveDocumentStages(makeDocument());
    expect(statusOf(steps, 'upload')).toBe('complete');
  });

  it('PENDING: Processing pending, Evidence pending, Ready pending', () => {
    const steps = deriveDocumentStages(makeDocument({ ingestionStatus: 'PENDING' }));
    expect(statusOf(steps, 'processing')).toBe('pending');
    expect(statusOf(steps, 'evidence')).toBe('pending');
    expect(statusOf(steps, 'ready')).toBe('pending');
  });

  it('IN_PROGRESS: Processing active, Evidence pending, Ready pending', () => {
    const steps = deriveDocumentStages(makeDocument({ ingestionStatus: 'IN_PROGRESS' }));
    expect(statusOf(steps, 'processing')).toBe('active');
    expect(statusOf(steps, 'evidence')).toBe('pending');
    expect(statusOf(steps, 'ready')).toBe('pending');
  });

  it('COMPLETED with evidence: Processing/Evidence/Ready all complete', () => {
    const steps = deriveDocumentStages(
      makeDocument({ ingestionStatus: 'COMPLETED', evidenceItemCount: 3 }),
    );
    expect(statusOf(steps, 'processing')).toBe('complete');
    expect(statusOf(steps, 'evidence')).toBe('complete');
    expect(statusOf(steps, 'ready')).toBe('complete');
  });

  it('COMPLETED with zero evidence items: Ready complete but Evidence stays pending (real count, not assumed)', () => {
    const steps = deriveDocumentStages(
      makeDocument({ ingestionStatus: 'COMPLETED', evidenceItemCount: 0 }),
    );
    expect(statusOf(steps, 'evidence')).toBe('pending');
    expect(statusOf(steps, 'ready')).toBe('complete');
  });

  it('FAILED: Processing failed with the real ingestionError as detail, Evidence/Ready skipped', () => {
    const steps = deriveDocumentStages(
      makeDocument({
        ingestionStatus: 'FAILED',
        ingestionError: 'Gemini API returned HTTP 400: The document has no pages.',
      }),
    );
    const processing = steps.find((step) => step.id === 'processing');
    expect(processing?.status).toBe('failed');
    expect(processing?.detail).toBe('Gemini API returned HTTP 400: The document has no pages.');
    expect(statusOf(steps, 'evidence')).toBe('skipped');
    expect(statusOf(steps, 'ready')).toBe('skipped');
  });
});
