/**
 * Application Queue filter registry (Product Experience phase, Phase 1;
 * revised in the final product polish sprint, A1).
 *
 * `STATUS_FILTERS` are real today — each maps directly to
 * `Application.status` and the backend's existing `status` query param.
 *
 * `ATTENTION_FILTERS` are real, independent boolean toggles (composing with
 * `STATUS_FILTERS`/search, AND not OR) backed by genuinely new backend
 * queries added this sprint: "Assigned to Me"
 * (`AssignmentService.get_assigned_to_me` — owner or reviewer) and
 * "Escalated" (`ReviewService.get_escalated_for_caller` — a Finding
 * currently escalated to the caller's role or to them specifically). Both
 * used to live in `RESERVED_FILTERS` below with no backing field at all.
 *
 * `RESERVED_FILTERS` are the remaining operational filters the underwriting-
 * workflow vision calls for (Needs Attention, Missing Documents, High Risk,
 * Verified Today) that are **still not** wired to any UI control — none of
 * them are backed by a real field on `Application` today. Each entry names
 * the exact backend field it needs so adding the real filter later is
 * wiring a new chip against this same registry, not a design decision. Do
 * not render these as disabled chips — an unclickable, greyed-out control
 * is its own kind of placeholder UI; simply not rendering them until
 * they're real is the honest choice.
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

export type AttentionFilterKey = 'assignedToMe' | 'escalated';

export interface AttentionFilterOption {
  readonly label: string;
  readonly key: AttentionFilterKey;
}

export const ATTENTION_FILTERS: readonly AttentionFilterOption[] = [
  { label: 'Assigned to Me', key: 'assignedToMe' },
  { label: 'Escalated', key: 'escalated' },
];

export interface ReservedFilter {
  readonly label: string;
  readonly requiresBackendField: string;
}

export const RESERVED_FILTERS: readonly ReservedFilter[] = [
  { label: 'Needs Attention', requiresBackendField: 'Application.flagged_finding_count' },
  { label: 'Missing Documents', requiresBackendField: 'Application.missing_document_count' },
  { label: 'High Risk', requiresBackendField: 'Application.risk_level' },
  { label: 'Verified Today', requiresBackendField: 'Application.last_verified_at' },
];
