/**
 * SummaryGrid (spec 003 Component Architecture) — the single, consistent
 * key/value fact-summary pattern for grouped record data (an Application's
 * core fields, a grouped set of Evidence items), used identically wherever
 * a screen needs to present "here are the facts about this record" before
 * any narrative content (UX audit `plan.md`/`generic-fluttering-rocket.md`
 * §3, §5 — reimplements `frontend_reference`'s key/value card grid inside
 * the closed token vocabulary, corroborated by the Stripe/Vercel Dashboard
 * benchmark pattern of a compact fact-summary before any detail view).
 *
 * Responsive per the UX audit's §4a breakpoints: 1 column below `sm`, 2 at
 * `sm`, 3 at `lg` — using Tailwind's existing breakpoint scale, no new
 * breakpoint tokens. Each item is a `surface-raised`/`border-subtle`/
 * `rounded-container` card, matching `FindingCard`'s own padding/border/
 * radius vocabulary so the two read as the same visual language.
 */

import type { ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';
import { typeScaleClassName } from '@design-system/tokens/typography';

export interface SummaryGridItem {
  /** Unique key for list rendering — falls back to `label` when items are known-distinct. */
  readonly id?: string;
  readonly label: string;
  readonly value: ReactNode;
  /** Renders the value in the tabular/monospace figure style (IDs, loan numbers, amounts). */
  readonly tabular?: boolean;
}

export interface SummaryGridProps {
  readonly items: readonly SummaryGridItem[];
  readonly className?: string;
}

export function SummaryGrid({ items, className }: SummaryGridProps) {
  return (
    <dl className={cn('grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3', className)}>
      {items.map((item, index) => (
        <div
          key={item.id ?? `${item.label}-${String(index)}`}
          className="border-border-subtle bg-surface-raised rounded-container flex flex-col gap-1 border p-5"
        >
          <dt className="text-caption text-text-secondary">{item.label}</dt>
          <dd
            className={cn(
              'text-body-emphasis text-text-primary break-words',
              item.tabular === true && typeScaleClassName.dataTabular,
            )}
          >
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
