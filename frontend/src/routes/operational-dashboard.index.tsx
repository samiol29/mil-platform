/**
 * Operational Dashboard route (spec 005-enterprise-platform §10, Wave 3) —
 * `/operational-dashboard`. Gated by `navConfig.ts`'s `roles` filter
 * (`ADMIN`, `OPERATIONS_MANAGER`); the backend's own RBAC
 * (`read:operational`) is the real enforcement boundary.
 */

import { createFileRoute } from '@tanstack/react-router';

import { OperationalDashboardPage } from '@features/operational-dashboard/OperationalDashboardPage';

export const Route = createFileRoute('/operational-dashboard/')({
  component: OperationalDashboardRoute,
});

function OperationalDashboardRoute() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-display">Operational Dashboard</h1>
      <OperationalDashboardPage />
    </div>
  );
}
