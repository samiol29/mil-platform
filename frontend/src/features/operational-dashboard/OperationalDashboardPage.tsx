/**
 * Operational Dashboard (spec 005-enterprise-platform §10, Wave 3) — for
 * platform administrators/operations managers. Reuses the existing
 * `GET /v1/metrics` in-process counters (`useMetrics`, if already present)
 * alongside two new real, on-demand aggregates: job queue depth and the
 * application-lifecycle funnel. Everything shown is real, already-persisted
 * data — no fabricated historical trend or time-series (disclosed in the
 * spec's own implementation-correction note for this section).
 */

import { AlertTriangle } from 'lucide-react';

import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import {
  useApplicationFunnel,
  useJobQueueHealth,
  usePoisonJobs,
  useQueueDepth,
} from '@entities/operational/queries';

function StatRow({ items }: { items: readonly { label: string; value: string | number }[] }) {
  return (
    <div className="divide-border-default bg-surface-raised shadow-raised rounded-container flex divide-x">
      {items.map((item) => (
        <div key={item.label} className="flex-1 px-4 py-3">
          <div className="text-display tabular-nums">{item.value}</div>
          <div className="text-caption text-text-tertiary tracking-wide uppercase">
            {item.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function QueueDepthSection() {
  const queueDepthQuery = useQueueDepth();

  if (queueDepthQuery.isPending) return <Skeleton className="h-24 w-full" />;
  if (queueDepthQuery.isError) {
    return (
      <ErrorState
        title="Failed to load queue depth"
        description={
          queueDepthQuery.error instanceof Error ? queueDepthQuery.error.message : 'Unknown error'
        }
        onRetry={() => void queueDepthQuery.refetch()}
      />
    );
  }

  const rows = queueDepthQuery.data.items;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-heading">Job Queue Depth</h2>
      {rows.length === 0 ? (
        <p className="text-caption text-text-tertiary">No active workflow runs.</p>
      ) : (
        <table className="text-body w-full">
          <thead>
            <tr className="text-caption text-text-tertiary border-border-default border-b text-left uppercase">
              <th className="py-1.5 font-normal">Workflow Type</th>
              <th className="py-1.5 font-normal">Status</th>
              <th className="py-1.5 text-right font-normal">Count</th>
            </tr>
          </thead>
          <tbody className="divide-border-default divide-y">
            {rows.map((row) => (
              <tr key={`${row.workflowType}-${row.status}`}>
                <td className="py-1.5">{row.workflowType}</td>
                <td className="py-1.5">{row.status}</td>
                <td className="py-1.5 text-right tabular-nums">{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function PoisonJobsSection() {
  const poisonJobsQuery = usePoisonJobs();

  if (poisonJobsQuery.isPending) return <Skeleton className="h-16 w-full" />;
  if (poisonJobsQuery.isError) {
    return (
      <ErrorState
        title="Failed to load poison jobs"
        description={
          poisonJobsQuery.error instanceof Error ? poisonJobsQuery.error.message : 'Unknown error'
        }
        onRetry={() => void poisonJobsQuery.refetch()}
      />
    );
  }

  const jobs = poisonJobsQuery.data.items;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-heading">Poison Jobs</h2>
      <p className="text-caption text-text-tertiary">
        Workflow steps that exceeded their retry ceiling — these require manual investigation; no
        automatic redelivery exists for a worker crash (a documented platform limitation).
      </p>
      {jobs.length === 0 ? (
        <p className="text-caption text-text-tertiary">No poison jobs detected.</p>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Poison jobs">
          {jobs.map((job) => (
            <li
              key={job.id}
              className="bg-feedback-error-bg border-feedback-error-border flex items-start gap-2 rounded-container border p-3"
            >
              <AlertTriangle
                className="text-feedback-error-fg mt-0.5 size-4 shrink-0"
                aria-hidden="true"
              />
              <div>
                <p className="text-body font-medium">
                  {job.stepName} — {job.retryCount}/{job.maxRetries} retries exhausted
                </p>
                {job.errorMessage !== null && (
                  <p className="text-caption text-text-tertiary">{job.errorMessage}</p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function FunnelSection() {
  const funnelQuery = useApplicationFunnel();

  if (funnelQuery.isPending) return <Skeleton className="h-24 w-full" />;
  if (funnelQuery.isError) {
    return (
      <ErrorState
        title="Failed to load application funnel"
        description={
          funnelQuery.error instanceof Error ? funnelQuery.error.message : 'Unknown error'
        }
        onRetry={() => void funnelQuery.refetch()}
      />
    );
  }

  const rows = funnelQuery.data.items;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-heading">Application Funnel</h2>
      <p className="text-caption text-text-tertiary">
        “Avg. time since updated” approximates dwell time from the application's last update — this
        platform does not track per-status transition history, so it is not exact per-status dwell
        time.
      </p>
      {rows.length === 0 ? (
        <p className="text-caption text-text-tertiary">No applications yet.</p>
      ) : (
        <StatRow
          items={rows.map((row) => ({
            label: row.status,
            value: row.count,
          }))}
        />
      )}
    </section>
  );
}

function JobQueueHealthSection() {
  const healthQuery = useJobQueueHealth();

  if (healthQuery.isPending) return <Skeleton className="h-16 w-full" />;
  if (healthQuery.isError) {
    return (
      <ErrorState
        title="Failed to load job queue health"
        description={
          healthQuery.error instanceof Error ? healthQuery.error.message : 'Unknown error'
        }
        onRetry={() => void healthQuery.refetch()}
      />
    );
  }

  const health = healthQuery.data;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-heading">Job Queue Health</h2>
      <p className="text-caption text-text-tertiary">
        Real, process-wide broker counters (spec 005 §14) — not tenant-scoped. Dead-letter jobs
        exceeded their retry ceiling and require manual investigation; a periodic reaper (deployment
        configuration, not shown here) recovers jobs stuck after a worker crash.
      </p>
      <StatRow
        items={[
          { label: 'Pending', value: health.pendingCount },
          { label: 'Processing', value: health.processingCount },
          { label: 'Dead Letter', value: health.deadLetterCount },
        ]}
      />
    </section>
  );
}

export function OperationalDashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <FunnelSection />
      <QueueDepthSection />
      <JobQueueHealthSection />
      <PoisonJobsSection />
    </div>
  );
}
