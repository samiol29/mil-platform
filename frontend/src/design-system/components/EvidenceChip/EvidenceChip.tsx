/**
 * EvidenceChip (spec 003 T028, FR-059) — the single, reusable representation
 * of a citation or evidence reference, used identically wherever one appears
 * (a finding's evidence list, a Copilot citation, the audit trail) so a user
 * learns its meaning once and recognizes it everywhere.
 *
 * Domain-agnostic by design (plan.md's Design System layer "has no knowledge
 * of mortgage domain concepts") — it takes a plain label and an activation
 * callback; it does not know what an `EvidenceItem` is. The feature layer
 * (US1's Evidence Explorer/Document Viewer) supplies the label and wires
 * `onActivate` to navigate to the item's exact source location, satisfying
 * 002 FR-048's "one action from its source location" requirement — this
 * component only guarantees that exactly one action exists, not what it does.
 *
 * Always interactive (a `<button>`, never a static label) — an evidence
 * reference that cannot be followed to its source is a citation in name
 * only, contrary to Constitution Principle II.
 */

import { FileText } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@design-system/lib/cn';

export interface EvidenceChipProps extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  'children'
> {
  readonly label: string;
  readonly icon?: LucideIcon;
}

export const EvidenceChip = forwardRef<HTMLButtonElement, EvidenceChipProps>(
  ({ label, icon: Icon = FileText, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type="button"
        className={cn(
          'inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-caption font-medium',
          'bg-surface-secondary border-border-default text-text-secondary',
          'hover:bg-surface-disabled hover:text-text-primary',
          'transition-colors duration-micro ease-standard',
          'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
          'disabled:pointer-events-none disabled:opacity-50',
          className,
        )}
        {...props}
      >
        <Icon className="size-3.5" aria-hidden="true" />
        {label}
      </button>
    );
  },
);
EvidenceChip.displayName = 'EvidenceChip';
