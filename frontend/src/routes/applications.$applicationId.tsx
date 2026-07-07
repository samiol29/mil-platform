/**
 * Application Workspace route (spec 002 tasks.md T069) — the deep-linkable
 * destination User Story 1 requires (direct deep link, bypassing the
 * queue). The active region is URL search-param state (`?region=`), per
 * plan.md's Routing Strategy ("the active tab within the Application
 * Workspace... is URL state") — region switching is a URL change handled
 * by the router, never a full page reload.
 */

import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';

import { isReadOnlyUser, useAuthUser } from '@app/auth/authProvider';
import { ApplicationWorkspace } from '@features/application-workspace/ApplicationWorkspace';
import { WORKSPACE_REGIONS, type WorkspaceRegion } from '@features/application-workspace/regions';

const searchSchema = z.object({
  region: z.enum(WORKSPACE_REGIONS).catch('overview'),
});

export const Route = createFileRoute('/applications/$applicationId')({
  validateSearch: searchSchema,
  component: ApplicationWorkspaceRoute,
});

function ApplicationWorkspaceRoute() {
  const { applicationId } = Route.useParams();
  const { region } = Route.useSearch();
  const navigate = Route.useNavigate();
  const user = useAuthUser();

  const setRegion = (next: WorkspaceRegion) => {
    void navigate({ search: { region: next } });
  };

  return (
    <ApplicationWorkspace
      applicationId={applicationId}
      region={region}
      onRegionChange={setRegion}
      readOnly={user !== null && isReadOnlyUser(user.roles)}
    />
  );
}
