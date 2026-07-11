import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../../routeTree.gen';
import { server } from '../../test/msw/server';

function renderPolicyAdministration() {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/policy-administration'] }),
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

const SAMPLE_PACK = {
  id: '11111111-1111-4111-8111-111111111111',
  tenant_id: '22222222-2222-4222-8222-222222222222',
  version: '1.0.0',
  name: 'Standard Pack',
  jurisdiction: 'US',
  is_active: false,
  activated_at: null,
  deactivated_at: null,
  created_at: '2026-07-01T00:00:00Z',
};

describe('PolicyAdministrationPage', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('renders the heading and an empty state when there are no packs', async () => {
    server.use(http.get('/v1/policy-packs', () => HttpResponse.json({ items: [] })));

    renderPolicyAdministration();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Policy Packs' })).toBeInTheDocument();
    });
    expect(await screen.findByText('No policy packs yet')).toBeInTheDocument();
  });

  it('creates a draft pack via the New pack dialog', async () => {
    server.use(http.get('/v1/policy-packs', () => HttpResponse.json({ items: [] })));
    let capturedBody: Record<string, unknown> | null = null;
    server.use(
      http.post('/v1/policy-packs', async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...SAMPLE_PACK, version: capturedBody.version }, { status: 201 });
      }),
    );

    renderPolicyAdministration();
    const user = userEvent.setup();

    await screen.findByText('No policy packs yet');
    await user.click(screen.getByRole('button', { name: 'New pack' }));
    await user.type(screen.getByLabelText('Version'), '2.0.0');
    await user.type(screen.getByLabelText('Name'), 'US Standard Pack');
    await user.click(screen.getByRole('button', { name: 'Create draft' }));

    await waitFor(() => {
      expect(capturedBody).toMatchObject({ version: '2.0.0', name: 'US Standard Pack' });
    });
  });

  it('shows pack status and lets a drafter submit for approval', async () => {
    server.use(http.get('/v1/policy-packs', () => HttpResponse.json({ items: [SAMPLE_PACK] })));
    server.use(
      http.get(`/v1/policy-packs/${SAMPLE_PACK.id}/rules`, () => HttpResponse.json([])),
      http.get(`/v1/policy-packs/${SAMPLE_PACK.id}/approvals`, () => HttpResponse.json({ items: [] })),
    );
    let submitted = false;
    server.use(
      http.post(`/v1/policy-packs/${SAMPLE_PACK.id}/submit-for-approval`, () => {
        submitted = true;
        return HttpResponse.json(
          {
            id: '33333333-3333-4333-8333-333333333333',
            policy_pack_id: SAMPLE_PACK.id,
            requested_by_user_id: '44444444-4444-4444-8444-444444444444',
            decided_by_user_id: null,
            decision: 'PENDING',
            reason: null,
            decided_at: null,
            created_at: '2026-07-11T00:00:00Z',
          },
          { status: 201 },
        );
      }),
    );

    renderPolicyAdministration();
    const user = userEvent.setup();

    await screen.findByText('Standard Pack');
    expect(screen.getByText('Draft')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Standard Pack/ }));
    await user.click(await screen.findByRole('button', { name: 'Submit for approval' }));

    await waitFor(() => {
      expect(submitted).toBe(true);
    });
  });
});
