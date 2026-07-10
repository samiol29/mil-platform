/**
 * Ephemeral UI state store (spec 002 tasks.md T038; plan.md State Management).
 *
 * Zustand, for exactly the state plan.md's State Management section scopes
 * to it: command palette open/closed + its query, transient panel
 * expand/collapse, a requested finding-action-dialog open, and (Product
 * Experience phase, Phase 0) a transient toast queue — never an entity from
 * `data-model.md`. If it came from the server, TanStack Query owns it; this
 * store must never become a shadow cache for server data (plan.md: "a
 * concrete rule preventing drift").
 */

import { create } from 'zustand';

export type FindingActionKind = 'verify' | 'override' | 'escalate';

export interface RequestedFindingAction {
  readonly findingId: string;
  readonly action: FindingActionKind;
}

export type ToastVariant = 'success' | 'error' | 'info';

export interface ToastInput {
  readonly title: string;
  readonly description?: string;
  readonly variant?: ToastVariant;
}

export interface Toast extends ToastInput {
  readonly id: string;
  readonly variant: ToastVariant;
}

interface UiState {
  readonly commandPaletteOpen: boolean;
  readonly commandPaletteQuery: string;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  setCommandPaletteQuery: (query: string) => void;

  readonly expandedPanels: ReadonlySet<string>;
  togglePanel: (panelId: string) => void;
  isPanelExpanded: (panelId: string) => boolean;

  /**
   * Set by the Command Palette when a finding-action command is chosen
   * (UX audit §5) — consumed by that finding's own `FindingActions`
   * instance, which opens the exact same confirm-dialog a manual click on
   * its Verify/Override/Escalate button would, then clears the request.
   * This never performs the mutation itself: the palette only triggers the
   * same mandatory second-confirmation-step UI that already exists
   * (FR-078), it does not bypass it.
   */
  readonly requestedFindingAction: RequestedFindingAction | null;
  requestFindingAction: (request: RequestedFindingAction) => void;
  clearRequestedFindingAction: () => void;

  readonly toasts: readonly Toast[];
  addToast: (toast: ToastInput) => string;
  dismissToast: (id: string) => void;

  /**
   * Whether the application-intake wizard (Product Experience phase, Phase 2)
   * is open. Reachable from the Dashboard, the Queue header, and the Command
   * Palette — three places with no shared parent — so one global flag +
   * a single `IntakeWizard` instance mounted in `routes/__root.tsx` avoids
   * duplicating the Drawer (which only supports one open instance at a time
   * by composition convention) or prop-drilling an open/close callback.
   */
  readonly intakeWizardOpen: boolean;
  openIntakeWizard: () => void;
  closeIntakeWizard: () => void;
}

export const useUiStore = create<UiState>((set, get) => ({
  commandPaletteOpen: false,
  commandPaletteQuery: '',
  openCommandPalette: () => {
    set({ commandPaletteOpen: true });
  },
  closeCommandPalette: () => {
    set({ commandPaletteOpen: false, commandPaletteQuery: '' });
  },
  setCommandPaletteQuery: (query) => {
    set({ commandPaletteQuery: query });
  },

  expandedPanels: new Set(),
  togglePanel: (panelId) => {
    const next = new Set(get().expandedPanels);
    if (next.has(panelId)) {
      next.delete(panelId);
    } else {
      next.add(panelId);
    }
    set({ expandedPanels: next });
  },
  isPanelExpanded: (panelId) => get().expandedPanels.has(panelId),

  requestedFindingAction: null,
  requestFindingAction: (request) => {
    set({ requestedFindingAction: request });
  },
  clearRequestedFindingAction: () => {
    set({ requestedFindingAction: null });
  },

  toasts: [],
  addToast: (toast) => {
    const id = crypto.randomUUID();
    set({ toasts: [...get().toasts, { id, variant: toast.variant ?? 'info', ...toast }] });
    return id;
  },
  dismissToast: (id) => {
    set({ toasts: get().toasts.filter((toast) => toast.id !== id) });
  },

  intakeWizardOpen: false,
  openIntakeWizard: () => {
    set({ intakeWizardOpen: true });
  },
  closeIntakeWizard: () => {
    set({ intakeWizardOpen: false });
  },
}));
