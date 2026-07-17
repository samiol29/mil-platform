/**
 * Business Analytics (spec 005-enterprise-platform §11, Wave 3; visually
 * redesigned in RC3 — Enterprise Experience & Visual Excellence). An
 * executive analytics view. Only real, on-demand backend aggregates are
 * shown — no fabricated KPI, no historical trend chart, since no
 * time-series metrics substrate exists on the backend (see the spec's own
 * implementation-correction note for this section). Where trend data
 * would normally appear, this page shows an honest disclosure instead.
 *
 * RC3 replaces the plain proportion-bar/table rendering with real charts
 * (`recharts`) over the exact same fields — a horizontal bar chart for
 * `applicationCountsByStatus`, a donut for `findingOutcomes` — because the
 * data is genuinely categorical/proportional and a chart communicates that
 * faster than a column of numbers. Nothing new is computed: every chart
 * consumes the identical already-fetched snapshot the previous table did.
 * `policyOutcomes` stays a table — it's a (version × outcome) matrix, not a
 * single-series distribution, so a chart would not honestly simplify it.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  CHART_AXIS_STROKE,
  CHART_GRID_STROKE,
  CHART_TOOLTIP_BACKGROUND,
  CHART_TOOLTIP_BORDER,
  categoricalChartColor,
} from '@design-system/charts/chartTheme';
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

/** Shared tooltip styling — every chart on this page uses the identical treatment. */
const TOOLTIP_CONTENT_STYLE = {
  background: CHART_TOOLTIP_BACKGROUND,
  border: `1px solid ${CHART_TOOLTIP_BORDER}`,
  borderRadius: 8,
  fontSize: 12,
};

const APPLICATION_STATUS_CHART_COLOR: Record<string, string> = {
  DRAFT: 'var(--text-tertiary)',
  SUBMITTED: 'var(--interactive-primary-default)',
  IN_REVIEW: 'var(--feedback-warning-fg)',
  REVIEW_COMPLETE: 'var(--feedback-success-fg)',
  WITHDRAWN: 'var(--text-disabled)',
};

function ApplicationStatusChart({
  rows,
}: {
  readonly rows: readonly { status: string; count: number }[];
}) {
  const data = rows.map((row) => ({
    name: row.status,
    count: row.count,
    fill: APPLICATION_STATUS_CHART_COLOR[row.status] ?? 'var(--text-tertiary)',
  }));
  const height = Math.max(140, data.length * 44);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
        <CartesianGrid horizontal={false} stroke={CHART_GRID_STROKE} />
        <XAxis type="number" allowDecimals={false} stroke={CHART_AXIS_STROKE} fontSize={12} />
        <YAxis
          type="category"
          dataKey="name"
          width={110}
          stroke={CHART_AXIS_STROKE}
          fontSize={12}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: 'var(--surface-secondary)' }}
          contentStyle={TOOLTIP_CONTENT_STYLE}
        />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function FindingOutcomeChart({
  rows,
}: {
  readonly rows: readonly { lifecycleState: string; count: number }[];
}) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const data = rows.map((row, index) => ({
    name: row.lifecycleState,
    value: row.count,
    fill: categoricalChartColor(index),
  }));

  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width="60%" height={180}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={48}
            outerRadius={72}
            paddingAngle={data.length > 1 ? 2 : 0}
            strokeWidth={0}
          />
          <Tooltip contentStyle={TOOLTIP_CONTENT_STYLE} />
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex flex-1 flex-col gap-1.5">
        {data.map((entry, index) => (
          <li key={entry.name} className="flex items-center gap-2 text-caption">
            <span
              aria-hidden="true"
              className="size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: categoricalChartColor(index) }}
            />
            <span className="text-text-secondary min-w-0 flex-1 truncate">{entry.name}</span>
            <span className="text-text-primary font-medium tabular-nums">
              {entry.value} ({total > 0 ? Math.round((entry.value / total) * 100) : 0}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BusinessAnalyticsPage() {
  const snapshotQuery = useBusinessAnalyticsSnapshot();

  if (snapshotQuery.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex gap-3">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-16 flex-1" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-2 p-5">
          <h2 className="text-heading">Applications by Status</h2>
          {snapshot.applicationCountsByStatus.length === 0 ? (
            <p className="text-caption text-text-tertiary">No applications yet.</p>
          ) : (
            <ApplicationStatusChart rows={snapshot.applicationCountsByStatus} />
          )}
        </section>

        <section className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-2 p-5">
          <h2 className="text-heading">Finding Outcomes</h2>
          <p className="text-caption text-text-tertiary">
            Real finding lifecycle states — derived, never a fabricated trend.
          </p>
          {snapshot.findingOutcomes.length === 0 ? (
            <p className="text-caption text-text-tertiary">No findings yet.</p>
          ) : (
            <FindingOutcomeChart rows={snapshot.findingOutcomes} />
          )}
        </section>
      </div>

      <section className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-2 p-5">
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
