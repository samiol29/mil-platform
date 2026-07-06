/**
 * Router configuration and root provider composition (spec 002 tasks.md
 * T037; plan.md Routing Strategy, State Management).
 *
 * `AppProviders` is the one place Theme, Query, and Router providers are
 * composed — `main.tsx` renders only this (inside the root error boundary),
 * so no other module needs to know the provider order or the query client
 * instance.
 */

import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createRouter } from '@tanstack/react-router';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { routeTree } from '../routeTree.gen';

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  context: { queryClient },
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

export function AppProviders() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
