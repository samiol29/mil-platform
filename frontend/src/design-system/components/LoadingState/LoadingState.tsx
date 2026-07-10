/**
 * LoadingState (spec 003 T022, FR-042) — the single indeterminate-loading
 * pattern used identically across every view in the product. Used only when
 * the eventual content's shape is NOT known ahead of time; where it is
 * known, `SkeletonState` is used instead (FR-043).
 *
 * Accessibility (FR-072): `role="status"` + `aria-live="polite"` announces
 * the loading state to assistive technology without interrupting other
 * announcements; the visible label is never icon-only.
 */

import { Loader2 } from 'lucide-react';

import { cn } from '@design-system/lib/cn';

export interface LoadingStateProps {
  readonly label?: string;
  readonly className?: string;
}

export function LoadingState({ label = 'Loading…', className }: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn('flex items-center gap-2 text-body text-text-secondary', className)}
    >
      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
