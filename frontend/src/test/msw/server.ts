/**
 * MSW Node server (spec 002 tasks.md T044) — wired into `src/test/setup.ts`
 * so every Vitest unit/component test runs against these contract-shaped
 * handlers rather than a real network call.
 */

import { setupServer } from 'msw/node';

import { handlers } from './handlers';

export const server = setupServer(...handlers);
