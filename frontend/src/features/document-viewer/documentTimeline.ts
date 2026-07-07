/**
 * Per-document timeline (Product Experience phase, Phase 8 — "the document
 * remains the anchor," now extending to its own history). Genuinely new
 * derivation, not a reuse of `findingReviewHistory.ts`'s single-predicate
 * filter — a document's real audit trail is scattered across three
 * distinct shapes, confirmed by direct backend inspection
 * (`src/mil/document/service.py`, `src/mil/evidence/service.py`,
 * `src/mil/review/service.py`):
 *
 * - `DOCUMENT_UPLOADED`/`DOCUMENT_STORED` key on the *top-level*
 *   `entityType === 'DOCUMENT'` + `entityId === document.id` — these two
 *   event types carry no `document_id` inside `eventData` at all.
 * - `EVIDENCE_CREATED` carries `eventData.document_id` directly.
 * - `REVIEW_FINDING_APPROVED`/`OVERRIDDEN`/`ESCALATED` carry no document
 *   reference whatsoever — they're reached only by first finding which
 *   findings cite evidence belonging to this document (the same
 *   evidence→findings join `evidenceFindingIndex.ts` already does).
 *
 * `actorType` (`SYSTEM`/`USER`) is the only real "who" signal — no name
 * resolution exists anywhere (same gap as `Document.uploadedBy`/
 * `AuditTrailEntry.actorId` noted throughout this whole plan), so no
 * fabricated reviewer name appears here.
 *
 * **`eventData` keys are camelCase, not the backend's snake_case** —
 * `httpClient`'s response interceptor (`camelCaseKeysDeep`) recurses into
 * this free-form blob with no exemption, so `document_id`/`finding_id`
 * arrive as `documentId`/`findingId`. Confirmed by an integration test
 * that actually round-trips through MSW/`httpClient` (this function's own
 * unit tests construct `AuditTrailEntry` objects directly and never
 * exercised the interceptor, so they didn't catch this originally).
 */

import type { AuditTrailEntry } from '@entities/audit/types';
import type { EvidenceItem } from '@entities/evidence/queries';
import type { Finding } from '@entities/finding/queries';

export interface DocumentTimelineEntry {
  readonly id: string;
  readonly occurredAt: string;
  readonly actorType: AuditTrailEntry['actorType'];
  readonly label: string;
}

const DOCUMENT_EVENT_LABEL: Partial<Record<string, string>> = {
  DOCUMENT_UPLOADED: 'Document uploaded',
  DOCUMENT_STORED: 'Document stored',
};

const REVIEW_EVENT_LABEL: Partial<Record<string, string>> = {
  REVIEW_FINDING_APPROVED: 'A finding on this document was verified',
  REVIEW_FINDING_OVERRIDDEN: 'A finding on this document was overridden',
  REVIEW_FINDING_ESCALATED: 'A finding on this document was escalated',
};

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

export function buildDocumentTimeline(
  auditEntries: readonly AuditTrailEntry[],
  documentId: string,
  evidenceItems: readonly EvidenceItem[],
  findings: readonly Finding[],
): readonly DocumentTimelineEntry[] {
  const entries: DocumentTimelineEntry[] = [];

  const documentEvidenceIds = new Set(
    evidenceItems.filter((item) => item.documentId === documentId).map((item) => item.id),
  );
  const documentFindingIds = new Set(
    findings
      .filter((finding) => finding.evidenceRefs.some((ref) => documentEvidenceIds.has(ref)))
      .map((finding) => finding.id),
  );

  for (const entry of auditEntries) {
    const documentLabel = DOCUMENT_EVENT_LABEL[entry.eventType];
    if (documentLabel !== undefined && entry.entityType === 'DOCUMENT' && entry.entityId === documentId) {
      entries.push({ id: entry.id, occurredAt: entry.occurredAt, actorType: entry.actorType, label: documentLabel });
      continue;
    }

    if (entry.eventType === 'EVIDENCE_CREATED' && asString(entry.eventData.documentId) === documentId) {
      entries.push({
        id: entry.id,
        occurredAt: entry.occurredAt,
        actorType: entry.actorType,
        label: 'Evidence extracted from this document',
      });
      continue;
    }

    const reviewLabel = REVIEW_EVENT_LABEL[entry.eventType];
    if (reviewLabel !== undefined && documentFindingIds.has(asString(entry.eventData.findingId) ?? '')) {
      entries.push({ id: entry.id, occurredAt: entry.occurredAt, actorType: entry.actorType, label: reviewLabel });
    }
  }

  return entries.sort((a, b) => a.occurredAt.localeCompare(b.occurredAt));
}
