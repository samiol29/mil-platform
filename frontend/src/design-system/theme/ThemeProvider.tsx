/**
 * ThemeProvider (spec 003 FR-028–031, T020).
 *
 * Resolves which of the two independently-designed themes (light/dark) is
 * active by setting `data-theme` on the document root — the attribute every
 * token in `tokens.css` and every `dark:` Tailwind variant (see
 * `theme/globals.css`'s `@custom-variant dark`) reads from. Switching themes
 * is therefore a single attribute write with no re-render of the token
 * layer and no page reload (FR-030).
 *
 * Default and persistence (FR-030): a first-time user gets the OS
 * `prefers-color-scheme` preference; once a user explicitly chooses a theme,
 * that choice is persisted in `localStorage` (a non-sensitive UI preference,
 * per plan.md's Storage policy) and takes precedence over the OS preference
 * on every subsequent visit.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { THEME_STORAGE_KEY, ThemeContext, resolveInitialTheme, type Theme } from './ThemeContext';

export interface ThemeProviderProps {
  readonly children: ReactNode;
  /** Test/Storybook override — bypasses localStorage/system detection. */
  readonly initialTheme?: Theme;
}

export function ThemeProvider({ children, initialTheme }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(() => initialTheme ?? resolveInitialTheme());

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    window.localStorage.setItem(THEME_STORAGE_KEY, next);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  }, [theme, setTheme]);

  const value = useMemo(() => ({ theme, setTheme, toggleTheme }), [theme, setTheme, toggleTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
