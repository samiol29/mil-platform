/**
 * Evidence/Confidence color family (spec 003 FR-023, FR-061) — extraction
 * confidence and evidence-conflict states ONLY.
 *
 * Structurally and hue-distinct from Status (`color.status.ts`) and AI-signal
 * (`color.ai.ts`) — a dedicated teal hue never reused elsewhere in the
 * product. The non-color signal required by FR-026/FR-061 is
 * `filledSegments`: a count of filled bars (3/2/1) rendered by
 * `ConfidenceIndicator`, structurally distinct from a Status badge's icon
 * treatment, so confidence and status remain distinguishable even displayed
 * adjacently (Edge Cases: "the hardest test of the color system's
 * discipline").
 */

import { SignalHigh, SignalLow, SignalMedium } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export interface ConfidenceToken {
  readonly label: string;
  readonly bgClassName: string;
  readonly fgClassName: string;
  readonly fillClassName: string;
  /** Non-color signal (FR-026): number of filled segments out of 3, total. */
  readonly filledSegments: 1 | 2 | 3;
  readonly icon: LucideIcon;
}

export const confidenceTokens: Readonly<Record<ConfidenceLevel, ConfidenceToken>> = {
  high: {
    label: 'High Confidence',
    bgClassName: 'bg-confidence-high-bg',
    fgClassName: 'text-confidence-high-fg',
    fillClassName: 'bg-confidence-high-fill',
    filledSegments: 3,
    icon: SignalHigh,
  },
  medium: {
    label: 'Medium Confidence',
    bgClassName: 'bg-confidence-medium-bg',
    fgClassName: 'text-confidence-medium-fg',
    fillClassName: 'bg-confidence-medium-fill',
    filledSegments: 2,
    icon: SignalMedium,
  },
  low: {
    label: 'Low Confidence',
    bgClassName: 'bg-confidence-low-bg',
    fgClassName: 'text-confidence-low-fg',
    fillClassName: 'bg-confidence-low-fill',
    filledSegments: 1,
    icon: SignalLow,
  },
} as const;

/** Evidence-conflict state (FR-023) — a value that contradicts another. */
export const evidenceConflictToken = {
  label: 'Conflicting Evidence',
  bgClassName: 'bg-confidence-conflict-bg',
  fgClassName: 'text-confidence-conflict-fg',
  borderClassName: 'border-confidence-conflict-border',
} as const;
