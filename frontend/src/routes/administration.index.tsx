/**
 * Enterprise Administration route (spec 005-enterprise-platform §15, Wave 1)
 * — `/administration`. ADMIN-only, gated by `navConfig.ts`'s `roles` filter
 * in `PrimaryNav`; the route itself has no separate guard beyond the API's
 * own RBAC enforcement (matches the existing pattern — no route-level auth
 * guard exists anywhere else in this app either; the backend is the actual
 * enforcement boundary).
 */

import { createFileRoute } from '@tanstack/react-router';

import { PageContainer } from '@design-system/components/PageContainer';
import { RetentionPolicyPanel } from '@features/administration/RetentionPolicyPanel';
import { UserManagementTable } from '@features/administration/UserManagementTable';

export const Route = createFileRoute('/administration/')({
  component: AdministrationRoute,
});

function AdministrationRoute() {
  return (
    <PageContainer variant="dense" className="gap-8">
      <h1 className="text-display">Administration</h1>
      <UserManagementTable />
      <RetentionPolicyPanel />
    </PageContainer>
  );
}
