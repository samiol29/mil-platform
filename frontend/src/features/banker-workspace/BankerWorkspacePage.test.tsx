import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../../routeTree.gen';
import { server } from '../../test/msw/server';

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
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 600 });
});

function renderBankerWorkspace() {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/banker-workspace'] }),
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

describe('BankerWorkspacePage', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('shows an empty state with no portfolio applications', async () => {
    server.use(http.get('/v1/rm/portfolio', () => HttpResponse.json({ items: [] })));

    renderBankerWorkspace();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'My Portfolio' })).toBeInTheDocument();
    });
    expect(await screen.findByText('No applications in your portfolio yet')).toBeInTheDocument();
  });

  it('lists a real owned application', async () => {
    server.use(
      http.get('/v1/rm/portfolio', () =>
        HttpResponse.json({
          items: [
            {
              id: '11111111-1111-4111-8111-111111111111',
              los_reference: 'LOS-999',
              loan_number: null,
              status: 'DRAFT',
              active_policy_pack_id: null,
              party_count: 1,
              created_at: '2026-07-01T00:00:00Z',
              updated_at: null,
            },
          ],
        }),
      ),
    );

    renderBankerWorkspace();

    expect(await screen.findByText('LOS-999')).toBeInTheDocument();
  });
});
