/**
 * Button (spec 003 T021) — the sole button primitive in the product.
 *
 * State model (FR-078): default, hover, focus (via the single dedicated
 * focus-ring token, FR-021), active/pressed, disabled, and loading are all
 * defined below. An "error" state is deliberately NOT a distinct Button
 * visual variant: a button does not fail on its own — the action it
 * triggers does, and that failure is represented by the surrounding
 * feedback pattern (`ErrorState`, a toast, or a form's inline validation
 * message), never by recoloring the button itself, which would conflate two
 * different meanings (FR-073: "against representing the same concept two
 * different visual ways" applies here in reverse — a button's identity
 * should not change based on transient outcomes of past clicks).
 *
 * Variants map directly to the three interaction-token groups defined in
 * `tokens/color.semantic.ts` (primary/secondary/danger) — there is no
 * fourth variant and no way to pass an arbitrary color.
 */

import { Loader2 } from 'lucide-react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@design-system/lib/cn';

const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 rounded-interactive font-medium',
    'text-label transition-colors duration-micro ease-standard',
    'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
    'disabled:pointer-events-none disabled:cursor-not-allowed',
  ],
  {
    variants: {
      variant: {
        primary:
          'bg-interactive-primary-default text-text-on-brand hover:bg-interactive-primary-hover active:bg-interactive-primary-active disabled:bg-interactive-primary-disabled disabled:text-interactive-primary-disabled-text',
        secondary:
          'bg-interactive-secondary-default text-text-primary border border-interactive-secondary-border hover:bg-interactive-secondary-hover active:bg-interactive-secondary-active disabled:bg-interactive-secondary-disabled disabled:text-text-disabled',
        danger:
          'bg-interactive-danger-default text-text-on-brand hover:bg-interactive-danger-hover active:bg-interactive-danger-active disabled:bg-interactive-primary-disabled disabled:text-interactive-primary-disabled-text',
      },
      size: {
        sm: 'h-8 px-3 text-caption',
        md: 'h-9 px-4',
        lg: 'h-10 px-5',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  /** Renders the child element instead of a <button> (Radix Slot pattern). */
  readonly asChild?: boolean;
  /**
   * The action this button triggers is in flight — disables the button,
   * replaces its icon slot with a spinner, and exposes `aria-busy` so
   * assistive technology announces the in-progress state (FR-072).
   */
  readonly loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant, size, asChild = false, loading = false, disabled, children, ...props },
    ref,
  ) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        disabled={Boolean(disabled) || loading}
        aria-busy={loading}
        {...props}
      >
        {loading ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
        {children}
      </Comp>
    );
  },
);
Button.displayName = 'Button';
