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

/**
 * A plain proportion bar for an already-real count against an already-real
 * total (final polish sprint) — no analytics are invented here, this is
 * purely a visual comparison of numbers the page already renders as text,
 * so a reviewer can compare rows at a glance instead of doing the division
 * themselves.
 */
function ProportionRow({
  label,
  count,
  total,
  detail,
}: {
  label: string;
  count: number;
  total: number;
  detail?: string;
}) {
  const percent = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <tr>
      <td className="py-1.5">
        <div className="flex flex-col gap-1">
          <span>{label}</span>
          <div className="bg-surface-sunken h-1.5 w-full max-w-48 overflow-hidden rounded-full">
            <div
              className="bg-interactive-primary-default h-full rounded-full"
              style={{ width: `${String(percent)}%` }}
            />
          </div>
        </div>
      </td>
      <td className="py-1.5 text-right tabular-nums">
        {detail ?? `${String(count)} (${String(percent)}%)`}
      </td>
    </tr>
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
                <ProportionRow
                  key={row.status}
                  label={row.status}
                  count={row.count}
                  total={totalApplications}
                  detail={String(row.count)}
                />
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
                <ProportionRow
                  key={row.lifecycleState}
                  label={row.lifecycleState}
                  count={row.count}
                  total={totalFindings}
                />
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
