import tailwindcss from '@tailwindcss/vite';
import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  stories: ['../src/**/*.mdx', '../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  addons: [
    '@chromatic-com/storybook',
    '@storybook/addon-vitest',
    '@storybook/addon-a11y',
    '@storybook/addon-docs',
  ],
  framework: '@storybook/react-vite',
  // Storybook's own Vite instance does not automatically pick up the
  // project's vite.config.ts plugins — the Tailwind v4 plugin (required to
  // process `@import 'tailwindcss'` in globals.css) is added explicitly here
  // so Storybook renders every component with real design-system styling,
  // not unstyled markup.
  viteFinal(viteConfig) {
    viteConfig.plugins ??= [];
    viteConfig.plugins.push(tailwindcss());
    return viteConfig;
  },
};

export default config;
