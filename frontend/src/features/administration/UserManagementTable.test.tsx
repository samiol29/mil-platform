import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../../routeTree.gen';
import { server } from '../../test/msw/server';

// Same jsdom/virtualized-Table stub as ApplicationQueueTable.test.tsx — this
// is the second feature to render the design-system `Table` primitive.
beforeAll(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {
        // no-op: jsdom has no real layout to observe
      }
      unobserve() {
        // no-op
      }
      disconnect() {
        // no-op
      }
    },
  );
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
    configurable: true,
    value: 600,
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    value: 600,
  });
});

function renderAdministration() {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/administration'] }),
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

const SAMPLE_USER = {
  id: '11111111-1111-4111-8111-111111111111',
  tenant_id: '22222222-2222-4222-8222-222222222222',
  display_name: 'Jane Reviewer',
  is_active: true,
  roles: ['UNDERWRITER'],
  created_at: '2026-07-01T00:00:00Z',
};

describe('UserManagementTable', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('renders the users heading and existing users', async () => {
    server.use(http.get('/v1/admin/users', () => HttpResponse.json({ items: [SAMPLE_USER] })));

    renderAdministration();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Users' })).toBeInTheDocument();
    });
    expect(await screen.findByText('Jane Reviewer')).toBeInTheDocument();
    expect(screen.getByText('UNDERWRITER')).toBeInTheDocument();
  });

  it('shows an empty state when there are no users', async () => {
    server.use(http.get('/v1/admin/users', () => HttpResponse.json({ items: [] })));

    renderAdministration();

    await waitFor(() => {
      expect(screen.getByText('No users yet')).toBeInTheDocument();
    });
  });

  it('creates a user via the New user dialog', async () => {
    server.use(http.get('/v1/admin/users', () => HttpResponse.json({ items: [] })));
    let capturedBody: Record<string, unknown> | null = null;
    server.use(
      http.post('/v1/admin/users', async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { ...SAMPLE_USER, display_name: capturedBody.display_name, roles: [] },
          { status: 201 },
        );
      }),
    );

    renderAdministration();
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByText('No users yet')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'New user' }));
    await user.type(screen.getByLabelText('External identity id'), 'idp-002');
    await user.type(screen.getByLabelText('Email'), 'new@example.com');
    await user.type(screen.getByLabelText('Display name'), 'New Reviewer');
    await user.click(screen.getByRole('button', { name: 'Create user' }));

    await waitFor(() => {
      expect(capturedBody).toMatchObject({
        external_identity_id: 'idp-002',
        email: 'new@example.com',
        display_name: 'New Reviewer',
      });
    });
  });

  it('assigns a role to a user via the Assign role dialog', async () => {
    server.use(http.get('/v1/admin/users', () => HttpResponse.json({ items: [SAMPLE_USER] })));
    let capturedRole: string | null = null;
    server.use(
      http.post(`/v1/admin/users/${SAMPLE_USER.id}/roles`, async ({ request }) => {
        const body = (await request.json()) as { role_name: string };
        capturedRole = body.role_name;
        return HttpResponse.json(
          {
            id: '33333333-3333-4333-8333-333333333333',
            user_id: SAMPLE_USER.id,
            role_id: '44444444-4444-4444-8444-444444444444',
            role_name: body.role_name,
            assigned_by: '55555555-5555-4555-8555-555555555555',
            assigned_at: '2026-07-11T00:00:00Z',
            revoked_at: null,
          },
          { status: 201 },
        );
      }),
    );

    renderAdministration();
    const user = userEvent.setup();

    await screen.findByText('Jane Reviewer');
    const nameCell = screen.getByText('Jane Reviewer');
    const row = nameCell.closest('[role="row"]') ?? nameCell.parentElement;
    if (row === null) throw new Error('Expected a row element for Jane Reviewer');
    await user.click(within(row as HTMLElement).getByRole('button', { name: 'Assign role' }));

    const dialog = await screen.findByRole('dialog');
    await user.selectOptions(within(dialog).getByLabelText('Role'), 'COMPLIANCE_OFFICER');
    await user.click(within(dialog).getByRole('button', { name: 'Assign role' }));

    await waitFor(() => {
      expect(capturedRole).toBe('COMPLIANCE_OFFICER');
    });
  });
});
