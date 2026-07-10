/**
 * MSW browser worker (spec 002 tasks.md T044) — lets the frontend run
 * standalone against contract-shaped mocks with no backend running at all
 * (parallel frontend/backend delivery, per plan.md's Risks & Mitigations).
 * Started conditionally from `main.tsx` behind `VITE_USE_MSW=true`; normal
 * local development (against the real API via the Vite dev proxy) never
 * imports this module, so it has zero effect unless explicitly opted into.
 */

import { setupWorker } from 'msw/browser';

import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
