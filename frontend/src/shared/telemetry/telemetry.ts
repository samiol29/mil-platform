/**
 * Client-side telemetry (spec 002 tasks.md T042; plan.md Observability,
 * Constitution Principle X — Operational Excellence).
 *
 * The single, shared module every error boundary and Performance Budget
 * measurement reports through — never a scattered `console.error` call.
 * This task does not select a telemetry vendor/backend (an infrastructure
 * decision, per plan.md); `reportError`/`reportPerformanceMetric` are real,
 * complete implementations against a `console`-based reporter today, with
 * the reporting destination itself behind the `TelemetryReporter`
 * interface so wiring a real backend (tasks.md T122) only replaces
 * `activeReporter`, not every call site.
 */

export interface ErrorReport {
  readonly message: string;
  readonly stack?: string;
  /** Which error-boundary tier caught this (`root` / `route` / `panel`), or `undefined` for a directly-reported error. */
  readonly boundary?: string;
  readonly context?: Readonly<Record<string, unknown>>;
}

export interface PerformanceMetricReport {
  readonly name: string;
  readonly durationMs: number;
  readonly context?: Readonly<Record<string, unknown>>;
}

export interface TelemetryReporter {
  reportError: (report: ErrorReport) => void;
  reportPerformanceMetric: (report: PerformanceMetricReport) => void;
}

/**
 * Default reporter: structured `console` output. Correct and complete for
 * local development and for a reader piping browser console output into a
 * log aggregator — not a stub awaiting replacement, though tasks.md T122
 * (wiring an actual telemetry backend) will supply a production
 * `TelemetryReporter` via `setTelemetryReporter`.
 */
const consoleReporter: TelemetryReporter = {
  reportError: (report) => {
    console.error('[telemetry:error]', report);
  },
  reportPerformanceMetric: (report) => {
    console.info('[telemetry:performance]', report);
  },
};

let activeReporter: TelemetryReporter = consoleReporter;

export function setTelemetryReporter(reporter: TelemetryReporter): void {
  activeReporter = reporter;
}

export function reportError(report: ErrorReport): void {
  activeReporter.reportError(report);
}

export function reportPerformanceMetric(report: PerformanceMetricReport): void {
  activeReporter.reportPerformanceMetric(report);
}
