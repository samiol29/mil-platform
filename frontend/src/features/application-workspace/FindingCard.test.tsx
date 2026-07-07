import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { EvidenceItem } from '@entities/evidence/queries';
import type { Finding } from '@entities/finding/queries';

import { FindingCard } from './FindingCard';
import type { ReviewHistoryEntry } from './findingReviewHistory';

const EVIDENCE_ID = '33333333-3333-3333-a333-333333333333';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: '44444444-4444-4444-a444-444444444444',
    applicationId: '11111111-1111-1111-a111-111111111111',
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
    escalatedToRole: null,
    escalatedToUserId: null,
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

function makeEvidenceItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: EVIDENCE_ID,
    applicationId: '11111111-1111-1111-a111-111111111111',
    documentId: '22222222-2222-2222-a222-222222222222',
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

  it('places the reviewer decision (recommended action + actions) before the AI-details/review-history disclosures — reviewer action first, implementation details last', () => {
    const { container } = render(
      <FindingCard
        finding={makeFinding()}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
        actions={<button type="button">Verify</button>}
      />,
    );

    const text = container.textContent;
    const decisionIndex = text.indexOf('Your decision');
    const recommendedActionIndex = text.indexOf('Recommended reviewer action');
    const verifyButtonIndex = text.indexOf('Verify');
    const aiDetailsIndex = text.indexOf('AI details');
    const reviewHistoryIndex = text.indexOf('Review history');

    expect(decisionIndex).toBeGreaterThan(-1);
    expect(recommendedActionIndex).toBeGreaterThan(decisionIndex);
    expect(verifyButtonIndex).toBeGreaterThan(recommendedActionIndex);
    expect(aiDetailsIndex).toBeGreaterThan(verifyButtonIndex);
    expect(reviewHistoryIndex).toBeGreaterThan(aiDetailsIndex);
  });

  it('shows the target role for an escalated finding', () => {
    render(
      <FindingCard
        finding={makeFinding({ state: 'escalated', escalatedToRole: 'COMPLIANCE_OFFICER' })}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
      />,
    );
    expect(screen.getByText(/Escalated/)).toBeInTheDocument();
    expect(screen.getByText(/COMPLIANCE_OFFICER/)).toBeInTheDocument();
  });

  it('shows the real policy version when present, honestly labels a null one', () => {
    const { rerender } = render(
      <FindingCard
        finding={makeFinding({ policyVersion: 'policy-pack-2026.2' })}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
      />,
    );
    expect(screen.getByText('Evaluated under policy policy-pack-2026.2')).toBeInTheDocument();

    rerender(
      <FindingCard
        finding={makeFinding({ policyVersion: null })}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
      />,
    );
    expect(screen.getByText('Not yet evaluated against policy')).toBeInTheDocument();
  });

  it('shows an Impact line captioned as derived, not a backend severity', () => {
    render(
      <FindingCard
        finding={makeFinding({ confidence: 'high' })}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
      />,
    );
    expect(screen.getByText('High confidence, supported by 1 evidence item.')).toBeInTheDocument();
    expect(
      screen.getByText('Derived from confidence and evidence count — not a backend-assigned severity.'),
    ).toBeInTheDocument();
  });

  it('keeps AI details collapsed by default, showing the real model/prompt/extraction versions when opened', async () => {
    const user = userEvent.setup();
    render(
      <FindingCard
        finding={makeFinding()}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
      />,
    );
    expect(screen.queryByText('gpt-underwriting-2026.06')).not.toBeInTheDocument();

    await user.click(screen.getByText('AI details'));
    expect(screen.getByText('gpt-underwriting-2026.06')).toBeInTheDocument();
    expect(screen.getByText('finding-v3')).toBeInTheDocument();
    expect(screen.getByText('2026.06.1')).toBeInTheDocument();
  });

  it('shows the real reviewer rationale in Review history once expanded, and an honest empty state otherwise', async () => {
    const history: ReviewHistoryEntry[] = [
      {
        id: 'a',
        occurredAt: '2026-06-22T09:00:00Z',
        actorType: 'USER',
        kind: 'overridden',
        reason: 'Borrower confirmed a raise not yet reflected in the pay stub.',
        previousValue: '6200.00',
        newValue: '6500.00',
        targetRole: null,
      },
    ];
    const user = userEvent.setup();
    const { rerender } = render(
      <FindingCard
        finding={makeFinding()}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
        reviewHistory={history}
      />,
    );
    await user.click(screen.getByText('Review history'));
    expect(
      screen.getByText(/Borrower confirmed a raise not yet reflected in the pay stub\./),
    ).toBeInTheDocument();

    rerender(
      <FindingCard
        finding={makeFinding()}
        evidenceItems={[makeEvidenceItem()]}
        onEvidenceChipActivate={vi.fn()}
        reviewHistory={[]}
      />,
    );
    expect(screen.getByText('No review decisions recorded yet.')).toBeInTheDocument();
  });
});
