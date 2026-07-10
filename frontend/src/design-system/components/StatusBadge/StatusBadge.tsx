/**
 * StatusBadge (spec 003 T025, FR-022, FR-026, FR-054) — the single, consistent
 * representation of workflow/SLA lifecycle state, used identically wherever
 * a status appears (queue rows, the Application Workspace header, filters).
 *
 * Always pairs the Status color family with its dedicated icon (`color.status.ts`)
 * — never color alone (FR-026) — so status remains legible in grayscale
 * print/export and to color-vision-deficient reviewers.
 */

import { statusTokens, type StatusLevel } from '@design-system/tokens/color.status';
import { cn } from '@design-system/lib/cn';

export interface StatusBadgeProps {
  readonly status: StatusLevel;
  readonly className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const token = statusTokens[status];
  const Icon = token.icon;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-caption font-medium',
        token.bgClassName,
        token.fgClassName,
        token.borderClassName,
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {token.label}
    </span>
  );
}
