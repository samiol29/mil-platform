/**
 * Business Analytics route (spec 005-enterprise-platform §11, Wave 3) —
 * `/business-analytics`. Gated by `navConfig.ts`'s `roles` filter
 * (`ADMIN`, `OPERATIONS_MANAGER`, `COMPLIANCE_OFFICER`); the backend's own
 * RBAC (`read:analytics`) is the real enforcement boundary.
 */

import { createFileRoute } from '@tanstack/react-router';

import { BusinessAnalyticsPage } from '@features/business-analytics/BusinessAnalyticsPage';

export const Route = createFileRoute('/business-analytics/')({
  component: BusinessAnalyticsRoute,
});

function BusinessAnalyticsRoute() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-display">Business Analytics</h1>
      <BusinessAnalyticsPage />
    </div>
  );
}
