/**
 * PageContainer (RC3 — Enterprise Experience & Visual Excellence, Layout
 * System). Every top-level page in the product previously rolled its own
 * `mx-auto max-w-{4xl,5xl,6xl,7xl}` wrapper, independently guessed per
 * route — the result was inconsistent (and often accidentally narrower
 * than intended: five separate admin/analytics/queue routes all landed on
 * the same copy-pasted `max-w-5xl` — 1024px — regardless of how
 * information-dense their actual content was) rather than a deliberate
 * choice. This is the one place that choice is made, in two variants:
 *
 * - `"workspace"` (~1480px): a single focused record read top-to-bottom —
 *   the Application Workspace and every region within it (Documents,
 *   Evidence, Findings, Policy, Timeline, Copilot — all one container
 *   already), the Borrower Profile, the Escalation Queue's review list.
 *   Bounded for reading comfort, not stretched just because the monitor is
 *   wide.
 * - `"dense"` (~1760px): tabular/administrative surfaces meant to show as
 *   much real information at once as the data actually has — the
 *   Dashboard, Business Analytics, the Application Queue, Operational
 *   Dashboard, Administration, Policy Administration, the Banker
 *   Workspace's portfolio table. These widen to use a modern widescreen
 *   monitor rather than leaving it mostly empty.
 *
 * Deliberately not a global margin removal (RC3 explicitly warns against
 * that) — both variants stay centered and bounded, just at two considered
 * widths instead of five accidental ones.
 */

import type { ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';

export type PageContainerVariant = 'workspace' | 'dense';

const VARIANT_MAX_WIDTH_CLASS_NAME: Record<PageContainerVariant, string> = {
  workspace: 'max-w-[1480px]',
  dense: 'max-w-[1760px]',
};

export interface PageContainerProps {
  readonly variant: PageContainerVariant;
  readonly className?: string;
  readonly children?: ReactNode;
}

export function PageContainer({ variant, className, children }: PageContainerProps) {
  return (
    <div
      className={cn(
        'mx-auto flex w-full flex-col gap-6 p-6',
        VARIANT_MAX_WIDTH_CLASS_NAME[variant],
        className,
      )}
    >
      {children}
    </div>
  );
}
