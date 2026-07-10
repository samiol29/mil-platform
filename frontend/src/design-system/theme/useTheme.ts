import { useContext } from 'react';

import { ThemeContext, type ThemeContextValue } from './ThemeContext';

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error('useTheme() must be called within a <ThemeProvider>.');
  }
  return context;
}
