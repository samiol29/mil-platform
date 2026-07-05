/**
 * Drawer (spec 003 T029, FR-051, FR-053) — the contextual, non-blocking
 * panel pattern for viewing/editing tasks that should not interrupt the
 * surrounding application context (e.g. the Evidence Explorer inspecting one
 * evidence item without leaving the Application Workspace). This is the
 * enterprise-appropriate alternative to `Dialog` for anything that is not a
 * genuinely blocking confirmation (FR-050, FR-073).
 *
 * Built on `@radix-ui/react-dialog` in non-modal-adjacent styling (a Drawer
 * is Radix's Dialog primitive with side-panel sizing/positioning) — focus
 * trap, `Escape`-to-dismiss, and return-focus-on-close are provided by Radix
 * (FR-053), identically to `Dialog`.
 *
 * Stacking rule (FR-051): only one Drawer is ever open at a time in this
 * product's UI composition — a second `open` Drawer replaces, rather than
 * layers atop, the first. This is enforced by feature-layer composition
 * (one Drawer instance mounted at a time), not by this primitive itself.
 */

import * as RadixDialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';

export type DrawerSide = 'left' | 'right';
export type DrawerSize = 'sm' | 'md' | 'lg';

const sizeClassName: Record<DrawerSize, string> = {
  sm: 'w-80',
  md: 'w-[28rem]',
  lg: 'w-[36rem]',
};

export interface DrawerProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly title: string;
  readonly children: ReactNode;
  readonly side?: DrawerSide;
  readonly size?: DrawerSize;
}

export function Drawer({
  open,
  onOpenChange,
  title,
  children,
  side = 'right',
  size = 'md',
}: DrawerProps) {
  const isRight = side === 'right';
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay
          className={cn(
            'fixed inset-0 z-40 bg-black/30',
            'opacity-0 data-[state=open]:opacity-100 data-[state=closed]:opacity-0',
            'transition-opacity duration-panel ease-decelerate',
          )}
        />
        <RadixDialog.Content
          className={cn(
            'fixed top-0 z-40 flex h-full flex-col',
            'bg-surface-overlay border-border-default shadow-overlay outline-none',
            isRight ? 'right-0 border-l' : 'left-0 border-r',
            sizeClassName[size],
            'translate-x-0 data-[state=closed]:opacity-0',
            isRight
              ? 'data-[state=closed]:translate-x-full'
              : 'data-[state=closed]:-translate-x-full',
            'transition-transform duration-panel ease-decelerate',
          )}
        >
          <div className="border-border-subtle flex items-center justify-between border-b px-5 py-4">
            <RadixDialog.Title className="text-heading-section text-text-primary">
              {title}
            </RadixDialog.Title>
            {/* Radix requires an accessible description on every Content;
                this Drawer's body is arbitrary children, so an sr-only
                fallback satisfies the requirement without visual change. */}
            <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
            <RadixDialog.Close asChild>
              <button
                type="button"
                aria-label="Close panel"
                className={cn(
                  'rounded-interactive p-1 text-text-tertiary',
                  'hover:bg-surface-disabled hover:text-text-primary',
                  'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
                )}
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </RadixDialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
