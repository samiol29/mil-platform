/**
 * EmptyState (spec 003 T023, FR-044) — the single, consistent empty-state
 * pattern used identically across every view that can have zero data.
 *
 * Deliberately minimal and action-oriented, never illustration-led (FR-037,
 * FR-044): a small icon (from the closed icon library), a plain-language
 * title, an optional one-line description, and an optional single action —
 * never a mascot or decorative illustration, which is pure visual cost in a
 * tool used by the same expert for years (Design Rationale).
 */

import type { LucideIcon } from 'lucide-react';
import { Inbox } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';

export interface EmptyStateProps {
  readonly icon?: LucideIcon;
  readonly title: string;
  readonly description?: string;
  readonly action?: ReactNode;
  readonly className?: string;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center gap-3 px-6 py-12 text-center',
        'text-text-secondary',
        className,
      )}
    >
      <Icon className="size-8 text-text-tertiary" aria-hidden="true" />
      <p className="text-body-emphasis text-text-primary">{title}</p>
      {description !== undefined && <p className="max-w-[40ch] text-body">{description}</p>}
      {action !== undefined && <div className="mt-2">{action}</div>}
    </div>
  );
}
