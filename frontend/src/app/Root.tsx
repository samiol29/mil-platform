/**
 * Bootstrap entry point for `/` (spec 002's stated MVP entry path: the
 * Application Workspace is "reachable via a direct link" — the full
 * Application Queue is User Story 2, tasks.md T079, not built here).
 *
 * This was previously a static placeholder (`<h1>MIL — Underwriter
 * Workspace</h1>`) that fetched nothing — the actual root cause of an
 * earlier reported "blank main content" bug (authentication was never
 * broken; this route just never rendered anything else). It now redirects
 * to the first available application's Workspace so `/` is a real,
 * working entry point rather than a dead end, without building queue UI
 * (search/filter/sort/pagination) ahead of User Story 2.
 */
import { Navigate } from '@tanstack/react-router';

import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { useApplications } from '@entities/application/queries';

export function Root() {
  const applicationsQuery = useApplications();

  if (applicationsQuery.isPending) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <LoadingState label="Loading applications…" />
      </div>
    );
  }

  if (applicationsQuery.isError) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <ErrorState
          title="Could not load applications"
          onRetry={() => {
            void applicationsQuery.refetch();
          }}
        />
      </div>
    );
  }

  if (applicationsQuery.data.items.length === 0) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <EmptyState
          title="No applications yet"
          description="Applications created in the Loan Origination System will appear here."
        />
      </div>
    );
  }

  return (
    <Navigate
      to="/applications/$applicationId"
      params={{ applicationId: applicationsQuery.data.items[0].id }}
      search={{ region: 'overview' }}
      replace
    />
  );
}
