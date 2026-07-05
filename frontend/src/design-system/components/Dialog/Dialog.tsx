/**
 * Dialog (spec 003 T030, FR-050, FR-052, FR-053) — reserved strictly for
 * genuinely blocking confirmations (an irreversible or hard-to-reverse
 * action). It MUST NOT be used for routine viewing, editing, or multi-step
 * tasks — `Drawer` exists for that (FR-050, FR-073).
 *
 * Built on `@radix-ui/react-dialog` (shadcn/ui's accessible primitive,
 * customized to the design system's tokens, not used as-is) — focus trap,
 * `Escape`-to-dismiss, and return-focus-on-close are handled by Radix and
 * verified, not reimplemented (FR-053).
 *
 * Every Dialog has exactly one primary action and one secondary
 * ("Cancel"/safe) action; the safe path is never visually subordinated to
 * the confirming path (FR-052) — both render as equally-sized buttons, with
 * the confirming action styled `danger` only when the action it performs is
 * itself destructive, never merely to draw attention to it.
 */

import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';

import { Button } from '@design-system/components/Button';
import { cn } from '@design-system/lib/cn';

export interface DialogAction {
  readonly label: string;
  readonly onClick: () => void;
  readonly variant?: 'primary' | 'danger';
  readonly loading?: boolean;
}

export interface DialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly title: string;
  readonly description?: string;
  readonly children?: ReactNode;
  /** The single confirming action (FR-052). */
  readonly primaryAction: DialogAction;
  /** The safe/non-destructive path — defaults to a plain "Cancel". */
  readonly secondaryActionLabel?: string;
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  primaryAction,
  secondaryActionLabel = 'Cancel',
}: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay
          className={cn(
            'fixed inset-0 z-50 bg-black/40',
            'opacity-0 data-[state=open]:opacity-100 data-[state=closed]:opacity-0',
            'transition-opacity duration-panel ease-decelerate',
          )}
        />
        <RadixDialog.Content
          className={cn(
            'fixed top-1/2 left-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2',
            'bg-surface-overlay border-border-default rounded-container border p-6',
            'shadow-overlay outline-none',
            'scale-95 opacity-0 data-[state=open]:scale-100 data-[state=open]:opacity-100',
            'data-[state=closed]:scale-95 data-[state=closed]:opacity-0',
            'transition-all duration-panel ease-decelerate',
          )}
        >
          <RadixDialog.Title className="text-heading-section text-text-primary">
            {title}
          </RadixDialog.Title>
          {description !== undefined ? (
            <RadixDialog.Description className="mt-2 text-body text-text-secondary">
              {description}
            </RadixDialog.Description>
          ) : (
            // Radix requires every Dialog.Content to have an accessible
            // description; when the caller supplies none, this sr-only
            // fallback satisfies that requirement without a visual change.
            <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
          )}
          {children !== undefined && <div className="mt-4">{children}</div>}
          <div className="mt-6 flex justify-end gap-3">
            <RadixDialog.Close asChild>
              <Button variant="secondary">{secondaryActionLabel}</Button>
            </RadixDialog.Close>
            <Button
              variant={primaryAction.variant ?? 'primary'}
              onClick={primaryAction.onClick}
              loading={primaryAction.loading ?? false}
            >
              {primaryAction.label}
            </Button>
          </div>
          <RadixDialog.Close asChild>
            <button
              type="button"
              aria-label="Close dialog"
              className={cn(
                'absolute top-4 right-4 rounded-interactive p-1 text-text-tertiary',
                'hover:bg-surface-disabled hover:text-text-primary',
                'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
              )}
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </RadixDialog.Close>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
