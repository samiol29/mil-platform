/**
 * Input (spec 003 Component Architecture) — the sole single-line text-input
 * primitive in the product. Replaces the hand-styled native `<input>`
 * elements that previously existed only inside `FindingActions.tsx`'s
 * override form.
 *
 * State model matches `Button`'s discipline: default, hover/focus (the
 * single dedicated focus-ring token, FR-021), disabled, and an `invalid`
 * state using the `feedback-error` family — never the Status/Confidence
 * color families, which are reserved for other meanings (FR-022).
 */

import { forwardRef } from 'react';
import type { InputHTMLAttributes } from 'react';

import { cn } from '@design-system/lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** The value entered has failed validation — renders the error border/focus treatment. */
  readonly invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid = false, disabled, ...props }, ref) => (
    <input
      ref={ref}
      disabled={disabled}
      aria-invalid={invalid}
      className={cn(
        'border-border-default bg-surface-background text-text-primary rounded-interactive text-body h-9 border px-3 py-2',
        'outline-none transition-colors duration-micro ease-standard',
        'placeholder:text-text-tertiary',
        'focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
        'disabled:bg-surface-disabled disabled:text-text-disabled disabled:cursor-not-allowed',
        invalid && 'border-feedback-error-border',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
