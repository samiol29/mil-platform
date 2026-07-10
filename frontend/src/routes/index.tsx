/**
 * Index route (`/`). Delegates to `Root`, the Home Dashboard (Product
 * Experience phase, Phase 1) — the real landing experience, replacing the
 * previous bootstrap redirect to the first application the API returned.
 */

import { createFileRoute } from '@tanstack/react-router';

import { Root } from '@app/Root';

export const Route = createFileRoute('/')({
  component: Root,
});
