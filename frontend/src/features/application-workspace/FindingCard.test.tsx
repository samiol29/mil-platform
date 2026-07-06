import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { EvidenceItem } from '@entities/evidence/queries';
import type { Finding } from '@entities/finding/queries';

import { FindingCard } from './FindingCard';

const EVIDENCE_ID = '33333333-3333-3333-3333-333333333333';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: '44444444-4444-4444-4444-444444444444',
    applicationId: '11111111-1111-1111-1111-111111111111',
    what: 'Reported income does not match the pay stub on file.',
    why: 'The application states $6,500/month; the extracted value is $6,200/month.',
    evidenceRefs: [EVIDENCE_ID],
    confidence: 'high',
    recommendedAction: 'Confirm current income with the borrower.',
    state: 'unreviewed',
    modelVersion: 'gpt-underwriting-2026.06',
    promptVersion: 'finding-v3',
    extractionVersion: '2026.06.1',
    policyVersion: 'policy-pack-2026.2',
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

function makeEvidenceItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: EVIDENCE_ID,
    applicationId: '11111111-1111-1111-1111-111111111111',
    documentId: '22222222-2222-2222-2222-222222222222',
    partyId: null,
    evidenceType: 'gross_monthly_income',
    valueText: '6200.00',
    valueNumeric: null,
    currency: null,
    pageNumber: 2,
    fieldLocation: null,
    confidence: 'high',
    extractionMethod: 'mock-keyword-matcher',
    extractionModelVersion: 'mock-extraction-1.0.0',
    extractedAt: '2026-06-21T10:15:00Z',
    supersedesId: null,
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

describe('FindingCard', () => {
  it('renders all five explainability elements', () => {
    const finding = makeFinding();
    render(
      <FindingCard
        finding={finding}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
      />,
    );

    // what
    expect(screen.getByText(finding.what)).toBeInTheDocument();
    // why
    expect(screen.getByText(finding.why)).toBeInTheDocument();
    // evidence (rendered as an EvidenceChip)
    expect(screen.getByRole('button', { name: /gross_monthly_income/i })).toBeInTheDocument();
    // confidence
    expect(screen.getByRole('meter')).toHaveAccessibleName('Extraction confidence');
    // recommended action
    expect(screen.getByText(finding.recommendedAction)).toBeInTheDocument();
  });

  it('never compiles with a missing explainability field', () => {
    // @ts-expect-error -- `why` is required; this must fail to type-check,
    // proving FindingCard is type-gated on all five explainability fields.
    const incomplete: Finding = makeFinding({ why: undefined });
    expect(incomplete).toBeDefined();
  });

  it("labels an evidence chip 'Evidence' when the referenced item is not loaded", () => {
    render(
      <FindingCard finding={makeFinding()} evidenceItems={[]} onEvidenceChipActivate={vi.fn()} />,
    );
    const chip = screen.getByRole('button', { name: 'Evidence' });
    expect(chip).toBeDisabled();
  });

  it('renders the current review state', () => {
    render(
      <FindingCard
        finding={makeFinding({ state: 'verified' })}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
      />,
    );
    expect(screen.getByText('Verified')).toBeInTheDocument();
  });

  it('renders supplied actions', () => {
    render(
      <FindingCard
        finding={makeFinding()}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
        actions={<button type="button">Verify</button>}
      />,
    );
    expect(screen.getByRole('button', { name: 'Verify' })).toBeInTheDocument();
  });
});
