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
