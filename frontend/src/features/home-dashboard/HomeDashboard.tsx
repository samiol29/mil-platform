/**
 * Home Dashboard (Product Experience phase, Phase 1) — the real landing
 * experience at `/`, replacing the previous bootstrap redirect
 * (`app/Root.tsx`'s old "jump to whichever application the API returns
 * first" stopgap). Answers "what needs my attention today" before "here's
 * a table" — the Application Queue (`/applications`) remains the detailed
 * operational view for when the underwriter already knows they want the
 * full list.
 *
 * Every count on this screen is derived client-side from the same
 * `useApplicationSearch` fetch `entities/application/queries.ts` already
 * exposes — no new endpoint, no aggregate the backend doesn't compute.
 * Real domain statuses only (`DRAFT/SUBMITTED/IN_REVIEW/REVIEW_COMPLETE/
 * WITHDRAWN` — `entities/application/types.ts`), not the aspirational
 * `READY_FOR_DECISION`-style naming an earlier draft of this plan assumed
 * before the actual schema was inspected.
 *
 * "New Application" opens the global intake wizard (Product Experience
 * phase, Phase 2, `features/application-intake/IntakeWizard.tsx`) via
 * `uiStore`'s `openIntakeWizard` — the same trigger the Queue header and
 * Command Palette use.
 */

import { useNavigate } from '@tanstack/react-router';
import { ArrowRight, FolderKanban, Plus } from 'lucide-react';

import { useAuthUser } from '@app/auth/authProvider';
import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import { cn } from '@design-system/lib/cn';
import { useApplicationSearch } from '@entities/application/queries';
import { APPLICATION_STATUS_LABEL } from '@entities/application/statusLabel';
import type { Application, ApplicationStatus } from '@entities/application/types';

const OPEN_STATUSES: readonly ApplicationStatus[] = ['DRAFT', 'SUBMITTED', 'IN_REVIEW'];
const CONTINUE_WORKING_LIMIT = 5;

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export function HomeDashboard() {
  const user = useAuthUser();
  const navigate = useNavigate();
  const openIntakeWizard = useUiStore((state) => state.openIntakeWizard);
  const applicationsQuery = useApplicationSearch();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-heading-page text-text-primary">
          {greeting()}
          {user !== null ? `, ${user.displayName}` : ''}
        </h1>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={openIntakeWizard}>
            <Plus className="size-4" aria-hidden="true" />
            New Application
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              void navigate({ to: '/applications' });
            }}
          >
            <FolderKanban className="size-4" aria-hidden="true" />
            View full queue
          </Button>
        </div>
      </div>

      {applicationsQuery.isPending && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}

      {applicationsQuery.isError && (
        <ErrorState
          title="Could not load your workload"
          onRetry={() => {
            void applicationsQuery.refetch();
          }}
        />
      )}

      {applicationsQuery.isSuccess && (
        <DashboardContent applications={applicationsQuery.data.items} />
      )}
    </div>
  );
}

function DashboardContent({ applications }: { readonly applications: readonly Application[] }) {
  const navigate = useNavigate();

  if (applications.length === 0) {
    return (
      <EmptyState
        title="No applications yet"
        description="Applications created in the Loan Origination System will appear here."
      />
    );
  }

  const countByStatus = (status: ApplicationStatus) =>
    applications.filter((app) => app.status === status).length;

  const continueWorking = applications
    .filter((app) => OPEN_STATUSES.includes(app.status))
    .slice()
    .sort((a, b) => (a.updatedAt ?? a.createdAt) < (b.updatedAt ?? b.createdAt) ? 1 : -1)
    .slice(0, CONTINUE_WORKING_LIMIT);

  return (
    <>
      <section aria-label="Today's workload" className="flex flex-col gap-3">
        <h2 className="text-heading-section text-text-primary">Today's workload</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <WorkloadCard
            label="In Review"
            description="Findings generated, awaiting your decision"
            count={countByStatus('IN_REVIEW')}
            onClick={() => {
              void navigate({ to: '/applications', search: { status: 'IN_REVIEW' } });
            }}
          />
          <WorkloadCard
            label="Submitted"
            description="Awaiting the intelligence pipeline"
            count={countByStatus('SUBMITTED')}
            onClick={() => {
              void navigate({ to: '/applications', search: { status: 'SUBMITTED' } });
            }}
          />
          <WorkloadCard
            label="Draft"
            description="Not yet submitted for review"
            count={countByStatus('DRAFT')}
            onClick={() => {
              void navigate({ to: '/applications', search: { status: 'DRAFT' } });
            }}
          />
        </div>
      </section>

      <section aria-label="Continue working" className="flex flex-col gap-3">
        <h2 className="text-heading-section text-text-primary">Continue working</h2>
        {continueWorking.length === 0 ? (
          <EmptyState
            title="Nothing in progress"
            description="Open applications will show up here as you work them."
          />
        ) : (
          <ul className="border-border-subtle divide-border-subtle divide-y rounded-container border">
            {continueWorking.map((app) => (
              <li key={app.id}>
                <button
                  type="button"
                  onClick={() => {
                    void navigate({
                      to: '/applications/$applicationId',
                      params: { applicationId: app.id },
                      search: { region: 'overview' },
                    });
                  }}
                  className={cn(
                    'flex w-full items-center justify-between gap-4 p-4 text-left',
                    'hover:bg-surface-secondary',
                    'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:-outline-offset-2',
                  )}
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="text-body-emphasis text-text-primary">
                      {app.loanNumber ?? app.losReference ?? app.id}
                    </span>
                    <span className="text-caption text-text-secondary">
                      {APPLICATION_STATUS_LABEL[app.status]}
                    </span>
                  </div>
                  <ArrowRight className="text-text-tertiary size-4 shrink-0" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

interface WorkloadCardProps {
  readonly label: string;
  readonly description: string;
  readonly count: number;
  readonly onClick: () => void;
}

function WorkloadCard({ label, description, count, onClick }: WorkloadCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'border-border-subtle bg-surface-raised rounded-container flex flex-col gap-1 border p-5 text-left',
        'hover:bg-surface-secondary transition-colors duration-micro ease-standard',
        'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
      )}
    >
      <span className="text-caption text-text-secondary">{label}</span>
      <span className="text-heading-section text-text-primary tabular-nums">{count}</span>
      <span className="text-caption text-text-tertiary">{description}</span>
    </button>
  );
}
