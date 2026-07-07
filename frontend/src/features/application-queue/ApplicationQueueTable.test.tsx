import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../../routeTree.gen';
import { server } from '../../test/msw/server';

// `Table` (design-system) virtualizes rows with @tanstack/react-virtual, which
// measures the scroll container via ResizeObserver/getBoundingClientRect —
// neither of which jsdom implements with a non-zero layout by default, so a
// virtualized list renders zero rows in jsdom unless stubbed. Scoped to this
// file only (not global test setup) since this is the first feature to use
// `Table`.
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

function renderQueue(initialEntry = '/applications') {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialEntry] }),
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

describe('ApplicationQueueTable', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('renders the queue heading, search box, and stage filter chips', async () => {
    server.use(
      http.get('/v1/applications', () => {
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 });
      }),
    );

    renderQueue();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Application Queue' })).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Search applications')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'In Review' })).toBeInTheDocument();
  });

  it('shows an empty state when no applications match', async () => {
    server.use(
      http.get('/v1/applications', () => {
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 });
      }),
    );

    renderQueue();

    await waitFor(() => {
      expect(screen.getByText('No applications yet')).toBeInTheDocument();
    });
  });

  it('sends the search box value as the search query param', async () => {
    let capturedUrl: URL | null = null;
    server.use(
      http.get('/v1/applications', ({ request }) => {
        capturedUrl = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 });
      }),
    );

    renderQueue();
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByLabelText('Search applications')).toBeInTheDocument();
    });
    await user.type(screen.getByLabelText('Search applications'), 'Alvarez');

    await waitFor(() => {
      expect(capturedUrl?.searchParams.get('search')).toBe('Alvarez');
    });
  });

  it('applies the status from the route search param as the active filter', async () => {
    let capturedUrl: URL | null = null;
    server.use(
      http.get('/v1/applications', ({ request }) => {
        capturedUrl = new URL(request.url);
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 });
      }),
    );

    renderQueue('/applications?status=IN_REVIEW');

    await waitFor(() => {
      expect(capturedUrl?.searchParams.get('status')).toBe('IN_REVIEW');
    });
    expect(screen.getByRole('button', { name: 'In Review' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });
});

describe('ApplicationQueueTable rows', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('renders a row for each returned application', async () => {
    server.use(
      http.get('/v1/applications', () => {
        return HttpResponse.json({
          items: [
            {
              id: '11111111-1111-1111-a111-111111111111',
              losReference: 'LOS-0000042',
              loanNumber: '4009123456',
              status: 'IN_REVIEW',
              activePolicyPackId: null,
              partyCount: 1,
              createdAt: '2026-01-01T00:00:00Z',
              updatedAt: '2026-01-01T00:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        });
      }),
    );

    renderQueue();

    await waitFor(() => {
      expect(screen.getByText('4009123456')).toBeInTheDocument();
    });
  });
});
