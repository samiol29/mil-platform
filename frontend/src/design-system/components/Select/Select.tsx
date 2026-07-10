/**
 * Select (spec 003 Component Architecture) — the sole native-select
 * primitive in the product. Replaces the hand-styled native `<select>`
 * previously used only in `FindingActions.tsx`'s escalate form.
 *
 * Deliberately a styled native `<select>`, not a custom listbox — the
 * escalate form's role picker is a short, closed enumeration (5 options),
 * exactly the case native `<select>` handles best (free keyboard/screen
 * reader support with zero extra work). A custom combobox primitive is not
 * introduced speculatively for a need this doesn't have (plan.md: no
 * over-engineering).
 */

import { ChevronDown } from 'lucide-react';
import { forwardRef } from 'react';
import type { SelectHTMLAttributes } from 'react';

import { cn } from '@design-system/lib/cn';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** The value selected has failed validation — renders the error border/focus treatment. */
  readonly invalid?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, invalid = false, disabled, children, ...props }, ref) => (
    <div className="relative">
      <select
        ref={ref}
        disabled={disabled}
        aria-invalid={invalid}
        className={cn(
          'border-border-default bg-surface-background text-text-primary rounded-interactive text-body h-9 w-full appearance-none border py-2 pr-9 pl-3',
          'outline-none transition-colors duration-micro ease-standard',
          'focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
          'disabled:bg-surface-disabled disabled:text-text-disabled disabled:cursor-not-allowed',
          invalid && 'border-feedback-error-border',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="text-text-tertiary pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
        aria-hidden="true"
      />
    </div>
  ),
);
Select.displayName = 'Select';
