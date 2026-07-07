/**
 * Per-finding review history (Product Experience phase, Phase 6 —
 * "make review collaborative"). `src/mil/review/service.py`'s
 * `approve_finding`/`override_finding`/`escalate_finding` each already
 * write a real audit event whose `eventData` carries the reviewer's own
 * typed `reason` (plus `previous_value`/`new_value`/`target_role` for
 * override/escalate) — this data already reaches the frontend via
 * `useAuditTrail`, but `AuditTimeline.tsx` never reads `eventData`, so it's
 * fetched and then discarded, not missing from the network.
 *
 * `AuditTrailEntry.entityId` is the review *session* id, not the finding's
 * — the only place a finding id appears is inside `eventData`, so that's
 * what this filters on. `actorType` (`SYSTEM`/`USER`) is the only real
 * actor signal available — no name resolution exists (the same gap noted
 * for `Document.uploadedBy`/`AuditTrailEntry.actorId` throughout this
 * plan), so no fabricated reviewer name is ever shown here.
 *
 * **`eventData` keys are camelCase, not the backend's snake_case.**
 * `httpClient`'s response interceptor (`camelCaseKeysDeep`) recurses into
 * every nested object with no exemption for this free-form blob — so the
 * backend's `finding_id`/`previous_value`/`new_value`/`target_role` arrive
 * here as `findingId`/`previousValue`/`newValue`/`targetRole`. Reading the
 * snake_case names (an earlier version of this file did) silently returns
 * `undefined` against real data — confirmed by an integration test that
 * actually round-trips through MSW/`httpClient`, unlike this function's
 * own pure-unit tests, which construct `AuditTrailEntry` objects directly
 * and never exercised the interceptor.
 */

import type { AuditTrailEntry } from '@entities/audit/types';

export interface ReviewHistoryEntry {
  readonly id: string;
  readonly occurredAt: string;
  readonly actorType: AuditTrailEntry['actorType'];
  readonly kind: 'verified' | 'overridden' | 'escalated';
  readonly reason: string | null;
  readonly previousValue: string | null;
  readonly newValue: string | null;
  readonly targetRole: string | null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

/**
 * One pass over the whole application's audit entries, grouped by finding
 * (Product Experience phase, Phase 10 audit — `FindingsRegion` previously
 * called `buildFindingReviewHistory` once per finding, each call re-scanning
 * and re-sorting every audit entry: genuinely `O(findings × audit entries)`
 * render work. This computes every finding's history in one `O(audit
 * entries)` pass instead — `buildFindingReviewHistory` below is now a thin
 * convenience wrapper over this, so its own tests/signature are unchanged).
 */
export function groupReviewHistoryByFinding(
  auditEntries: readonly AuditTrailEntry[],
): ReadonlyMap<string, readonly ReviewHistoryEntry[]> {
  const byFinding = new Map<string, ReviewHistoryEntry[]>();

  function push(findingId: string, entry: ReviewHistoryEntry) {
    const existing = byFinding.get(findingId);
    if (existing) existing.push(entry);
    else byFinding.set(findingId, [entry]);
  }

  for (const entry of auditEntries) {
    const findingId = asString(entry.eventData.findingId);
    if (findingId === null) continue;

    if (entry.eventType === 'REVIEW_FINDING_APPROVED') {
      push(findingId, {
        id: entry.id,
        occurredAt: entry.occurredAt,
        actorType: entry.actorType,
        kind: 'verified',
        reason: null,
        previousValue: null,
        newValue: null,
        targetRole: null,
      });
    } else if (entry.eventType === 'REVIEW_FINDING_OVERRIDDEN') {
      push(findingId, {
        id: entry.id,
        occurredAt: entry.occurredAt,
        actorType: entry.actorType,
        kind: 'overridden',
        reason: asString(entry.eventData.reason),
        previousValue: asString(entry.eventData.previousValue),
        newValue: asString(entry.eventData.newValue),
        targetRole: null,
      });
    } else if (entry.eventType === 'REVIEW_FINDING_ESCALATED') {
      push(findingId, {
        id: entry.id,
        occurredAt: entry.occurredAt,
        actorType: entry.actorType,
        kind: 'escalated',
        reason: asString(entry.eventData.reason),
        previousValue: null,
        newValue: null,
        targetRole: asString(entry.eventData.targetRole),
      });
    }
  }

  for (const entries of byFinding.values()) {
    entries.sort((a, b) => a.occurredAt.localeCompare(b.occurredAt));
  }

  return byFinding;
}

export function buildFindingReviewHistory(
  auditEntries: readonly AuditTrailEntry[],
  findingId: string,
): readonly ReviewHistoryEntry[] {
  return groupReviewHistoryByFinding(auditEntries).get(findingId) ?? [];
}
