import type { Preview } from '@storybook/react-vite';

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
};

export default preview;
