import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '../../test/msw/server';
import { DocumentViewer } from './DocumentViewer';

const APPLICATION_ID = '11111111-1111-1111-a111-111111111111';

function makeDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: '22222222-2222-2222-a222-222222222222',
    applicationId: APPLICATION_ID,
    partyId: null,
    filename: 'bank-statement.pdf',
    documentType: 'BANK_STATEMENT',
    ingestionStatus: 'COMPLETED',
    contentHash: 'a'.repeat(64),
    uploadedAt: '2026-06-20T09:00:00Z',
    uploadedBy: '33333333-3333-3333-a333-333333333333',
    evidenceItemCount: 1,
    pageCount: 3,
    ingestionCompletedAt: '2026-06-20T09:05:00Z',
    ingestionError: null,
    ...overrides,
  };
}

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function mockDocuments(documents: ReturnType<typeof makeDocument>[]) {
  server.use(
    http.get(`/v1/applications/${APPLICATION_ID}/documents`, () => HttpResponse.json(documents)),
  );
}

describe('DocumentViewer', () => {
  it('shows an empty state when there are no documents', async () => {
    mockDocuments([]);
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);
    expect(await screen.findByText('No documents uploaded yet')).toBeInTheDocument();
  });

  it('shows the processing state for a document that is not yet complete', async () => {
    mockDocuments([makeDocument({ ingestionStatus: 'IN_PROGRESS' })]);
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);
    expect(await screen.findByText('Processing…')).toBeInTheDocument();
  });

  it('shows the ingestion error for a failed document', async () => {
    mockDocuments([
      makeDocument({ ingestionStatus: 'FAILED', ingestionError: 'Unsupported file format' }),
    ]);
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);
    expect(await screen.findByText('Processing failed')).toBeInTheDocument();
    expect(screen.getByText('Unsupported file format')).toBeInTheDocument();
  });

  it('renders a document switcher only when there are multiple documents', async () => {
    mockDocuments([
      makeDocument({
        id: 'aaaaaaaa-1111-4111-a111-111111111111',
        filename: 'doc-1.pdf',
        ingestionStatus: 'IN_PROGRESS',
      }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        filename: 'doc-2.pdf',
        ingestionStatus: 'IN_PROGRESS',
      }),
    ]);
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);
    expect(await screen.findByRole('button', { name: 'doc-1.pdf' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'doc-2.pdf' })).toBeInTheDocument();
  });

  it('switches the active document when its tab is clicked', async () => {
    mockDocuments([
      makeDocument({
        id: 'aaaaaaaa-1111-4111-a111-111111111111',
        filename: 'doc-1.pdf',
        ingestionStatus: 'FAILED',
        ingestionError: 'first',
      }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        filename: 'doc-2.pdf',
        ingestionStatus: 'FAILED',
        ingestionError: 'second',
      }),
    ]);
    const user = userEvent.setup();
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);

    expect(await screen.findByText('first')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'doc-2.pdf' }));
    expect(await screen.findByText('second')).toBeInTheDocument();
  });

  it('jumps to the target document and page when jumpTarget is set', async () => {
    mockDocuments([
      makeDocument({
        id: 'aaaaaaaa-1111-4111-a111-111111111111',
        filename: 'doc-1.pdf',
        ingestionStatus: 'IN_PROGRESS',
      }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        filename: 'doc-2.pdf',
        ingestionStatus: 'IN_PROGRESS',
      }),
    ]);
    renderWithClient(
      <DocumentViewer
        applicationId={APPLICATION_ID}
        jumpTarget={{
          documentId: 'bbbbbbbb-2222-4222-a222-222222222222',
          pageNumber: 3,
          boundingBox: null,
          label: 'Income',
        }}
      />,
    );

    const doc2Tab = await screen.findByRole('button', { name: 'doc-2.pdf' });
    expect(doc2Tab).toHaveAttribute('aria-current', 'true');
  });

  it('disables "Previous page" on the first page', async () => {
    mockDocuments([makeDocument()]);
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);
    expect(await screen.findByRole('button', { name: 'Previous page' })).toBeDisabled();
  });

  it('advances to the next page and back', async () => {
    mockDocuments([makeDocument()]);
    const user = userEvent.setup();
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);

    await screen.findByRole('button', { name: 'Previous page' });
    const pageInput = screen.getByRole('spinbutton');
    expect(pageInput).toHaveValue(1);

    await user.click(screen.getByRole('button', { name: 'Next page' }));
    expect(pageInput).toHaveValue(2);

    await user.click(screen.getByRole('button', { name: 'Previous page' }));
    expect(pageInput).toHaveValue(1);
  });

  it('disables "Next page" at the last known page', async () => {
    mockDocuments([makeDocument({ pageCount: 1 })]);
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);
    expect(await screen.findByRole('button', { name: 'Next page' })).toBeDisabled();
  });

  it('zooms in and out', async () => {
    mockDocuments([makeDocument()]);
    const user = userEvent.setup();
    renderWithClient(<DocumentViewer applicationId={APPLICATION_ID} />);

    await screen.findByText('120%');
    await user.click(screen.getByRole('button', { name: 'Zoom in' }));
    expect(await screen.findByText('140%')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Zoom out' }));
    expect(await screen.findByText('120%')).toBeInTheDocument();
  });
});
