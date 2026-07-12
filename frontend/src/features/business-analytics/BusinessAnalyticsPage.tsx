/**
 * Business Analytics (spec 005-enterprise-platform §11, Wave 3) — an
 * executive analytics view. Only real, on-demand backend aggregates are
 * shown — no fabricated KPI, no historical trend chart, since no
 * time-series metrics substrate exists on the backend (see the spec's own
 * implementation-correction note for this section). Where trend data
 * would normally appear, this page shows an honest disclosure instead.
 */

import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import { useBusinessAnalyticsSnapshot } from '@entities/analytics/queries';

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '—';
  const hours = seconds / 3600;
  if (hours < 1) return `${String(Math.round(seconds / 60))}m`;
  return `${hours.toFixed(1)}h`;
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-surface-raised shadow-raised rounded-container flex-1 px-4 py-3">
      <div className="text-display tabular-nums">{value}</div>
      <div className="text-caption text-text-tertiary tracking-wide uppercase">{label}</div>
    </div>
  );
}

export function BusinessAnalyticsPage() {
  const snapshotQuery = useBusinessAnalyticsSnapshot();

  if (snapshotQuery.isPending) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }
  if (snapshotQuery.isError) {
    return (
      <ErrorState
        title="Failed to load business analytics"
        description={
          snapshotQuery.error instanceof Error ? snapshotQuery.error.message : 'Unknown error'
        }
        onRetry={() => void snapshotQuery.refetch()}
      />
    );
  }

  const snapshot = snapshotQuery.data;
  const totalApplications = snapshot.applicationCountsByStatus.reduce((sum, r) => sum + r.count, 0);
  const totalFindings = snapshot.findingOutcomes.reduce((sum, r) => sum + r.count, 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex gap-3">
        <StatCard label="Applications" value={totalApplications} />
        <StatCard label="Findings" value={totalFindings} />
        <StatCard label="Documents" value={snapshot.documentCount} />
        <StatCard label="Evidence Items" value={snapshot.evidenceCount} />
        <StatCard
          label="Avg. Review Duration"
          value={formatDuration(snapshot.averageReviewDurationSeconds)}
        />
      </div>

      <section className="flex flex-col gap-2">
        <h2 className="text-heading">Applications by Status</h2>
        {snapshot.applicationCountsByStatus.length === 0 ? (
          <p className="text-caption text-text-tertiary">No applications yet.</p>
        ) : (
          <table className="text-body w-full">
            <tbody className="divide-border-default divide-y">
              {snapshot.applicationCountsByStatus.map((row) => (
                <tr key={row.status}>
                  <td className="py-1.5">{row.status}</td>
                  <td className="py-1.5 text-right tabular-nums">{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-heading">Finding Outcomes</h2>
        <p className="text-caption text-text-tertiary">
          Verification/override/escalation rate, derived from real finding lifecycle states.
        </p>
        {snapshot.findingOutcomes.length === 0 ? (
          <p className="text-caption text-text-tertiary">No findings yet.</p>
        ) : (
          <table className="text-body w-full">
            <tbody className="divide-border-default divide-y">
              {snapshot.findingOutcomes.map((row) => (
                <tr key={row.lifecycleState}>
                  <td className="py-1.5">{row.lifecycleState}</td>
                  <td className="py-1.5 text-right tabular-nums">
                    {row.count} (
                    {totalFindings > 0 ? Math.round((row.count / totalFindings) * 100) : 0}%)
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-heading">Policy Calibration</h2>
        <p className="text-caption text-text-tertiary">
          Outcome distribution by policy version — helps judge whether a policy pack is flagging too
          much or too little.
        </p>
        {snapshot.policyOutcomes.length === 0 ? (
          <p className="text-caption text-text-tertiary">No policy evaluations yet.</p>
        ) : (
          <table className="text-body w-full">
            <thead>
              <tr className="text-caption text-text-tertiary border-border-default border-b text-left uppercase">
                <th className="py-1.5 font-normal">Policy Version</th>
                <th className="py-1.5 font-normal">Outcome</th>
                <th className="py-1.5 text-right font-normal">Count</th>
              </tr>
            </thead>
            <tbody className="divide-border-default divide-y">
              {snapshot.policyOutcomes.map((row) => (
                <tr key={`${row.policyVersion}-${row.outcome}`}>
                  <td className="py-1.5">{row.policyVersion}</td>
                  <td className="py-1.5">{row.outcome}</td>
                  <td className="py-1.5 text-right tabular-nums">{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="bg-surface-sunken text-caption text-text-tertiary rounded-container p-3">
        This is a current-state snapshot, not a historical trend report — this platform does not yet
        track time-series metrics, so month-over-month or multi-period trends are not available.
        This view is analytics, not the compliance record; the Audit Timeline remains the
        authoritative history.
      </div>
    </div>
  );
}
