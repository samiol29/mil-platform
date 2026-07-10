/**
 * Spacing scale (spec 003 FR-011).
 *
 * Base unit: 4px. This system deliberately reuses Tailwind's native spacing
 * scale (itself a fixed multiple of the same 4px base — `--spacing: 0.25rem`
 * by default) rather than defining a parallel, redundant scale: Tailwind's
 * `p-*`/`m-*`/`gap-*` utilities already are "all values drawn from a single
 * base unit and fixed multiple sequence," which is exactly FR-011's
 * requirement, not a generic framework default happening to coincide with it.
 *
 * `spacingStep` below is the CLOSED enumeration of steps this product uses —
 * every padding/margin/gap value in every component MUST be one of these
 * (FR-011: "no arbitrary spacing values permitted"). A step not in this list
 * is either a genuine gap requiring a formal addition here (003 Future
 * Extensibility), or a mistake to fix in review — never a legitimate
 * one-off Tailwind arbitrary value (e.g. `p-[13px]`).
 */

export const spacingStep = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 64] as const;

export type SpacingStep = (typeof spacingStep)[number];

/** `spacingStep` step → pixels, for documentation/tooling (Storybook, audits). */
export const spacingStepPx: Readonly<Record<SpacingStep, number>> = {
  0: 0,
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
  10: 40,
  12: 48,
  16: 64,
  20: 80,
  24: 96,
  32: 128,
  40: 160,
  48: 192,
  64: 256,
} as const;
