/**
 * Motion tokens (spec 003 FR-038–041).
 *
 * A small, fixed set of durations and easing curves, each mapped to a
 * category of transition, applied consistently by category (FR-039). Every
 * entry has a defined reduced-motion equivalent (FR-041) — in practice,
 * `tokens.css`'s global `@media (prefers-reduced-motion: reduce)` rule
 * collapses every duration to near-zero, so components need only use these
 * tokens (never a raw duration) to inherit that behavior automatically; no
 * component-level reduced-motion branching is required.
 */

export type MotionCategory = 'micro' | 'panel' | 'page';

export interface MotionToken {
  readonly purpose: string;
  readonly durationClassName: string;
  readonly easingClassName: string;
}

export const motionTokens: Readonly<Record<MotionCategory, MotionToken>> = {
  micro: {
    purpose: 'Hover, focus, pressed feedback — the most frequent transition.',
    durationClassName: 'duration-micro',
    easingClassName: 'ease-standard',
  },
  panel: {
    purpose: 'Drawer, dialog, dropdown, and popover enter/exit.',
    durationClassName: 'duration-panel',
    easingClassName: 'ease-decelerate',
  },
  page: {
    purpose: 'Route-level and tab-level transitions.',
    durationClassName: 'duration-page',
    easingClassName: 'ease-standard',
  },
} as const;

/** Composed `transition-*` utility className per category, ready to apply. */
export const transitionClassName: Readonly<Record<MotionCategory, string>> = {
  micro: 'transition-colors duration-micro ease-standard',
  panel: 'transition-all duration-panel ease-decelerate',
  page: 'transition-opacity duration-page ease-standard',
} as const;
