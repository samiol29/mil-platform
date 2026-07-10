/**
 * Primitive color tokens (spec 003 FR-018).
 *
 * Raw, non-meaningful color ramps. Nothing in this file carries semantic
 * meaning ("this is the danger color") — that mapping belongs exclusively to
 * `color.semantic.ts` and the Status/Confidence/AI family files. Components
 * and features MUST NOT import this module directly; it exists so the full
 * set of raw values the system defines is enumerable in one place (closed
 * vocabulary, FR-027), and so `color.semantic.ts` has a single source to
 * reference.
 *
 * Literal hex values live in `tokens.css` (the one file in the product
 * permitted to contain them). This module mirrors each primitive as a typed
 * reference to its CSS custom property — never as a duplicated raw value —
 * so the two can never drift out of sync silently.
 */

function cssVar(name: string): string {
  return `var(--${name})`;
}

export const neutral = {
  0: cssVar('color-neutral-0'),
  50: cssVar('color-neutral-50'),
  100: cssVar('color-neutral-100'),
  200: cssVar('color-neutral-200'),
  300: cssVar('color-neutral-300'),
  400: cssVar('color-neutral-400'),
  500: cssVar('color-neutral-500'),
  600: cssVar('color-neutral-600'),
  700: cssVar('color-neutral-700'),
  800: cssVar('color-neutral-800'),
  900: cssVar('color-neutral-900'),
  950: cssVar('color-neutral-950'),
} as const;

export const brand = {
  50: cssVar('color-brand-50'),
  100: cssVar('color-brand-100'),
  300: cssVar('color-brand-300'),
  500: cssVar('color-brand-500'),
  600: cssVar('color-brand-600'),
  700: cssVar('color-brand-700'),
  900: cssVar('color-brand-900'),
} as const;

export const green = {
  100: cssVar('color-green-100'),
  300: cssVar('color-green-300'),
  600: cssVar('color-green-600'),
  700: cssVar('color-green-700'),
  900: cssVar('color-green-900'),
} as const;

export const amber = {
  100: cssVar('color-amber-100'),
  300: cssVar('color-amber-300'),
  600: cssVar('color-amber-600'),
  700: cssVar('color-amber-700'),
  900: cssVar('color-amber-900'),
} as const;

export const red = {
  100: cssVar('color-red-100'),
  300: cssVar('color-red-300'),
  600: cssVar('color-red-600'),
  700: cssVar('color-red-700'),
  900: cssVar('color-red-900'),
} as const;

export const slateBlocked = {
  100: cssVar('color-slate-blocked-100'),
  600: cssVar('color-slate-blocked-600'),
  700: cssVar('color-slate-blocked-700'),
  900: cssVar('color-slate-blocked-900'),
} as const;

/** Evidence/Confidence family hue (FR-023) — never reused outside it. */
export const teal = {
  100: cssVar('color-teal-100'),
  300: cssVar('color-teal-300'),
  600: cssVar('color-teal-600'),
  700: cssVar('color-teal-700'),
  900: cssVar('color-teal-900'),
} as const;

/** AI-signal family hue (FR-024) — never reused outside it. */
export const violet = {
  100: cssVar('color-violet-100'),
  300: cssVar('color-violet-300'),
  600: cssVar('color-violet-600'),
  700: cssVar('color-violet-700'),
  900: cssVar('color-violet-900'),
} as const;

export const colorPrimitives = {
  neutral,
  brand,
  green,
  amber,
  red,
  slateBlocked,
  teal,
  violet,
} as const;
