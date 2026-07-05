/**
 * Theme context, type, and persistence helpers — split from `ThemeProvider.tsx`
 * so that file exports only the `ThemeProvider` component (react-refresh
 * requires component-only files for fast refresh to work).
 */

import { createContext } from 'react';

export type Theme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'mil-theme';

export interface ThemeContextValue {
  readonly theme: Theme;
  readonly setTheme: (theme: Theme) => void;
  readonly toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function readStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null;
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : null;
}

export function readSystemTheme(): Theme {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function resolveInitialTheme(): Theme {
  return readStoredTheme() ?? readSystemTheme();
}
