import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../../routeTree.gen';
import { server } from '../../test/msw/server';

function renderEscalationQueue() {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/escalation-queue'] }),
    context: { queryClient },
  });
  return render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

function makeFinding(overrides: Record<string, unknown> = {}) {
  return {
    id: '11111111-1111-4111-a111-111111111111',
    applicationId: '22222222-2222-4222-a222-222222222222',
    what: 'Income mismatch',
    why: 'Reported income differs from the pay stub.',
    evidenceRefs: ['33333333-3333-4333-a333-333333333333'],
    confidence: 'high',
    recommendedAction: 'Confirm with borrower.',
    state: 'escalated',
    modelVersion: 'v1',
    promptVersion: 'v1',
    extractionVersion: 'v1',
    policyVersion: null,
    escalatedToRole: 'COMPLIANCE_OFFICER',
    escalatedToUserId: null,
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

describe('EscalationQueuePage (final product polish sprint, A5)', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('shows an honest empty state when nothing is escalated to the caller', async () => {
    server.use(http.get('/v1/findings/escalated', () => HttpResponse.json([])));
    renderEscalationQueue();

    expect(
      await screen.findByText('Nothing escalated to you right now'),
    ).toBeInTheDocument();
  });

  it('renders a row for each escalated finding, with the real "what"/"why" text', async () => {
    server.use(
      http.get('/v1/findings/escalated', () => HttpResponse.json([makeFinding()])),
      http.get('/v1/applications/:id', ({ params }) =>
        HttpResponse.json({
          id: params.id,
          losReference: 'LOS-9001',
          loanNumber: '4009123456',
          status: 'IN_REVIEW',
          activePolicyPackId: null,
          partyCount: 1,
          createdAt: '2026-06-20T09:00:00Z',
          updatedAt: null,
        }),
      ),
    );
    renderEscalationQueue();

    expect(await screen.findByText('Income mismatch')).toBeInTheDocument();
    expect(
      screen.getByText('Reported income differs from the pay stub.'),
    ).toBeInTheDocument();
    expect(await screen.findByText('4009123456')).toBeInTheDocument();
  });

  it('labels a role-only escalation distinctly from a person-specific one', async () => {
    server.use(
      http.get('/v1/findings/escalated', () =>
        HttpResponse.json([
          makeFinding({
            id: '44444444-4444-4444-a444-444444444444',
            escalatedToRole: 'RISK_ANALYST',
            escalatedToUserId: null,
          }),
        ]),
      ),
      http.get('/v1/applications/:id', ({ params }) =>
        HttpResponse.json({
          id: params.id,
          losReference: 'LOS-9002',
          loanNumber: null,
          status: 'IN_REVIEW',
          activePolicyPackId: null,
          partyCount: 1,
          createdAt: '2026-06-20T09:00:00Z',
          updatedAt: null,
        }),
      ),
    );
    renderEscalationQueue();

    expect(await screen.findByText('Escalated to RISK_ANALYST')).toBeInTheDocument();
  });

  it('shows an error state when the escalation query fails', async () => {
    server.use(
      http.get('/v1/findings/escalated', () => HttpResponse.json(null, { status: 500 })),
    );
    renderEscalationQueue();

    await waitFor(
      () => {
        expect(screen.getByText('Could not load the escalation queue')).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });
});
