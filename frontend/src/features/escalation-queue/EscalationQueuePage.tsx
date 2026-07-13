/**
 * Escalation Queue (final product polish sprint, A5).
 *
 * A Risk Analyst, Compliance Officer, or Underwriter previously had no way
 * to see "everything escalated to me" in one place — an escalated finding
 * was only discoverable by opening the specific application it belonged to
 * (via a notification, or by chance). This page is a thin, read-only triage
 * view over `GET /v1/findings/escalated` (which reuses the exact same
 * `ReviewService.get_escalated_for_caller` query the Application Queue's
 * "Escalated" filter chip uses — one real capability, two surfaces).
 *
 * Deliberately not a second review surface: there is no Verify/Override/
 * Escalate action here, no evidence chips — resolving a finding still
 * happens in the Application Workspace, unmodified. Each row is a link
 * there. Each row resolves its own application's loan/LOS reference via the
 * existing single-application `useApplication` hook (no bulk "applications
 * by id" endpoint exists, and escalations are expected to be a short list,
 * not a paginated volume — the existing per-application fetch is the
 * honest, already-built tool for this, not new query infrastructure).
 */

import { Link } from '@tanstack/react-router';

import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import { useApplication } from '@entities/application/queries';
import type { Finding } from '@entities/finding/queries';
import { useEscalatedFindings } from '@entities/finding/queries';

function EscalatedFindingRow({ finding }: { readonly finding: Finding }) {
  const applicationQuery = useApplication(finding.applicationId);
  const application = applicationQuery.data;
  const reference =
    application?.loanNumber ?? application?.losReference ?? finding.applicationId;

  return (
    <li className="bg-surface-raised shadow-raised rounded-container animate-panel-in flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <Link
          to="/applications/$applicationId"
          params={{ applicationId: finding.applicationId }}
          search={{ region: 'findings' }}
          className="text-body-emphasis text-text-primary hover:text-interactive-primary-default underline-offset-2 transition-colors duration-micro ease-standard hover:underline"
        >
          {reference}
        </Link>
        <span className="text-caption bg-surface-secondary text-text-secondary rounded-chip px-2 py-0.5">
          {finding.escalatedToUserId !== null
            ? 'Escalated to you'
            : `Escalated to ${finding.escalatedToRole ?? 'another role'}`}
        </span>
      </div>
      <p className="text-body text-text-primary">{finding.what}</p>
      <p className="text-caption text-text-secondary">{finding.why}</p>
    </li>
  );
}

export function EscalationQueuePage() {
  const findingsQuery = useEscalatedFindings();

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4 p-6">
      <div>
        <h1 className="text-heading-page text-text-primary">Escalation Queue</h1>
        <p className="text-caption text-text-secondary">
          Findings currently escalated to your role, or to you specifically.
        </p>
      </div>

      {findingsQuery.isPending && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      )}

      {findingsQuery.isError && (
        <ErrorState
          title="Could not load the escalation queue"
          onRetry={() => {
            void findingsQuery.refetch();
          }}
        />
      )}

      {findingsQuery.isSuccess && findingsQuery.data.length === 0 && (
        <EmptyState
          title="Nothing escalated to you right now"
          description="Findings escalated to your role, or to you specifically, will appear here."
        />
      )}

      {findingsQuery.isSuccess && findingsQuery.data.length > 0 && (
        <ul className="flex flex-col gap-3">
          {findingsQuery.data.map((finding) => (
            <EscalatedFindingRow key={finding.id} finding={finding} />
          ))}
        </ul>
      )}
    </div>
  );
}
