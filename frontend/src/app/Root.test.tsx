import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { queryClient } from '@app/queryClient';

import { routeTree } from '../routeTree.gen';
import { FIXTURE_APPLICATION_ID } from '../test/msw/handlers';
import { server } from '../test/msw/server';

function renderAtRoot() {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ['/'] }),
    context: { queryClient },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe('Root', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('redirects to the first application’s Workspace', async () => {
    server.use(
      http.get('/v1/applications', () => {
        return HttpResponse.json({
          items: [
            {
              id: FIXTURE_APPLICATION_ID,
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

    renderAtRoot();

    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
    });
  });

  it('shows an empty state when there are no applications', async () => {
    server.use(
      http.get('/v1/applications', () => {
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20 });
      }),
    );

    renderAtRoot();

    await waitFor(() => {
      expect(screen.getByText('No applications yet')).toBeInTheDocument();
    });
  });
});
