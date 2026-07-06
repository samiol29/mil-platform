/**
 * Root route (spec 002 tasks.md T037) — the persistent application chrome
 * every route renders inside of: the top bar carrying the UserMenu
 * (FR-007) and the route outlet, wrapped in the route-level error boundary
 * (plan.md Error Boundaries, tier 2) so a failure loading one route's
 * content never takes down this persistent chrome.
 */

import type { QueryClient } from '@tanstack/react-query';
import { Outlet, createRootRouteWithContext } from '@tanstack/react-router';

import { UserMenu } from '@app/UserMenu';
import { RouteErrorBoundary } from '@shared/errors/RouteErrorBoundary';

export interface RouterContext {
  readonly queryClient: QueryClient;
}

function RootLayout() {
  return (
    <div className="bg-surface-background min-h-screen">
      <header className="border-border-subtle bg-surface-raised flex items-center justify-end border-b px-6 py-3">
        <UserMenu />
      </header>
      <main>
        <RouteErrorBoundary>
          <Outlet />
        </RouteErrorBoundary>
      </main>
    </div>
  );
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
});
