import { clsx } from 'clsx';
import type { ClassValue } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

/**
 * `tailwind-merge` configured with this design system's custom `@theme`
 * namespaces (`theme/globals.css`).
 *
 * Without this extension, `tailwind-merge`'s default heuristics cannot tell
 * our custom `text-<type-scale-step>` utilities (font-size — e.g.
 * `text-caption`) apart from our custom `text-<semantic-color>` utilities
 * (text color — e.g. `text-text-on-brand`), because both share the bare
 * `text-` prefix and neither matches a name in Tailwind's own default
 * palette/scale. Left unconfigured, `tailwind-merge` treats every `text-*`
 * class as one conflicting group and silently drops all but the last —
 * this was caught for real by the Storybook `a11y` gate (T033): `Button`'s
 * `size="sm"` variant (`text-caption`) was silently deleting the `primary`
 * variant's `text-text-on-brand` color class, leaving the button's label
 * to inherit the page body's default text color against a colored
 * background — a genuine, gate-caught color-contrast defect, not a
 * hypothetical one.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        {
          text: [
            'display',
            'heading-page',
            'heading-section',
            'body',
            'body-emphasis',
            'label',
            'caption',
            'data-tabular',
          ],
        },
      ],
      'text-color': [
        {
          text: [
            'primary',
            'secondary',
            'tertiary',
            'disabled',
            'critical',
            'inverse',
            'on-brand',
            'status-on-track-fg',
            'status-at-risk-fg',
            'status-overdue-fg',
            'status-blocked-fg',
            'confidence-high-fg',
            'confidence-medium-fg',
            'confidence-low-fg',
            'confidence-conflict-fg',
            'ai-signal-fg',
            'ai-processing-fg',
            'feedback-success-fg',
            'feedback-warning-fg',
            'feedback-error-fg',
          ],
        },
      ],
    },
  },
});

/**
 * Merge className fragments, resolving conflicting Tailwind utilities in
 * favor of the last one specified (standard shadcn/ui primitive helper).
 * Every design-system component uses this instead of manual string
 * concatenation, so a consumer-supplied `className` can safely override a
 * component's own default utility classes without producing duplicate,
 * conflicting classes in the DOM.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
