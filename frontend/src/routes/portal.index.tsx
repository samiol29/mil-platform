/**
 * Customer Portal main route (spec 005-enterprise-platform §12, Wave 4) —
 * `/portal`. Redirects to activation if no portal session exists yet.
 */

import { createFileRoute } from '@tanstack/react-router';

import { portalAuthStore } from '@app/auth/portalAuthStore';
import { EmptyState } from '@design-system/components/EmptyState';
import { PortalChecklistPage } from '@features/customer-portal/PortalChecklistPage';

export const Route = createFileRoute('/portal/')({
  component: PortalRoute,
});

function PortalRoute() {
  const isAuthenticated = portalAuthStore.isAuthenticated();

  if (!isAuthenticated) {
    return (
      <div className="mx-auto max-w-md px-6 py-16">
        <EmptyState
          title="Session not found"
          description="Please use the invitation link your loan officer sent you to access your portal."
        />
      </div>
    );
  }
  return <PortalChecklistPage />;
}
