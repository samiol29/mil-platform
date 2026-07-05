/**
 * Status color family (spec 003 FR-022) — workflow/SLA lifecycle state ONLY.
 *
 * Structurally and hue-distinct from the Evidence/Confidence family
 * (`color.confidence.ts`) and the AI-signal family (`color.ai.ts`) — this
 * family MUST NEVER be repurposed to represent extraction confidence,
 * evidence conflict, or "this was AI-generated" (FR-022). Every entry pairs
 * its color with a non-color signal (a distinct icon) so meaning survives
 * grayscale printing and color-vision deficiency (FR-026, Edge Cases: print
 * export).
 */

import { AlertTriangle, Ban, CheckCircle2, Clock } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type StatusLevel = 'onTrack' | 'atRisk' | 'overdue' | 'blocked';

export interface StatusToken {
  readonly label: string;
  readonly bgClassName: string;
  readonly fgClassName: string;
  readonly borderClassName: string;
  readonly icon: LucideIcon;
}

export const statusTokens: Readonly<Record<StatusLevel, StatusToken>> = {
  onTrack: {
    label: 'On Track',
    bgClassName: 'bg-status-on-track-bg',
    fgClassName: 'text-status-on-track-fg',
    borderClassName: 'border-status-on-track-border',
    icon: CheckCircle2,
  },
  atRisk: {
    label: 'At Risk',
    bgClassName: 'bg-status-at-risk-bg',
    fgClassName: 'text-status-at-risk-fg',
    borderClassName: 'border-status-at-risk-border',
    icon: Clock,
  },
  overdue: {
    label: 'Overdue',
    bgClassName: 'bg-status-overdue-bg',
    fgClassName: 'text-status-overdue-fg',
    borderClassName: 'border-status-overdue-border',
    icon: AlertTriangle,
  },
  blocked: {
    label: 'Blocked',
    bgClassName: 'bg-status-blocked-bg',
    fgClassName: 'text-status-blocked-fg',
    borderClassName: 'border-status-blocked-border',
    icon: Ban,
  },
} as const;
