/**
 * Elevation and radius scales (spec 003 FR-014–016).
 *
 * Three elevation levels, each a specific structural meaning — never a
 * decorative choice (FR-014). Shadows are minimal and strictly functional
 * (FR-016): `base` has none (it IS the page), `raised` is a near-flat
 * surface distinguished mainly by its border (cards, table rows), and
 * `overlay` is the only level with a visible shadow, reserved for content
 * temporarily on top of everything else (dialogs, drawers, dropdowns,
 * popovers). Dark theme independently tunes these (FR-031; see `tokens.css`)
 * rather than reusing light-theme shadow values.
 */

export type ElevationLevel = 'base' | 'raised' | 'overlay';

export interface ElevationToken {
  readonly meaning: string;
  readonly shadowClassName: string;
  readonly borderClassName: string;
}

export const elevationTokens: Readonly<Record<ElevationLevel, ElevationToken>> = {
  base: {
    meaning: 'The page surface itself. No shadow — nothing to elevate above.',
    shadowClassName: 'shadow-none',
    borderClassName: 'border-border-subtle',
  },
  raised: {
    meaning: 'A distinct but non-overlapping surface (card, table row, panel).',
    shadowClassName: 'shadow-raised',
    borderClassName: 'border-border-subtle',
  },
  overlay: {
    meaning: 'Temporarily on top of other content (dialog, drawer, dropdown).',
    shadowClassName: 'shadow-overlay',
    borderClassName: 'border-border-default',
  },
} as const;

/**
 * Border-radius scale (FR-015) — mapped by element category, applied
 * consistently by category across the entire product.
 */
export type RadiusCategory = 'interactive' | 'container' | 'chip';

export const radiusClassName: Readonly<Record<RadiusCategory, string>> = {
  interactive: 'rounded-interactive', // buttons, inputs, menu items
  container: 'rounded-container', // cards, panels, dialogs, drawers
  chip: 'rounded-chip', // badges, chips, pills
} as const;
