import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { queryClient } from '@app/queryClient';
import { useUiStore } from '@app/uiStore';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../routeTree.gen';
import { server } from '../test/msw/server';

// cmdk (the CommandPalette's underlying library) requires ResizeObserver,
// which jsdom does not implement — same stub already established by
// ApplicationQueueTable.test.tsx/UserManagementTable.test.tsx.
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
});

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

describe('CommandPaletteHost — Universal Search (spec 005 §7, Wave 2)', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
    useUiStore.getState().closeCommandPalette();
  });

  it('shows matching documents from the unified search endpoint', async () => {
    server.use(
      http.get('/v1/applications', () => HttpResponse.json({ items: [] })),
      http.get('/v1/search', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('kinds')).toBe('document');
        return HttpResponse.json({
          query: url.searchParams.get('q'),
          results: [
            {
              kind: 'document',
              documentId: '11111111-1111-4111-8111-111111111111',
              applicationId: '22222222-2222-4222-8222-222222222222',
              filename: 'bank-statement.pdf',
              uploadedAt: '2026-07-01T00:00:00Z',
            },
          ],
        });
      }),
    );

    renderApp();
    await waitFor(() => {
      expect(document.body.textContent).not.toBe('');
    });
    useUiStore.getState().openCommandPalette();
    const user = userEvent.setup();

    const input = await screen.findByPlaceholderText(/Search by loan/);
    await user.type(input, 'bank');

    expect(await screen.findByText('bank-statement.pdf')).toBeInTheDocument();
    expect(screen.getByText('Documents')).toBeInTheDocument();
  });
});
