/**
 * Index route (`/`). Delegates to `Root`, which redirects to the first
 * available application's Workspace — a real entry point (spec 002's
 * stated MVP path), not the Application Queue (User Story 2, tasks.md
 * T079), which will eventually replace this redirect as the default
 * destination.
 */

import { createFileRoute } from '@tanstack/react-router';

import { Root } from '@app/Root';

export const Route = createFileRoute('/')({
  component: Root,
});
