/**
 * Type scale (spec 003 FR-006–010).
 *
 * Eight steps, each with a fixed semantic purpose. No interface text may use
 * a size outside this scale (FR-006) — every step maps directly to a
 * Tailwind utility class generated from `tokens.css`'s paired
 * `--text-<step>` / `--text-<step>--line-height` / `--text-<step>--font-weight`
 * custom properties (see `theme/globals.css`'s `@theme inline` block).
 *
 * `dataTabular` is the dedicated numeric/financial/identifier step (FR-007):
 * `globals.css` sets `font-variant-numeric: tabular-nums` at the document
 * root, so any text using this step (or any digit anywhere) aligns in
 * columns without additional per-component configuration.
 */

export type TypeScaleStep =
  | 'display'
  | 'headingPage'
  | 'headingSection'
  | 'body'
  | 'bodyEmphasis'
  | 'label'
  | 'caption'
  | 'dataTabular';

export const typeScaleClassName: Readonly<Record<TypeScaleStep, string>> = {
  display: 'text-display',
  headingPage: 'text-heading-page',
  headingSection: 'text-heading-section',
  body: 'text-body',
  bodyEmphasis: 'text-body-emphasis font-semibold',
  label: 'text-label',
  caption: 'text-caption text-text-secondary',
  dataTabular: 'text-data-tabular font-mono',
} as const;

/** Semantic purpose documented per step (FR-006) — for tooling/Storybook use. */
export const typeScalePurpose: Readonly<Record<TypeScaleStep, string>> = {
  display: 'Rare, large numerals/headline moments (e.g. a dashboard KPI).',
  headingPage: 'Page title — one per screen.',
  headingSection: 'Section heading within a page or panel.',
  body: 'Default body text.',
  bodyEmphasis: 'Emphasized body text (e.g. a finding’s "what" statement).',
  label: 'Form labels, table column headers, compact UI labels.',
  caption: 'Secondary/supporting text (timestamps, helper text).',
  dataTabular: 'Numeric, financial, identifier, and code-like values.',
} as const;

/** Maximum comfortable reading measure for dense text (FR-009). */
export const readingMeasureClassName = 'max-w-[68ch]';
