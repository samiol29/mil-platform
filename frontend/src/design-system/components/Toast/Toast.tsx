/**
 * Toast (Product Experience phase, Phase 0) — transient, non-blocking
 * feedback for the outcome of an action the user already took (an upload
 * batch finished, a mutation succeeded) as distinct from the `Dialog`
 * component, which is reserved strictly for blocking confirmations before
 * an action happens (spec 003 FR-050).
 *
 * Deliberately neutral in color: this is not the Status family (spec 003
 * FR-022 — workflow/SLA lifecycle state only) and must never borrow its
 * palette. Every variant pairs an icon with text, never color alone
 * (FR-026), and renders in a single `aria-live="polite"` region so screen
 * readers announce new toasts without interrupting current focus.
 *
 * Props-driven, like `CommandPalette` — this component knows nothing about
 * `app/uiStore`. The app wires the shared toast queue in via `ToastHost`
 * (`app/ToastHost.tsx`), the same separation `CommandPaletteHost` keeps for
 * the Command Palette shell.
 */

import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useEffect } from 'react';

import { cn } from '@design-system/lib/cn';

export type ToastVariant = 'success' | 'error' | 'info';

export interface ToastData {
  readonly id: string;
  readonly title: string;
  readonly description?: string;
  readonly variant: ToastVariant;
}

const VARIANT_ICON: Readonly<Record<ToastVariant, LucideIcon>> = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
};

const VARIANT_ICON_CLASS_NAME: Readonly<Record<ToastVariant, string>> = {
  success: 'text-text-primary',
  error: 'text-text-critical',
  info: 'text-text-secondary',
};

const TOAST_DISPLAY_MS = 5_000;

export interface ToastViewportProps {
  readonly toasts: readonly ToastData[];
  readonly onDismiss: (id: string) => void;
  readonly className?: string;
}

export function ToastViewport({ toasts, onDismiss, className }: ToastViewportProps) {
  if (toasts.length === 0) {
    return null;
  }

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className={cn('fixed right-4 bottom-4 z-50 flex w-full max-w-sm flex-col gap-2', className)}
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({
  toast,
  onDismiss,
}: {
  readonly toast: ToastData;
  readonly onDismiss: (id: string) => void;
}) {
  const Icon = VARIANT_ICON[toast.variant];

  useEffect(() => {
    const timer = window.setTimeout(() => {
      onDismiss(toast.id);
    }, TOAST_DISPLAY_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [toast.id, onDismiss]);

  return (
    <div
      role={toast.variant === 'error' ? 'alert' : 'status'}
      className={cn(
        'bg-surface-overlay border-border-default shadow-overlay flex items-start gap-3',
        'rounded-container border p-3',
        toast.variant === 'error' && 'border-l-text-critical border-l-4',
      )}
    >
      <Icon
        className={cn('mt-0.5 size-4 shrink-0', VARIANT_ICON_CLASS_NAME[toast.variant])}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p className="text-body-emphasis text-text-primary">{toast.title}</p>
        {toast.description !== undefined && (
          <p className="text-caption text-text-secondary mt-0.5">{toast.description}</p>
        )}
      </div>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={() => {
          onDismiss(toast.id);
        }}
        className={cn(
          'rounded-interactive text-text-tertiary hover:bg-surface-disabled hover:text-text-primary shrink-0 p-1',
          'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
        )}
      >
        <X className="size-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}
