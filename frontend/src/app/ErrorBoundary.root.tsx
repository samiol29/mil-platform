/**
 * Root error boundary (spec 002 tasks.md T039; plan.md Error Boundaries,
 * tier 1) — catches a truly unrecoverable error (e.g. the design-system
 * provider itself failing to initialize). Renders a full-screen,
 * plain-language failure state with a reload action; there is nothing
 * beneath this tier to fall back to, so recovery is a full page reload,
 * not a local state reset.
 */

import type { ReactNode } from 'react';

import { ErrorState } from '@design-system/components/ErrorState';
import { ErrorBoundaryBase } from '@shared/errors/ErrorBoundaryBase';

export interface RootErrorBoundaryProps {
  readonly children: ReactNode;
}

export function RootErrorBoundary({ children }: RootErrorBoundaryProps) {
  return (
    <ErrorBoundaryBase
      boundary="root"
      renderFallback={(error) => (
        <div className="bg-surface-background flex min-h-screen items-center justify-center p-6">
          <ErrorState
            title="MIL failed to load"
            description="Something went wrong while starting the application. Reloading usually resolves this."
            details={error.message}
            onRetry={() => {
              window.location.reload();
            }}
            className="max-w-md"
          />
        </div>
      )}
    >
      {children}
    </ErrorBoundaryBase>
  );
}
