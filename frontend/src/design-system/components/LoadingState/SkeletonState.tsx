/**
 * SkeletonState (spec 003 T022, FR-043) — a structural placeholder matching
 * the eventual content's layout, used wherever that shape is known ahead of
 * time (a queue-row skeleton is row-shaped, a finding-card skeleton is
 * finding-card-shaped) in place of an indeterminate `LoadingState` spinner.
 *
 * `Skeleton` is the atomic shimmering block; `SkeletonText` and `SkeletonRow`
 * are the two composed shapes this product's data-dense screens need most
 * (a line of text, a table/list row) — additional shapes compose from
 * `Skeleton` directly rather than requiring a new primitive per screen.
 */

import { cn } from '@design-system/lib/cn';

export interface SkeletonProps {
  readonly className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-interactive bg-surface-disabled', className)}
    />
  );
}

export interface SkeletonTextProps {
  readonly lines?: number;
  readonly className?: string;
}

export function SkeletonText({ lines = 1, className }: SkeletonTextProps) {
  return (
    <div
      role="status"
      aria-label="Loading content"
      className={cn('flex flex-col gap-2', className)}
    >
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} className={cn('h-4', index === lines - 1 && lines > 1 && 'w-3/4')} />
      ))}
    </div>
  );
}

export interface SkeletonRowProps {
  readonly columns?: number;
  readonly className?: string;
}

export function SkeletonRow({ columns = 4, className }: SkeletonRowProps) {
  return (
    <div
      role="status"
      aria-label="Loading row"
      className={cn('flex h-10 items-center gap-4 border-b border-border-subtle px-4', className)}
    >
      {Array.from({ length: columns }, (_, index) => (
        <Skeleton key={index} className="h-4 flex-1" />
      ))}
    </div>
  );
}
