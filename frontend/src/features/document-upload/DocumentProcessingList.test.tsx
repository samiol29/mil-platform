import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../../test/msw/server';
import { DocumentProcessingList } from './DocumentProcessingList';

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
    evidenceItemCount: 0,
    pageCount: 3,
    ingestionCompletedAt: '2026-06-20T09:05:00Z',
    ingestionError: null,
    ...overrides,
  };
}

function renderList(props: Partial<React.ComponentProps<typeof DocumentProcessingList>> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onSelectDocument = vi.fn();
  const onViewEvidence = vi.fn();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <DocumentProcessingList
        applicationId={APPLICATION_ID}
        selectedDocumentId={null}
        onSelectDocument={onSelectDocument}
        onViewEvidence={onViewEvidence}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { ...utils, onSelectDocument, onViewEvidence };
}

function mockDocuments(documents: ReturnType<typeof makeDocument>[]) {
  server.use(
    http.get(`/v1/applications/${APPLICATION_ID}/documents`, () => HttpResponse.json(documents)),
    http.get(`/v1/applications/${APPLICATION_ID}/parties`, () => HttpResponse.json([])),
  );
}

describe('DocumentProcessingList', () => {
  it('shows the package summary with real counts', async () => {
    mockDocuments([
      makeDocument({ id: 'aaaaaaaa-1111-4111-a111-111111111111', ingestionStatus: 'COMPLETED' }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        ingestionStatus: 'FAILED',
        ingestionError: 'boom',
      }),
    ]);
    renderList();
    expect(await screen.findByText(/2 documents/)).toBeInTheDocument();
    expect(screen.getByText(/1 ready/)).toBeInTheDocument();
    expect(screen.getByText(/1 failed/)).toBeInTheDocument();
  });

  it('flags documents sharing a contentHash as possible duplicates', async () => {
    mockDocuments([
      makeDocument({ id: 'aaaaaaaa-1111-4111-a111-111111111111', contentHash: 'x'.repeat(64) }),
      makeDocument({ id: 'bbbbbbbb-2222-4222-a222-222222222222', contentHash: 'x'.repeat(64) }),
    ]);
    renderList();
    expect(await screen.findAllByText('Possible duplicate')).toHaveLength(2);
    expect(screen.getByText(/2 possible duplicates/)).toBeInTheDocument();
  });

  it('calls onSelectDocument when a row is clicked', async () => {
    mockDocuments([
      makeDocument({ id: 'aaaaaaaa-1111-4111-a111-111111111111', filename: 'paystub.pdf' }),
    ]);
    const { onSelectDocument } = renderList();
    const user = userEvent.setup();

    await user.click(await screen.findByText('paystub.pdf'));
    expect(onSelectDocument).toHaveBeenCalledWith('aaaaaaaa-1111-4111-a111-111111111111');
  });

  it('shows a "View evidence" link only when evidenceItemCount is greater than zero', async () => {
    mockDocuments([
      makeDocument({
        id: 'aaaaaaaa-1111-4111-a111-111111111111',
        filename: 'has-evidence.pdf',
        evidenceItemCount: 2,
      }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        filename: 'no-evidence.pdf',
        evidenceItemCount: 0,
      }),
    ]);
    renderList();
    expect(await screen.findByText('View 2 evidence items →')).toBeInTheDocument();
    expect(screen.queryByText(/no-evidence.*evidence/)).not.toBeInTheDocument();
  });

  it('calls onViewEvidence with the document id when the evidence link is clicked', async () => {
    mockDocuments([
      makeDocument({ id: 'aaaaaaaa-1111-4111-a111-111111111111', evidenceItemCount: 1 }),
    ]);
    const { onViewEvidence } = renderList();
    const user = userEvent.setup();

    await user.click(await screen.findByText('View 1 evidence item →'));
    expect(onViewEvidence).toHaveBeenCalledWith('aaaaaaaa-1111-4111-a111-111111111111');
  });

  it('never implies the whole package is broken when one document FAILED — the row shows its own real error (in Details), others are unaffected', async () => {
    mockDocuments([
      makeDocument({
        id: 'aaaaaaaa-1111-4111-a111-111111111111',
        filename: 'ok.pdf',
        ingestionStatus: 'COMPLETED',
      }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        filename: 'broken.pdf',
        ingestionStatus: 'FAILED',
        ingestionError: 'Gemini API returned HTTP 400: The document has no pages.',
      }),
    ]);
    renderList();
    expect(await screen.findByText('ok.pdf')).toBeInTheDocument();
    const user = userEvent.setup();
    const detailsButtons = await screen.findAllByText('Details');
    await user.click(detailsButtons[1]);
    expect(screen.getByText(/Gemini API returned HTTP 400/)).toBeInTheDocument();
  });

  it('shows a Retry action only for FAILED documents', async () => {
    mockDocuments([
      makeDocument({ id: 'aaaaaaaa-1111-4111-a111-111111111111', ingestionStatus: 'COMPLETED' }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        ingestionStatus: 'FAILED',
        ingestionError: 'boom',
      }),
    ]);
    renderList();
    await screen.findByText(/2 documents/);
    expect(screen.getAllByText('Retry', { exact: false })).toHaveLength(1);
  });

  it('calls the retry endpoint for a single FAILED document', async () => {
    mockDocuments([
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        ingestionStatus: 'FAILED',
        ingestionError: 'boom',
      }),
    ]);
    let retried = false;
    server.use(
      http.post(
        `/v1/applications/${APPLICATION_ID}/documents/bbbbbbbb-2222-4222-a222-222222222222/retry`,
        () => {
          retried = true;
          return HttpResponse.json(
            makeDocument({
              id: 'bbbbbbbb-2222-4222-a222-222222222222',
              ingestionStatus: 'PENDING',
              ingestionError: null,
              retryCount: 1,
            }),
          );
        },
      ),
    );
    renderList();
    const user = userEvent.setup();
    await user.click(await screen.findByText('Retry'));
    await waitFor(() => {
      expect(retried).toBe(true);
    });
  });

  it('"Retry all failed" retries every FAILED document, not just one', async () => {
    mockDocuments([
      makeDocument({
        id: 'aaaaaaaa-1111-4111-a111-111111111111',
        ingestionStatus: 'FAILED',
        ingestionError: 'boom 1',
      }),
      makeDocument({
        id: 'bbbbbbbb-2222-4222-a222-222222222222',
        ingestionStatus: 'FAILED',
        ingestionError: 'boom 2',
      }),
    ]);
    const retriedIds = new Set<string>();
    server.use(
      http.post(
        `/v1/applications/${APPLICATION_ID}/documents/:documentId/retry`,
        ({ params }) => {
          retriedIds.add(params.documentId as string);
          return HttpResponse.json(
            makeDocument({ id: params.documentId, ingestionStatus: 'PENDING' }),
          );
        },
      ),
    );
    renderList();
    const user = userEvent.setup();
    await user.click(await screen.findByText(/Retry all failed \(2\)/));
    await waitFor(() => {
      expect(retriedIds).toEqual(
        new Set(['aaaaaaaa-1111-4111-a111-111111111111', 'bbbbbbbb-2222-4222-a222-222222222222']),
      );
    });
  });
});
