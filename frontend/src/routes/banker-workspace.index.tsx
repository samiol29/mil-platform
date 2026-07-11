/**
 * RM / Banker Workspace route (spec 005-enterprise-platform §1, Wave 2) —
 * `/banker-workspace`. Gated by `navConfig.ts`'s `roles` filter
 * (`RELATIONSHIP_MANAGER`, `ADMIN`); the backend's own RBAC
 * (`manage:assignment`) is the real enforcement boundary.
 */

import { createFileRoute } from '@tanstack/react-router';

import { BankerWorkspacePage } from '@features/banker-workspace/BankerWorkspacePage';

export const Route = createFileRoute('/banker-workspace/')({
  component: BankerWorkspaceRoute,
});

function BankerWorkspaceRoute() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-display">Banker Workspace</h1>
      <BankerWorkspacePage />
    </div>
  );
}
