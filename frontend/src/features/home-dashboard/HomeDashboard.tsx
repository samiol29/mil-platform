/**
 * Home Dashboard (Product Experience phase, Phase 1; recomposed as a
 * command center in Phase 11) — the real landing experience at `/`,
 * replacing the previous bootstrap redirect (`app/Root.tsx`'s old "jump to
 * whichever application the API returns first" stopgap). Answers "what
 * needs my attention today" before "here's a table" — the Application
 * Queue (`/applications`) remains the detailed operational view.
 *
 * Every number on this screen is derived client-side from the same
 * `useApplicationSearch` fetch `entities/application/queries.ts` already
 * exposes — no new endpoint, no aggregate the backend doesn't compute.
 * The Phase 11 recomposition replaces three equally weighted metric cards
 * with one hairline-divided stat row (display-size numbers, quiet labels —
 * big type reserved for the few numbers that matter) and reframes
 * "Continue working" as **"Needs attention"**: the same real open-
 * applications list, reordered by urgency (IN_REVIEW oldest-first — the
 * ones a decision is actually waiting on — then SUBMITTED, then DRAFT).
 * "Oldest in review" is a real derived age from `createdAt`, the honest
 * urgency signal this data supports; no risk scores or priorities are
 * fabricated.
 *
 * "New Application" opens the global intake wizard (Product Experience
 * phase, Phase 2, `features/application-intake/IntakeWizard.tsx`) via
 * `uiStore`'s `openIntakeWizard` — the same trigger the Queue header and
 * Command Palette use.
 */

import { useNavigate } from '@tanstack/react-router';
import { ArrowRight, FolderKanban, Plus } from 'lucide-react';
import { Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { useAuthUser } from '@app/auth/authProvider';
import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import { PageContainer } from '@design-system/components/PageContainer';
import { cn } from '@design-system/lib/cn';
import { useApplicationSearch } from '@entities/application/queries';
import {
  APPLICATION_STATUS_CHIP_BASE_CLASS,
  APPLICATION_STATUS_CHIP_CLASS_NAME,
  APPLICATION_STATUS_LABEL,
} from '@entities/application/statusLabel';
import type { Application, ApplicationStatus } from '@entities/application/types';

const NEEDS_ATTENTION_LIMIT = 6;

/** Urgency order for "Needs attention": decisions waiting on a human first. */
const ATTENTION_ORDER: readonly ApplicationStatus[] = ['IN_REVIEW', 'SUBMITTED', 'DRAFT'];

/** Same per-status color vocabulary as the Business Analytics status chart — one palette, not two. */
const STATUS_CHART_COLOR: Record<ApplicationStatus, string> = {
  DRAFT: 'var(--text-tertiary)',
  SUBMITTED: 'var(--interactive-primary-default)',
  IN_REVIEW: 'var(--feedback-warning-fg)',
  REVIEW_COMPLETE: 'var(--feedback-success-fg)',
  WITHDRAWN: 'var(--text-disabled)',
};

const TOOLTIP_CONTENT_STYLE = {
  background: 'var(--surface-overlay)',
  border: '1px solid var(--border-default)',
  borderRadius: 8,
  fontSize: 12,
};

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

const DAY_MS = 24 * 60 * 60 * 1000;

function ageInDays(iso: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / DAY_MS));
}

function formatAge(days: number): string {
  if (days === 0) return 'today';
  return `${String(days)}d`;
}

function formatAgeRow(days: number): string {
  if (days === 0) return 'today';
  return `${String(days)}d old`;
}

