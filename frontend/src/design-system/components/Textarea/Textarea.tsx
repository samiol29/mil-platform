/**
 * Textarea (spec 003 Component Architecture) — the sole multi-line
 * text-input primitive in the product. Replaces the hand-styled native
 * `<textarea>` elements previously duplicated across `FindingActions.tsx`'s
 * override and escalate forms.
 *
 * Same state model as `Input` (default/hover/focus/disabled/invalid) —
 * the two share the exact same visual treatment, differing only in the
 * element they render, so a reviewer never has to learn a second set of
 * field states.
 */

import { forwardRef } from 'react';
import type { TextareaHTMLAttributes } from 'react';

import { cn } from '@design-system/lib/cn';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** The value entered has failed validation — renders the error border/focus treatment. */
  readonly invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, invalid = false, disabled, rows = 3, ...props }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      disabled={disabled}
      aria-invalid={invalid}
      className={cn(
        'border-border-default bg-surface-background text-text-primary rounded-interactive text-body border px-3 py-2',
        'outline-none transition-colors duration-micro ease-standard resize-y',
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
Textarea.displayName = 'Textarea';
