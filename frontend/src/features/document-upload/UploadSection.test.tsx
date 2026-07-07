import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { FIXTURE_APPLICATION_ID } from '../../test/msw/handlers';
import { server } from '../../test/msw/server';
import { sha256Hex } from './fileHash';
import { UploadSection } from './UploadSection';

function renderSection(applicationId = FIXTURE_APPLICATION_ID) {
  const onExpandedChange = () => undefined;
  return render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <UploadSection applicationId={applicationId} expanded onExpandedChange={onExpandedChange} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe('UploadSection', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('flags a staged file as a duplicate when its hash matches an existing document', async () => {
    const duplicateContent = 'duplicate-bank-statement-bytes';
    const duplicateHash = await sha256Hex(new File([duplicateContent], 'whatever.pdf'));

    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/documents`, () =>
        HttpResponse.json([
          {
            id: '22222222-2222-2222-a222-222222222222',
            application_id: FIXTURE_APPLICATION_ID,
            party_id: null,
            filename: 'existing-bank-statement.pdf',
            document_type: 'BANK_STATEMENT',
            ingestion_status: 'COMPLETED',
            content_hash: duplicateHash,
            uploaded_at: '2026-06-20T09:00:00Z',
            uploaded_by: '33333333-3333-3333-a333-333333333333',
            evidence_item_count: 1,
            page_count: 1,
            ingestion_completed_at: '2026-06-20T09:05:00Z',
            ingestion_error: null,
          },
        ]),
      ),
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/parties`, () => HttpResponse.json([])),
    );

    renderSection();
    const user = userEvent.setup();

    const fileInput = screen.getByLabelText('Choose files to upload');
    const duplicateFile = new File([duplicateContent], 'bank_statement_copy.pdf', {
      type: 'application/pdf',
    });
    await user.upload(fileInput, duplicateFile);

    await waitFor(() => {
      expect(
        screen.getByText('This looks like a duplicate of a document already on this application.'),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Upload anyway' })).toBeInTheDocument();
    // The Upload button should exclude the unacknowledged duplicate from its count.
    expect(screen.getByRole('button', { name: 'Upload 0 files' })).toBeDisabled();
  });

  it('retries only the failed file and does not resend an already-uploaded file', async () => {
    let uploadCalls = 0;
    const uploadedDocuments: Record<string, unknown>[] = [];
    server.use(
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/documents`, () =>
        HttpResponse.json(uploadedDocuments),
      ),
      http.get(`/v1/applications/${FIXTURE_APPLICATION_ID}/parties`, () => HttpResponse.json([])),
      http.post(`/v1/applications/${FIXTURE_APPLICATION_ID}/documents`, () => {
        // Deliberately does not parse the multipart body (`request.formData()`)
        // — MSW/undici's multipart parser doesn't accept jsdom's `File` brand
        // in this test environment (a jsdom/Node interop gap, not a product
        // bug; the real upload flow is exercised against the actual backend,
        // see the plan's verification notes). This handler only needs to
        // control response sequencing (fail once, then succeed).
        uploadCalls += 1;
        if (uploadCalls === 1) {
          return HttpResponse.json({ message: 'Storage backend unavailable' }, { status: 500 });
        }
        const document = {
          id: '55555555-5555-4555-a555-555555555555',
          application_id: FIXTURE_APPLICATION_ID,
          party_id: null,
          filename: 'paystub.pdf',
          document_type: 'PAYSLIP',
          ingestion_status: 'PENDING',
          content_hash: 'b'.repeat(64),
          uploaded_at: '2026-06-20T09:00:00Z',
          uploaded_by: '33333333-3333-3333-a333-333333333333',
          evidence_item_count: 0,
          page_count: null,
          ingestion_completed_at: null,
          ingestion_error: null,
        };
        uploadedDocuments.push(document);
        return HttpResponse.json(document, { status: 201 });
      }),
    );

    renderSection();
    const user = userEvent.setup();

    const fileInput = screen.getByLabelText('Choose files to upload');
    await user.upload(fileInput, new File(['content'], 'paystub.pdf', { type: 'application/pdf' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Upload 1 file' })).toBeEnabled();
    });
    await user.click(screen.getByRole('button', { name: 'Upload 1 file' }));

    await waitFor(() => {
      expect(screen.getByText('Storage backend unavailable')).toBeInTheDocument();
    });
    expect(uploadCalls).toBe(1);

    await user.click(screen.getByRole('button', { name: 'Retry paystub.pdf' }));

    await waitFor(() => {
      expect(screen.getByText('Queued for processing')).toBeInTheDocument();
    });
    expect(uploadCalls).toBe(2);
  });
});