export function HomeDashboard() {
  const user = useAuthUser();
  const navigate = useNavigate();
  const openIntakeWizard = useUiStore((state) => state.openIntakeWizard);
  const applicationsQuery = useApplicationSearch();

  return (
    <PageContainer variant="dense" className="gap-8">
      <div className="flex items-center justify-between">
        <h1 className="text-heading-page text-text-primary">
          {greeting()}
          {user !== null ? `, ${user.displayName}` : ''}
        </h1>
        <div className="flex items-center gap-2">
          <Button variant="primary" onClick={openIntakeWizard}>
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
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
    </PageContainer>
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

  const inReview = applications.filter((app) => app.status === 'IN_REVIEW');
  const oldestInReviewDays =
    inReview.length > 0 ? Math.max(...inReview.map((app) => ageInDays(app.createdAt))) : null;

  // Urgency ordering: within IN_REVIEW oldest-first (a decision is actually
  // waiting), then SUBMITTED, then DRAFT — each group oldest-first.
  const needsAttention = applications
    .filter((app) => ATTENTION_ORDER.includes(app.status))
    .slice()
    .sort((a, b) => {
      const statusDelta = ATTENTION_ORDER.indexOf(a.status) - ATTENTION_ORDER.indexOf(b.status);
      if (statusDelta !== 0) return statusDelta;
      return a.createdAt < b.createdAt ? -1 : 1;
    })
    .slice(0, NEEDS_ATTENTION_LIMIT);

  return (
    <>
      <section
        aria-label="Today's workload"
        className="bg-surface-raised shadow-raised rounded-container grid grid-cols-2 sm:grid-cols-4 sm:divide-x divide-border-subtle"
      >
        <StatBlock
          label="In review"
          value={countByStatus('IN_REVIEW')}
          onClick={() => {
            void navigate({ to: '/applications', search: { status: 'IN_REVIEW' } });
          }}
        />
        <StatBlock
          label="Submitted"
          value={countByStatus('SUBMITTED')}
          onClick={() => {
            void navigate({ to: '/applications', search: { status: 'SUBMITTED' } });
          }}
        />
        <StatBlock
          label="Draft"
          value={countByStatus('DRAFT')}
          onClick={() => {
            void navigate({ to: '/applications', search: { status: 'DRAFT' } });
          }}
        />
        <StatBlock
          label="Oldest in review"
          value={oldestInReviewDays !== null ? formatAge(oldestInReviewDays) : '—'}
          onClick={() => {
            void navigate({ to: '/applications', search: { status: 'IN_REVIEW' } });
          }}
        />
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section aria-label="Needs attention" className="flex flex-col gap-3 lg:col-span-2">
          <h2 className="text-heading-section text-text-primary">Needs attention</h2>
          {needsAttention.length === 0 ? (
            <EmptyState
              title="Nothing in progress"
              description="Open applications will show up here as you work them."
            />
          ) : (
            <ul className="bg-surface-raised shadow-raised divide-border-subtle divide-y rounded-container">
              {needsAttention.map((app) => (
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
                      'flex w-full items-center gap-4 px-4 py-3 text-left',
                      'hover:bg-surface-secondary transition-colors duration-micro ease-standard',
                      'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:-outline-offset-2',
                    )}
                  >
                    <span className="text-body-emphasis text-text-primary min-w-0 flex-1 truncate">
                      {app.loanNumber ?? app.losReference ?? app.id}
                    </span>
                    <span className="text-caption text-text-tertiary shrink-0">
                      {app.partyCount} {app.partyCount === 1 ? 'party' : 'parties'}
                    </span>
                    <span
                      className={cn(
                        APPLICATION_STATUS_CHIP_BASE_CLASS,
                        APPLICATION_STATUS_CHIP_CLASS_NAME[app.status],
                        'shrink-0',
                      )}
                    >
                      {APPLICATION_STATUS_LABEL[app.status]}
                    </span>
                    <span className="text-caption text-text-tertiary w-16 shrink-0 text-right tabular-nums">
                      {formatAgeRow(ageInDays(app.createdAt))}
                    </span>
                    <ArrowRight className="text-text-tertiary size-4 shrink-0" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <PortfolioCompositionCard applications={applications} />
      </div>
    </>
  );
}

const PORTFOLIO_STATUS_ORDER: readonly ApplicationStatus[] = [
  'DRAFT',
  'SUBMITTED',
  'IN_REVIEW',
  'REVIEW_COMPLETE',
  'WITHDRAWN',
];

/**
 * A real-data donut over the entire visible portfolio's status mix — not
 * just the three "needs attention" statuses the list above narrows to.
 * Same data this page already fetches (`useApplicationSearch`), no new
 * endpoint; same per-status color vocabulary as Business Analytics' status
 * chart, so a reviewer sees one consistent status palette everywhere.
 */
function PortfolioCompositionCard({
  applications,
}: {
  readonly applications: readonly Application[];
}) {
  const data = PORTFOLIO_STATUS_ORDER.map((status) => ({
    name: APPLICATION_STATUS_LABEL[status],
    value: applications.filter((app) => app.status === status).length,
    fill: STATUS_CHART_COLOR[status],
  })).filter((entry) => entry.value > 0);

  return (
    <section
      aria-label="Portfolio composition"
      className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-3 p-5"
    >
      <h2 className="text-heading-section text-text-primary">Portfolio composition</h2>
      {data.length === 0 ? (
        <p className="text-caption text-text-tertiary">No applications yet.</p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={44}
                outerRadius={68}
                paddingAngle={data.length > 1 ? 2 : 0}
                strokeWidth={0}
              />
              <Tooltip contentStyle={TOOLTIP_CONTENT_STYLE} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="flex flex-col gap-1.5">
            {data.map((entry) => (
              <li key={entry.name} className="flex items-center gap-2 text-caption">
                <span
                  aria-hidden="true"
                  className="size-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: entry.fill }}
                />
                <span className="text-text-secondary min-w-0 flex-1 truncate">{entry.name}</span>
                <span className="text-text-primary font-medium tabular-nums">{entry.value}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

interface StatBlockProps {
  readonly label: string;
  readonly value: number | string;
  readonly onClick: () => void;
}

/** One stat in the command-center row: quiet uppercase label, display-size number. */
function StatBlock({ label, value, onClick }: StatBlockProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex flex-col gap-1 p-5 text-left',
        'hover:bg-surface-secondary transition-colors duration-micro ease-standard',
        'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:-outline-offset-2',
      )}
    >
      <span className="text-caption text-text-tertiary tracking-wide uppercase">{label}</span>
      <span className="text-display text-text-primary tabular-nums">{value}</span>
    </button>
  );
}
