/**
 * ErrorState (spec 003 T024, FR-045, FR-049) — the single, consistent
 * error-state pattern used identically across the product.
 *
 * Rules this component enforces structurally, not by convention:
 * - `title`/`description` MUST be plain language — this component has no
 *   prop for rendering a raw error/exception as the primary message.
 * - Raw technical detail (`details`) is optional and, when present, is
 *   rendered inside a collapsed `<details>` disclosure — visible on demand
 *   for support/debugging, never as the primary, always-visible message
 *   (FR-045: "never exposes raw technical detail as the primary message").
 * - `onRetry`, when supplied, renders the one retry action; there is no way
 *   to render more than one primary action from this component, keeping the
 *   pattern consistent everywhere it appears.
 * - Uses the dedicated `feedback.error` color family plus a non-decorative
 *   icon — never the Status, Confidence, or AI-signal families (FR-049:
 *   distinguishable from every other feedback state without reading text).
 */

import { AlertCircle } from 'lucide-react';

import { Button } from '@design-system/components/Button';
import { cn } from '@design-system/lib/cn';

export interface ErrorStateProps {
  readonly title?: string;
  readonly description?: string;
  readonly details?: string;
  readonly onRetry?: () => void;
  /**
   * `panel` (default): the full centered treatment for a region/page that
   * failed outright. `inline` (Product Experience phase, Phase 11): a
   * compact left-aligned strip for a failed *sub*-panel — clearly an
   * error, but proportionate: a failed side query must not visually
   * dominate the content a reviewer actually came to read.
   */
  readonly variant?: 'panel' | 'inline';
  readonly className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  description = 'This content could not be loaded. You can try again.',
  details,
  onRetry,
  variant = 'panel',
  className,
}: ErrorStateProps) {
  if (variant === 'inline') {
    return (
      <div
        role="alert"
        className={cn(
          'bg-feedback-error-bg rounded-container flex flex-wrap items-center gap-2.5 px-3 py-2',
          className,
        )}
      >
        <AlertCircle className="text-feedback-error-fg size-4 shrink-0" aria-hidden="true" />
        <span className="text-label text-feedback-error-fg font-medium">{title}</span>
        <span className="text-caption text-text-secondary">{description}</span>
        {onRetry !== undefined && (
          <Button variant="secondary" size="sm" onClick={onRetry} className="ml-auto">
            Try again
          </Button>
        )}
      </div>
    );
  }

  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center gap-3 rounded-container border px-6 py-8 text-center',
        'bg-feedback-error-bg border-feedback-error-border',
        className,
      )}
    >
      <AlertCircle className="text-feedback-error-fg size-8" aria-hidden="true" />
      <p className="text-feedback-error-fg text-body-emphasis">{title}</p>
      <p className="max-w-[40ch] text-body text-text-secondary">{description}</p>
      {onRetry !== undefined && (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-1">
          Try again
        </Button>
      )}
      {details !== undefined && details.length > 0 && (
        <details className="mt-2 w-full max-w-[40ch] text-left">
          <summary className="cursor-pointer text-caption text-text-secondary">
            Technical details
          </summary>
          <pre className="mt-1 overflow-x-auto text-caption text-text-secondary">{details}</pre>
        </details>
      )}
    </div>
  );
}
