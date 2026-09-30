import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { EvidenceItem } from '@entities/evidence/queries';

import { EvidenceCard } from './EvidenceCard';

function makeItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    documentId: '33333333-3333-4333-a333-333333333333',
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

describe('EvidenceCard', () => {
  it('shows the evidence type, value, confidence, and provenance', () => {
    render(
      <EvidenceCard
        item={makeItem()}
        relatedFindingsCount={0}
        onViewInDocument={() => undefined}
      />,
    );

    expect(screen.getByText('gross monthly income')).toBeInTheDocument();
    expect(screen.getByText('6200.00')).toBeInTheDocument();
    expect(screen.getByRole('meter')).toBeInTheDocument();
    expect(
      screen.getByText(/Extracted via LLM_EXTRACTION_V1 · model 2026.06.1/),
    ).toBeInTheDocument();
  });

  it('shows the page number honestly, never a fabricated fallback, when it is null', () => {
    render(
      <EvidenceCard
        item={makeItem({ pageNumber: null })}
        relatedFindingsCount={0}
        onViewInDocument={() => undefined}
      />,
    );
    expect(screen.getByText('Page —')).toBeInTheDocument();
  });

  it('calls onViewInDocument when "View in document" is clicked', async () => {
    const onViewInDocument = vi.fn();
    const user = userEvent.setup();
    render(
      <EvidenceCard
        item={makeItem()}
        relatedFindingsCount={0}
        onViewInDocument={onViewInDocument}
      />,
    );

    await user.click(screen.getByText('View in document'));
    expect(onViewInDocument).toHaveBeenCalled();
  });

  it('only shows a "used in finding(s)" link when relatedFindingsCount is greater than zero', () => {
    const { rerender } = render(
      <EvidenceCard
        item={makeItem()}
        relatedFindingsCount={0}
        onViewInDocument={() => undefined}
      />,
    );
    expect(screen.queryByText(/Used in/)).not.toBeInTheDocument();

    rerender(
      <EvidenceCard
        item={makeItem()}
        relatedFindingsCount={2}
        onViewInDocument={() => undefined}
        onViewFindings={() => undefined}
      />,
    );
    expect(screen.getByText('Used in 2 findings →')).toBeInTheDocument();
  });

  it('shows a supersedes line only when a resolved prior item is provided', () => {
    const { rerender } = render(
      <EvidenceCard
        item={makeItem()}
        relatedFindingsCount={0}
        onViewInDocument={() => undefined}
      />,
    );
    expect(screen.queryByText(/Supersedes/)).not.toBeInTheDocument();

    rerender(
      <EvidenceCard
        item={makeItem({ supersedesId: '44444444-4444-4444-a444-444444444444' })}
        supersededItem={makeItem({
          id: '44444444-4444-4444-a444-444444444444',
          extractedAt: '2026-06-01T09:00:00Z',
        })}
        relatedFindingsCount={0}
        onViewInDocument={() => undefined}
      />,
    );
    expect(screen.getByText(/Supersedes an earlier extraction from/)).toBeInTheDocument();
  });

  it('highlights matching text within the field name and value when searchQuery is set', () => {
    const { container } = render(
      <EvidenceCard
        item={makeItem()}
        relatedFindingsCount={0}
        onViewInDocument={() => undefined}
        searchQuery="income"
      />,
    );

    const marks = container.querySelectorAll('mark');
    expect(marks.length).toBeGreaterThan(0);
    expect(marks[0]).toHaveTextContent('income');
    expect(container).toHaveTextContent('gross monthly income');
  });

  it('renders no highlight marks when searchQuery is empty or unset', () => {
    const { container } = render(
      <EvidenceCard
        item={makeItem()}
        relatedFindingsCount={0}
        onViewInDocument={() => undefined}
      />,
    );
    expect(container.querySelectorAll('mark')).toHaveLength(0);
  });
});
