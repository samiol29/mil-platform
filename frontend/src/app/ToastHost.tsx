/**
 * ToastHost (Product Experience phase, Phase 0) — mounts the props-driven
 * `ToastViewport` shell (`design-system/components/Toast`) globally and
 * wires it to the shared `useUiStore` toast queue, the same separation
 * `CommandPaletteHost` keeps for the Command Palette shell: the
 * design-system component knows nothing about the app's state management,
 * only this host does.
 */

import { useUiStore } from '@app/uiStore';
import { ToastViewport } from '@design-system/components/Toast';

export function ToastHost() {
  const toasts = useUiStore((state) => state.toasts);
  const dismissToast = useUiStore((state) => state.dismissToast);

  return <ToastViewport toasts={toasts} onDismiss={dismissToast} />;
}
