/**
 * Panel-level error boundary (spec 002 tasks.md T041; plan.md Error
 * Boundaries, tier 3) — wraps each independently-loaded region within the
 * Application Workspace (Copilot panel, Evidence Explorer, Knowledge Graph
 * view) so, e.g., a Copilot failure never blanks the Findings view next to
 * it. The smallest, most localized of the three tiers — its fallback is
 * inline and compact, sized for a panel rather than a full page.
 */

import type { ReactNode } from 'react';

import { ErrorState } from '@design-system/components/ErrorState';
import { ErrorBoundaryBase } from '@shared/errors/ErrorBoundaryBase';

export interface PanelErrorBoundaryProps {
  readonly children: ReactNode;
  /** Identifies which panel failed, for the telemetry report and (optionally) the message. */
  readonly panelName: string;
}

export function PanelErrorBoundary({ children, panelName }: PanelErrorBoundaryProps) {
  return (
    <ErrorBoundaryBase
      boundary="panel"
      renderFallback={(error, reset) => (
        <ErrorState
          title={`${panelName} could not be loaded`}
          description="You can try again, or continue working in the rest of this page."
          details={error.message}
          onRetry={reset}
          className="p-6"
        />
      )}
    >
      {children}
    </ErrorBoundaryBase>
  );
}
