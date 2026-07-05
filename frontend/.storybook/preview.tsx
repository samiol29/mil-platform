import type { Decorator, Preview } from '@storybook/react-vite';

import { ThemeProvider } from '@design-system/theme/ThemeProvider';
import '@design-system/theme/globals.css';

// Every component must be independently contrast-audited in BOTH themes
// (plan.md Accessibility Strategy: "a theme is not considered complete until
// its own contrast audit passes, not inferred from the other theme's
// result") — this toolbar lets a reviewer flip themes per-story, and the
// a11y addon re-runs its audit against whichever theme is active.
const withTheme: Decorator = (Story, context) => {
  const theme = context.globals.theme === 'dark' ? 'dark' : 'light';
  return (
    <ThemeProvider initialTheme={theme}>
      <div className="bg-surface-background text-text-primary p-6">
        <Story />
      </div>
    </ThemeProvider>
  );
};

// Accessibility conformance is a hard CI gate, not an aspiration — per the Design
// System specification (003, FR-067) and the implementation plan's Accessibility
// Strategy. `test: 'error'` fails the Storybook test run (and therefore CI) on any
// detected violation; it is never relaxed to 'todo' or 'off'.
const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },

    a11y: {
      test: 'error',
    },
  },

  globalTypes: {
    theme: {
      description: 'Design system theme (spec 003 FR-028)',
      toolbar: {
        icon: 'mirror',
        items: [
          { value: 'light', title: 'Light' },
          { value: 'dark', title: 'Dark' },
        ],
        dynamicTitle: true,
      },
    },
  },

  initialGlobals: {
    theme: 'light',
  },

  decorators: [withTheme],
};

export default preview;
