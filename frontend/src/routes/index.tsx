/**
 * Index route (`/`). Temporary placeholder rendering the existing `Root`
 * component (Phase 1) until User Story 2 (tasks.md T079) wires the real
 * Application Queue as the default destination — not a redesign of
 * completed work, just where the router's index route delegates for now.
 */

import { createFileRoute } from '@tanstack/react-router';

import { Root } from '@app/Root';

export const Route = createFileRoute('/')({
  component: Root,
});
