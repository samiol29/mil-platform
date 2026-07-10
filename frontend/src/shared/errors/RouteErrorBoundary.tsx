/**
 * Route-level error boundary (spec 002 tasks.md T040; plan.md Error
 * Boundaries, tier 2) — catches a failure loading or rendering one route's
 * content (e.g. an application that fails to load); the surrounding app
 * shell (navigation, command palette) remains usable because this boundary
 * wraps only the route outlet, not the whole application.
 *
 * "Try again" resets the boundary's own state, re-rendering the route's
 * children fresh — sufficient for a transient network failure, which is
 * the dominant real-world cause of a route-load failure in this product.
 */

import type { ReactNode } from 'react';

import { ErrorState } from '@design-system/components/ErrorState';
import { ErrorBoundaryBase } from '@shared/errors/ErrorBoundaryBase';

export interface RouteErrorBoundaryProps {
  readonly children: ReactNode;
}

export function RouteErrorBoundary({ children }: RouteErrorBoundaryProps) {
  return (
    <ErrorBoundaryBase
      boundary="route"
      renderFallback={(error, reset) => (
        <div className="flex items-center justify-center p-12">
          <ErrorState
            title="This page could not be loaded"
            description="Something went wrong loading this content. You can try again."
            details={error.message}
            onRetry={reset}
            className="max-w-md"
          />
        </div>
      )}
    >
      {children}
    </ErrorBoundaryBase>
  );
}
