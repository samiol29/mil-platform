/**
 * Chart color palette (RC3 — Enterprise Experience & Visual Excellence,
 * Analytics Redesign). Every value is a CSS custom property reference into
 * the existing token system (`tokens/tokens.css`) — never a new hardcoded
 * hex palette — so charts stay theme-aware (light/dark) automatically and
 * never introduce a second, parallel color vocabulary. Modern SVG rendering
 * resolves `var(--token)` in presentation attributes (`fill`/`stroke`)
 * exactly like any other CSS color, so this works directly with recharts'
 * `fill`/`stroke` props without needing inline `style`.
 */

/** A small, ordered categorical palette for series with no fixed semantic meaning (e.g. an arbitrary set of policy outcomes). */
export const CHART_CATEGORICAL_PALETTE: readonly string[] = [
  'var(--interactive-primary-default)',
  'var(--ai-signal-fg)',
  'var(--feedback-success-fg)',
  'var(--feedback-warning-fg)',
  'var(--feedback-error-fg)',
  'var(--text-tertiary)',
];

export function categoricalChartColor(index: number): string {
  return CHART_CATEGORICAL_PALETTE[index % CHART_CATEGORICAL_PALETTE.length];
}

export const CHART_GRID_STROKE = 'var(--border-subtle)';
export const CHART_AXIS_STROKE = 'var(--text-tertiary)';
export const CHART_TOOLTIP_BACKGROUND = 'var(--surface-overlay)';
export const CHART_TOOLTIP_BORDER = 'var(--border-default)';
