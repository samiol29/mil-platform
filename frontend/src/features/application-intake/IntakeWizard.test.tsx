import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { queryClient } from '@app/queryClient';
import { useUiStore } from '@app/uiStore';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../../routeTree.gen';
import { server } from '../../test/msw/server';

function renderApp() {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/'] }),
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

async function openWizard(user: ReturnType<typeof userEvent.setup>) {
  server.use(
    http.get('/v1/applications', () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 }),
    ),
  );
  renderApp();
  await waitFor(() => {
    expect(screen.getByText('No applications yet')).toBeInTheDocument();
  });
  await user.click(screen.getByRole('button', { name: /new application/i }));
  await waitFor(() => {
    expect(screen.getByText('LOS reference')).toBeInTheDocument();
  });
}

describe('IntakeWizard', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
    useUiStore.getState().closeIntakeWizard();
  });

  it('shows system-generated identifiers on the Application step, with nothing to type', async () => {
    const user = userEvent.setup();
    await openWizard(user);

    expect(screen.getByText('LOS reference')).toBeInTheDocument();
    expect(screen.getByText('Loan number')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('advances to Borrowers on Continue with no validation to pass, and Enter in the last row adds another row', async () => {
    const user = userEvent.setup();
    await openWizard(user);

    await user.click(screen.getByRole('button', { name: 'Continue' }));

    await waitFor(() => {
      expect(screen.getByText('Add another borrower')).toBeInTheDocument();
    });
    expect(screen.getAllByPlaceholderText('Borrower name')).toHaveLength(1);

    await user.type(screen.getAllByPlaceholderText('Borrower name')[0], 'Jamie Alvarez{Enter}');

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText('Borrower name')).toHaveLength(2);
    });
  });

  it('does not recreate the application on retry after a borrower-add failure', async () => {
    let createApplicationCalls = 0;
    let addPartyCalls = 0;

    server.use(
      http.post('/v1/applications', async ({ request }) => {
        createApplicationCalls += 1;
        const body = (await request.json()) as { los_reference: string; loan_number?: string };
        return HttpResponse.json(
          {
            id: '99999999-9999-4999-a999-999999999999',
            los_reference: body.los_reference,
            loan_number: body.loan_number ?? null,
            status: 'DRAFT',
            active_policy_pack_id: null,
            party_count: 0,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: null,
          },
          { status: 201 },
        );
      }),
      http.post('/v1/applications/:id/parties', ({ params }) => {
        addPartyCalls += 1;
        if (addPartyCalls === 1) {
          return HttpResponse.json({ detail: 'party creation failed' }, { status: 500 });
        }
        return HttpResponse.json(
          {
            id: '88888888-8888-4888-a888-888888888888',
            application_id: params.id,
            party_type: 'APPLICANT',
            display_name: 'Jamie Alvarez',
            created_at: '2026-01-01T00:00:00Z',
          },
          { status: 201 },
        );
      }),
    );

    const user = userEvent.setup();
    await openWizard(user);

    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await waitFor(() => {
      expect(screen.getByText('Add another borrower')).toBeInTheDocument();
    });

    await user.type(screen.getAllByPlaceholderText('Borrower name')[0], 'Jamie Alvarez');
    await user.click(screen.getByRole('button', { name: 'Continue' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create Application' })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Create Application' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    });
    expect(createApplicationCalls).toBe(1);
    expect(addPartyCalls).toBe(1);

    await user.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
    });
    expect(createApplicationCalls).toBe(1);
    expect(addPartyCalls).toBe(2);
  });
});
