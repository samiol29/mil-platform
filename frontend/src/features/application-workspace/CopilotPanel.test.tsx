import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { server } from '../../test/msw/server';
import { CopilotPanel } from './CopilotPanel';

const APPLICATION_ID = '11111111-1111-1111-a111-111111111111';
const SESSION_ID = '22222222-2222-2222-a222-222222222222';

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <CopilotPanel applicationId={APPLICATION_ID} onEvidenceChipActivate={vi.fn()} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  server.resetHandlers();
});

describe('CopilotPanel citation labels (final design excellence sprint)', () => {
  it('shows a human-readable kind label and a truncated ref, never a raw 36-character UUID', async () => {
    server.use(
      http.get(`/v1/applications/${APPLICATION_ID}/copilot`, () =>
        HttpResponse.json({
          id: SESSION_ID,
          applicationId: APPLICATION_ID,
          tenantId: '33333333-3333-3333-a333-333333333333',
          createdByUserId: '44444444-4444-4444-a444-444444444444',
          correlationId: '77777777-7777-7777-a777-777777777777',
          createdAt: '2026-07-14T00:00:00Z',
        }),
      ),
      http.get(`/v1/copilot/sessions/${SESSION_ID}/history`, () =>
        HttpResponse.json({
          sessionId: SESSION_ID,
          items: [
            {
              queryId: '55555555-5555-5555-a555-555555555555',
              question: 'Summarise application',
              askedByUserId: '44444444-4444-4444-a444-444444444444',
              askedAt: '2026-07-14T00:00:01Z',
              response: {
                id: '66666666-6666-6666-a666-666666666666',
                queryId: '55555555-5555-5555-a555-555555555555',
                sessionId: SESSION_ID,
                answer: 'The application status is SUBMITTED [64cd5379-5104-4758-b443-5f8ea8ab2db6].',
                promptVersion: 'summarize-application-v1',
                modelVersion: 'gemini:gemini-2.5-flash',
                citations: [
                  { kind: 'APPLICATION', ref: '64cd5379-5104-4758-b443-5f8ea8ab2db6', locator: null },
                ],
                createdAt: '2026-07-14T00:00:02Z',
              },
            },
          ],
        }),
      ),
    );

    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole('button', { name: 'Ask Copilot about this application' }));

    // The chip shows a human-readable kind + truncated ref — the full,
    // un-truncated UUID legitimately still appears once, inline in the
    // model's own answer prose (that text is not this component's to
    // rewrite); only the *chip itself* must never render it in full.
    const chip = await screen.findByText('Application: 64cd5379…');
    expect(chip).toBeInTheDocument();
    expect(chip.textContent).not.toContain('64cd5379-5104-4758-b443-5f8ea8ab2db6');
  });
});
