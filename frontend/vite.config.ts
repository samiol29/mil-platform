/// <reference types="vitest/config" />
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
import { playwright } from '@vitest/browser-playwright';
import { tanstackRouter } from '@tanstack/router-plugin/vite';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const dirname =
  typeof __dirname !== 'undefined' ? __dirname : path.dirname(fileURLToPath(import.meta.url));

// Path aliases mirror tsconfig.app.json's "paths" exactly (plan.md Project Structure) —
// keep both in sync; a mismatch here silently breaks module resolution at build time
// even though the type checker still passes.
const aliases = {
  '@app': path.resolve(dirname, 'src/app'),
  '@design-system': path.resolve(dirname, 'src/design-system'),
  '@entities': path.resolve(dirname, 'src/entities'),
  '@features': path.resolve(dirname, 'src/features'),
  '@routes': path.resolve(dirname, 'src/routes'),
  '@shared': path.resolve(dirname, 'src/shared'),
};

export default defineConfig({
  plugins: [
    // Must run before @vitejs/plugin-react (TanStack Router docs) — generates
    // src/routeTree.gen.ts from the file-based route tree under src/routes/.
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: aliases,
  },
  server: {
    // Same-origin dev proxy to the local API (plan.md Deployment Strategy) — the
    // frontend and API share an origin in every environment, dev included, so the
    // httpOnly refresh-cookie auth flow never has to deal with cross-origin
    // cookie/CORS semantics, even locally.
    proxy: {
      '/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'unit',
          environment: 'jsdom',
          globals: true,
          setupFiles: ['./src/test/setup.ts'],
          include: ['src/**/*.test.{ts,tsx}'],
        },
      },
      {
        extends: true,
        plugins: [
          // Runs Storybook's own stories as Vitest tests, including the a11y
          // addon's assertions (preview.tsx sets a11y.test: 'error') — this is
          // the mechanism that makes "every component's a11y check is a CI gate"
          // true in practice, not just in the plan.
          storybookTest({
            configDir: path.join(dirname, '.storybook'),
          }),
        ],
        test: {
          name: 'storybook',
          browser: {
            enabled: true,
            headless: true,
            provider: playwright({}),
            instances: [{ browser: 'chromium' }],
          },
        },
      },
    ],
  },
});
