/**
 * Policy Administration route (spec 005-enterprise-platform §4, Wave 1) —
 * `/policy-administration`. Gated by `navConfig.ts`'s `roles` filter
 * (`POLICY_ADMINISTRATOR`, `COMPLIANCE_OFFICER`, `ADMIN`) in `PrimaryNav`;
 * the backend's own RBAC (`DRAFT_POLICY_PACK`/`MANAGE_POLICY_PACKS`) is the
 * real enforcement boundary, matching every other route in this app.
 */

import { createFileRoute } from '@tanstack/react-router';

import { PageContainer } from '@design-system/components/PageContainer';
import { PolicyAdministrationPage } from '@features/policy-administration/PolicyAdministrationPage';

export const Route = createFileRoute('/policy-administration/')({
  component: PolicyAdministrationRoute,
});

function PolicyAdministrationRoute() {
  return (
    <PageContainer variant="dense">
      <h1 className="text-display">Policy Administration</h1>
      <PolicyAdministrationPage />
    </PageContainer>
  );
}
