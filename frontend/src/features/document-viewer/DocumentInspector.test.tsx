import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import type { Document } from '@entities/document/queries';

import {
  FIXTURE_APPLICATION_ID,
  FIXTURE_DOCUMENT_ID,
  FIXTURE_FINDING_ID,
} from '../../test/msw/handlers';
import { server } from '../../test/msw/server';
import { DocumentInspector } from './DocumentInspector';

const OTHER_DOCUMENT_ID = '99999999-9999-4999-a999-999999999999';

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: FIXTURE_DOCUMENT_ID,
    applicationId: FIXTURE_APPLICATION_ID,
    partyId: null,
    filename: 'bank-statement.pdf',
    documentType: 'BANK_STATEMENT',
    ingestionStatus: 'COMPLETED',
    contentHash: 'a'.repeat(64),
    uploadedAt: '2026-06-20T09:00:00Z',
    uploadedBy: '33333333-3333-4333-a333-333333333333',
    evidenceItemCount: 1,
    pageCount: 3,
    ingestionCompletedAt: '2026-06-20T09:05:00Z',
    ingestionError: null,
    retryCount: 0,
    ...overrides,
  };
}

function mockParties() {
  server.use(
    http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/parties`, () => HttpResponse.json([])),
  );
}

function renderInspector(
  document: Document,
  overrides: Partial<React.ComponentProps<typeof DocumentInspector>> = {},
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <DocumentInspector
        applicationId={FIXTURE_APPLICATION_ID}
        document={document}
        onEvidenceChipActivate={vi.fn()}
        onViewFinding={vi.fn()}
        {...overrides}
      />
    </QueryClientProvider>,
  );
}

describe('DocumentInspector', () => {
  it('shows real document metadata with no new backend calls', async () => {
    mockParties();
    renderInspector(makeDocument());

    expect(await screen.findByText('BANK_STATEMENT')).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Unassigned')).toBeInTheDocument();
  });

  it("shows only this document's evidence, not the whole application's", async () => {
    mockParties();
    const user = userEvent.setup();
    renderInspector(makeDocument());

    await user.click(await screen.findByRole('tab', { name: /Evidence/ }));
    expect(await screen.findByText('gross monthly income')).toBeInTheDocument();
  });

  it('shows an honest empty state on the Evidence tab for a document with no evidence', async () => {
    mockParties();
    const user = userEvent.setup();
    renderInspector(makeDocument({ id: OTHER_DOCUMENT_ID }));

    await user.click(await screen.findByRole('tab', { name: /Evidence/ }));
    expect(
      await screen.findByText('No evidence extracted from this document yet'),
    ).toBeInTheDocument();
  });

  it('shows only findings whose evidence belongs to this document', async () => {
    mockParties();
    const user = userEvent.setup();
    renderInspector(makeDocument());

    await user.click(await screen.findByRole('tab', { name: /Findings/ }));
    expect(await screen.findByText(/Reported monthly income does not match/)).toBeInTheDocument();
  });

  it('clicking "View finding" calls onViewFinding with the real finding id', async () => {
    mockParties();
    const onViewFinding = vi.fn();
    const user = userEvent.setup();
    renderInspector(makeDocument(), { onViewFinding });

    await user.click(await screen.findByRole('tab', { name: /Findings/ }));
    await user.click(await screen.findByText('View finding →'));
    expect(onViewFinding).toHaveBeenCalledWith(FIXTURE_FINDING_ID);
  });

  it('shows the permanent honest policy-limitation disclosure on the Policy tab', async () => {
    mockParties();
    const user = userEvent.setup();
    renderInspector(makeDocument());

    await user.click(await screen.findByRole('tab', { name: /Policy/ }));
    expect(
      await screen.findByText(/cannot show checks that passed silently, individual rule names/),
    ).toBeInTheDocument();
  });

  it('clicking an evidence chip calls onEvidenceChipActivate with the real evidence location', async () => {
    mockParties();
    const onEvidenceChipActivate = vi.fn();
    const user = userEvent.setup();
    renderInspector(makeDocument(), { onEvidenceChipActivate });

    await user.click(await screen.findByRole('tab', { name: /Evidence/ }));
    await user.click(await screen.findByText('View in document'));
    expect(onEvidenceChipActivate).toHaveBeenCalledWith(
      expect.objectContaining({ documentId: FIXTURE_DOCUMENT_ID, label: 'gross_monthly_income' }),
    );
  });

  it('shows an honest empty state on the Timeline tab when no real audit events exist for this document', async () => {
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/audit`, () => HttpResponse.json([])),
    );
    mockParties();
    const user = userEvent.setup();
    renderInspector(makeDocument());

    await user.click(await screen.findByRole('tab', { name: /Timeline/ }));
    expect(await screen.findByText('No timeline events for this document yet')).toBeInTheDocument();
  });
});
