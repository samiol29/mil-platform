/**
 * Business Analytics route (spec 005-enterprise-platform §11, Wave 3) —
 * `/business-analytics`. Gated by `navConfig.ts`'s `roles` filter
 * (`ADMIN`, `OPERATIONS_MANAGER`, `COMPLIANCE_OFFICER`); the backend's own
 * RBAC (`read:analytics`) is the real enforcement boundary.
 */

import { createFileRoute } from '@tanstack/react-router';

import { PageContainer } from '@design-system/components/PageContainer';
import { BusinessAnalyticsPage } from '@features/business-analytics/BusinessAnalyticsPage';

export const Route = createFileRoute('/business-analytics/')({
  component: BusinessAnalyticsRoute,
});

function BusinessAnalyticsRoute() {
  return (
    <PageContainer variant="dense">
      <h1 className="text-display">Business Analytics</h1>
      <BusinessAnalyticsPage />
    </PageContainer>
  );
}
