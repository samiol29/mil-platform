/**
 * Semantic color tokens (spec 003 FR-018–021).
 *
 * Role- and meaning-based names ("surface.raised", "text.critical",
 * "border.focus") — the ONLY color vocabulary components and features are
 * permitted to reference (FR-018). Every export here is a closed set of
 * Tailwind utility class names bound to the CSS custom properties in
 * `tokens.css`; there is no mechanism to construct an arbitrary class name
 * from this module, only to select one of the named, enumerated roles.
 *
 * Both light and dark resolutions exist for every token named here — see
 * `tokens.css`'s `:root` and `:root[data-theme='dark']` blocks. This module
 * does not choose a theme; it names the role, and the CSS variable
 * resolves per the active theme.
 */

export const surfaceClassName = {
  background: 'bg-surface-background',
  secondary: 'bg-surface-secondary',
  raised: 'bg-surface-raised',
  overlay: 'bg-surface-overlay',
  disabled: 'bg-surface-disabled',
  sunken: 'bg-surface-sunken',
} as const;

export const textClassName = {
  primary: 'text-text-primary',
  secondary: 'text-text-secondary',
  tertiary: 'text-text-tertiary',
  disabled: 'text-text-disabled',
  critical: 'text-text-critical',
  inverse: 'text-text-inverse',
  onBrand: 'text-text-on-brand',
} as const;

export const borderClassName = {
  subtle: 'border-border-subtle',
  default: 'border-border-default',
  strong: 'border-border-strong',
} as const;

/** Interaction-state class groups (FR-020) — one per action category. */
export const interactiveClassName = {
  primary:
    'bg-interactive-primary-default hover:bg-interactive-primary-hover active:bg-interactive-primary-active disabled:bg-interactive-primary-disabled disabled:text-interactive-primary-disabled-text',
  secondary:
    'bg-interactive-secondary-default hover:bg-interactive-secondary-hover active:bg-interactive-secondary-active border border-interactive-secondary-border disabled:bg-interactive-secondary-disabled',
  danger:
    'bg-interactive-danger-default hover:bg-interactive-danger-hover active:bg-interactive-danger-active',
} as const;

/**
 * The single dedicated focus treatment (FR-021), applied identically to
 * every interactive element in the product — never a per-component focus
 * style. Compose this className onto every focusable element.
 */
export const focusRingClassName =
  'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2';

export const colorSemantic = {
  surface: surfaceClassName,
  text: textClassName,
  border: borderClassName,
  interactive: interactiveClassName,
  focusRing: focusRingClassName,
} as const;
