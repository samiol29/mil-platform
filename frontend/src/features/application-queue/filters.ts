/**
 * Application Queue filter registry (Product Experience phase, Phase 1).
 *
 * `STATUS_FILTERS` are real today — each maps directly to
 * `Application.status` and the backend's existing `status` query param.
 *
 * `RESERVED_FILTERS` are the operational filters the underwriting-workflow
 * vision calls for (Assigned to Me, Needs Attention, Missing Documents,
 * Escalated, High Risk, Verified Today) that are **not** wired to any UI
 * control yet — none of them are backed by a real field on `Application`
 * today (see the plan's field-availability audit). Each entry names the
 * exact backend field it needs so adding the real filter later is wiring a
 * new chip against this same registry, not a design decision. Do not
 * render these as disabled chips — an unclickable, greyed-out control is
 * its own kind of placeholder UI; simply not rendering them until they're
 * real is the honest choice.
 */

import type { ApplicationStatus } from '@entities/application/types';

export interface StatusFilterOption {
  readonly label: string;
  readonly value: ApplicationStatus;
}

export const STATUS_FILTERS: readonly StatusFilterOption[] = [
  { label: 'Draft', value: 'DRAFT' },
  { label: 'Submitted', value: 'SUBMITTED' },
  { label: 'In Review', value: 'IN_REVIEW' },
  { label: 'Review Complete', value: 'REVIEW_COMPLETE' },
  { label: 'Withdrawn', value: 'WITHDRAWN' },
];

export interface ReservedFilter {
  readonly label: string;
  readonly requiresBackendField: string;
}

export const RESERVED_FILTERS: readonly ReservedFilter[] = [
  { label: 'Assigned to Me', requiresBackendField: 'Application.assigned_reviewer_id' },
  { label: 'Needs Attention', requiresBackendField: 'Application.flagged_finding_count' },
  { label: 'Missing Documents', requiresBackendField: 'Application.missing_document_count' },
  { label: 'Escalated', requiresBackendField: 'Application.escalated_finding_count' },
  { label: 'High Risk', requiresBackendField: 'Application.risk_level' },
  { label: 'Verified Today', requiresBackendField: 'Application.last_verified_at' },
];
