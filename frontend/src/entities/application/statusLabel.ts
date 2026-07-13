/**
 * Application lifecycle status presentation (UX audit §5) — plain colored
 * label, following the exact `STATE_LABEL`/`STATE_CLASS_NAME` precedent
 * `FindingCard.tsx` already established for `Finding.state`. Deliberately
 * NOT `StatusBadge`: that component's `StatusLevel` family (on-track/at-risk
 * /overdue/blocked) is reserved for workflow/SLA state per spec 003
 * FR-022's own doc comment (`color.status.ts`) — an application's lifecycle
 * stage is a different concept and must not borrow that family's colors.
 */

import type { ApplicationStatus } from './types';

export const APPLICATION_STATUS_LABEL: Record<ApplicationStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  IN_REVIEW: 'In Review',
  REVIEW_COMPLETE: 'Review Complete',
  WITHDRAWN: 'Withdrawn',
};

export const APPLICATION_STATUS_CLASS_NAME: Record<ApplicationStatus, string> = {
  DRAFT: 'text-text-secondary',
  SUBMITTED: 'text-text-secondary',
  IN_REVIEW: 'text-feedback-warning-fg',
  REVIEW_COMPLETE: 'text-feedback-success-fg',
  WITHDRAWN: 'text-text-tertiary',
};

/**
 * The one lifecycle-status chip (Product Experience phase, Phase 11) —
 * soft-tinted, borderless, shared by the header's active-application chip,
 * the Workspace header, and the Queue's Stage column, replacing three
 * hand-rolled variants. Color only where it communicates state (in-review
 * warning tint, complete success tint); neutral lifecycle stages stay
 * neutral. Still deliberately not `StatusBadge` (see module docstring).
 */
export const APPLICATION_STATUS_CHIP_CLASS_NAME: Record<ApplicationStatus, string> = {
  DRAFT: 'bg-surface-sunken text-text-secondary',
  SUBMITTED: 'bg-surface-sunken text-text-secondary',
  IN_REVIEW: 'bg-feedback-warning-bg text-feedback-warning-fg',
  REVIEW_COMPLETE: 'bg-feedback-success-bg text-feedback-success-fg',
  WITHDRAWN: 'bg-surface-sunken text-text-tertiary',
};

export const APPLICATION_STATUS_CHIP_BASE_CLASS =
  'rounded-chip px-2 py-0.5 text-caption font-medium transition-colors duration-panel ease-standard';
