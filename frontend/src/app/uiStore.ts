/**
 * Ephemeral UI state store (spec 002 tasks.md T038; plan.md State Management).
 *
 * Zustand, for exactly the state plan.md's State Management section scopes
 * to it: command palette open/closed + its query, and transient panel
 * expand/collapse — never an entity from `data-model.md`. If it came from
 * the server, TanStack Query owns it; this store must never become a
 * shadow cache for server data (plan.md: "a concrete rule preventing
 * drift").
 */

import { create } from 'zustand';

interface UiState {
  readonly commandPaletteOpen: boolean;
  readonly commandPaletteQuery: string;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  setCommandPaletteQuery: (query: string) => void;

  readonly expandedPanels: ReadonlySet<string>;
  togglePanel: (panelId: string) => void;
  isPanelExpanded: (panelId: string) => boolean;
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
}));
