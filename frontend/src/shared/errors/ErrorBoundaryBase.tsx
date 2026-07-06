/**
 * Shared error-boundary base (spec 002 tasks.md T039–T041; plan.md Error
 * Boundaries: three tiers — root, route, panel — each catching failures at
 * the granularity 002 FR-083 requires).
 *
 * React error boundaries must be class components (there is no Hook
 * equivalent) — this base is the one place that fact lives; `ErrorBoundary
 * .root.tsx`, `RouteErrorBoundary.tsx`, and `PanelErrorBoundary.tsx` each
 * configure it with their own fallback presentation and reset behavior
 * rather than re-implementing `componentDidCatch`/`getDerivedStateFromError`
 * three times.
 */

import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

import { reportError } from '@shared/telemetry/telemetry';

export interface ErrorBoundaryBaseProps {
  readonly children: ReactNode;
  readonly boundary: 'root' | 'route' | 'panel';
  readonly renderFallback: (error: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryBaseState {
  readonly error: Error | null;
}

export class ErrorBoundaryBase extends Component<ErrorBoundaryBaseProps, ErrorBoundaryBaseState> {
  override state: ErrorBoundaryBaseState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryBaseState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    reportError({
      message: error.message,
      ...(error.stack !== undefined ? { stack: error.stack } : {}),
      boundary: this.props.boundary,
      context: { componentStack: info.componentStack ?? '' },
    });
  }

  private readonly reset = (): void => {
    this.setState({ error: null });
  };

  override render(): ReactNode {
    if (this.state.error !== null) {
      return this.props.renderFallback(this.state.error, this.reset);
    }
    return this.props.children;
  }
}
