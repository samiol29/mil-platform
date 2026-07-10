/**
 * `Finding.state` display vocabulary — shared by `FindingCard.tsx` and
 * `PolicyRegion` (`ApplicationWorkspace.tsx`) so both present the same
 * state labeling/coloring, not two independently-maintained copies.
 */

import type { Finding } from '@entities/finding/queries';

export const STATE_LABEL: Record<Finding['state'], string> = {
  unreviewed: 'Unreviewed',
  verified: 'Verified',
  overridden: 'Overridden',
  escalated: 'Escalated',
};

export const STATE_CLASS_NAME: Record<Finding['state'], string> = {
  unreviewed: 'text-text-secondary',
  verified: 'text-feedback-success-fg',
  overridden: 'text-feedback-warning-fg',
  escalated: 'text-feedback-error-fg',
};
