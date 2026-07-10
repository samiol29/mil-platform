/**
 * Application-level case history (Product Experience phase, Phase 9 — "the
 * Timeline should evolve beyond an audit log into the application's case
 * history"). The whole-application counterpart to Phase 8's
 * `documentTimeline.ts` (one document's history) — same pattern, wider
 * scope, not a new persistence concept. `AuditTimeline.tsx`/`useAuditTrail`
 * remain the untouched source of truth; this is a pure client-side
 * transform of the identical data already fetched for Overview's
 * "Activity" card.
 *
 * Every real event type below was confirmed by grepping every
 * `.record(...)` call site across the backend (`src/mil/**\/*.py`) — one
 * audit event becomes exactly one timeline entry, never merged or
 * collapsed into a synthetic beat that isn't in the data. Unrecognized
 * event types (the four `COPILOT_*` types, global `POLICY_PACK_*`/
 * `POLICY_RULE_ADDED` lifecycle events not tied to a finding) are silently
 * omitted — the same discipline `documentTimeline.ts` already established
 * — never shown as a raw fallback string.
 *
 * `trace` resolves each entry back to a real document or finding using
 * only the event's own real reference (`entityId` for document/finding
 * entity events, `eventData.documentId`/`eventData.findingId` for
 * evidence/review/policy events — the same "entityId is the session, not
 * the finding" gap Phase 6's `findingReviewHistory.ts` already handles).
 * This is the seam for future case-history additions (reviewer comments,
 * document version history, reassessments, policy-pack changes, LOS sync,
 * workflow milestones): each would be one more real event type mapped
 * here, rendered by the same component — never built ahead of a real
 * event/endpoint existing.
 *
 * **`eventData` keys read here are camelCase, not the backend's
 * snake_case.** `httpClient`'s response interceptor (`camelCaseKeysDeep`)
 * recurses into this free-form blob with no exemption, so e.g. the
 * backend's `previous_value`/`target_role`/`policy_version` arrive as
 * `previousValue`/`targetRole`/`policyVersion` by the time this function
 * ever sees them.
 */

import type { AuditTrailEntry } from '@entities/audit/types';
import type { Document } from '@entities/document/queries';
import type { Finding } from '@entities/finding/queries';

export type ApplicationTimelineTrace =
  | { readonly kind: 'document'; readonly documentId: string }
  | { readonly kind: 'finding'; readonly findingId: string };

export interface ApplicationTimelineEntry {
  readonly id: string;
  readonly occurredAt: string;
  readonly actorType: AuditTrailEntry['actorType'];
  readonly label: string;
  readonly trace?: ApplicationTimelineTrace | undefined;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

export function buildApplicationTimeline(
  auditEntries: readonly AuditTrailEntry[],
  documents: readonly Document[],
  findings: readonly Finding[],
): readonly ApplicationTimelineEntry[] {
  const documentsById = new Map(documents.map((doc) => [doc.id, doc]));
  const findingsById = new Map(findings.map((finding) => [finding.id, finding]));

  function documentLabel(documentId: string | null): string {
    if (documentId === null) return 'a document';
    return documentsById.get(documentId)?.filename ?? 'a document';
  }

  function findingLabel(findingId: string | null): string {
    if (findingId === null) return 'a finding';
    return findingsById.get(findingId)?.what ?? 'a finding';
  }

  const entries: ApplicationTimelineEntry[] = [];

  for (const entry of auditEntries) {
    const base = { id: entry.id, occurredAt: entry.occurredAt, actorType: entry.actorType };
    const data = entry.eventData;

    switch (entry.eventType) {
      case 'APPLICATION_CREATED':
        entries.push({ ...base, label: 'Application created' });
        break;
      case 'APPLICATION_STATE_CHANGED': {
        const from = asString(data.fromStatus) ?? '—';
        const to = asString(data.toStatus) ?? '—';
        entries.push({ ...base, label: `Status changed from ${from} to ${to}` });
        break;
      }
      case 'PARTY_ADDED': {
        const name = asString(data.displayName) ?? 'a borrower';
        entries.push({ ...base, label: `Borrower added: ${name}` });
        break;
      }
      case 'PARTY_REMOVED': {
        const partyType = asString(data.partyType) ?? 'Borrower';
        entries.push({ ...base, label: `Borrower removed (${partyType})` });
        break;
      }

      case 'DOCUMENT_UPLOADED': {
        const filename = asString(data.originalFilename) ?? documentLabel(entry.entityId);
        entries.push({
          ...base,
          label: `Document uploaded: ${filename}`,
          trace: { kind: 'document', documentId: entry.entityId },
        });
        break;
      }
      case 'DOCUMENT_STORED': {
        entries.push({
          ...base,
          label: `Document stored: ${documentLabel(entry.entityId)}`,
          trace: { kind: 'document', documentId: entry.entityId },
        });
        break;
      }
      case 'DOCUMENT_INGESTION_STARTED': {
        entries.push({
          ...base,
          label: `Processing started: ${documentLabel(entry.entityId)}`,
          trace: { kind: 'document', documentId: entry.entityId },
        });
        break;
      }
      case 'DOCUMENT_INGESTION_COMPLETED': {
        const pageCount = asNumber(data.pageCount);
        const evidenceCount = asNumber(data.evidenceItemCount);
        const detail =
          pageCount !== null && evidenceCount !== null
            ? ` (${String(pageCount)} pages, ${String(evidenceCount)} evidence items)`
            : '';
        entries.push({
          ...base,
          label: `Processing completed: ${documentLabel(entry.entityId)}${detail}`,
          trace: { kind: 'document', documentId: entry.entityId },
        });
        break;
      }
      case 'DOCUMENT_INGESTION_FAILED': {
        const reason = asString(data.reason);
        entries.push({
          ...base,
          label: `Processing failed: ${documentLabel(entry.entityId)}${reason !== null ? ` — ${reason}` : ''}`,
          trace: { kind: 'document', documentId: entry.entityId },
        });
        break;
      }

      case 'EVIDENCE_CREATED': {
        const evidenceType = asString(data.evidenceType) ?? 'a field';
        const documentId = asString(data.documentId);
        entries.push({
          ...base,
          label: `Evidence extracted: ${evidenceType} (from ${documentLabel(documentId)})`,
          trace: documentId !== null ? { kind: 'document', documentId } : undefined,
        });
        break;
      }

      case 'FINDING_GENERATED': {
        entries.push({
          ...base,
          label: `Finding generated: ${findingLabel(entry.entityId)}`,
          trace: { kind: 'finding', findingId: entry.entityId },
        });
        break;
      }

      case 'REVIEW_SESSION_STARTED': {
        const findingId = asString(data.findingId);
        entries.push({
          ...base,
          label: `Review started: ${findingLabel(findingId)}`,
          trace: findingId !== null ? { kind: 'finding', findingId } : undefined,
        });
        break;
      }
      case 'REVIEW_REVIEWER_ASSIGNED': {
        entries.push({ ...base, label: 'Reviewer assigned' });
        break;
      }
      case 'REVIEW_FINDING_APPROVED': {
        const findingId = asString(data.findingId);
        entries.push({
          ...base,
          label: `Finding verified: ${findingLabel(findingId)}`,
          trace: findingId !== null ? { kind: 'finding', findingId } : undefined,
        });
        break;
      }
      case 'REVIEW_FINDING_REJECTED': {
        const findingId = asString(data.findingId);
        const reason = asString(data.reason) ?? '';
        entries.push({
          ...base,
          label: `Finding rejected: ${findingLabel(findingId)} — "${reason}"`,
          trace: findingId !== null ? { kind: 'finding', findingId } : undefined,
        });
        break;
      }
      case 'REVIEW_FINDING_OVERRIDDEN': {
        const findingId = asString(data.findingId);
        const reason = asString(data.reason) ?? '';
        const previousValue = asString(data.previousValue) ?? '—';
        const newValue = asString(data.newValue) ?? '—';
        entries.push({
          ...base,
          label: `Finding overridden: ${findingLabel(findingId)} — "${reason}" (was ${previousValue} → ${newValue})`,
          trace: findingId !== null ? { kind: 'finding', findingId } : undefined,
        });
        break;
      }
      case 'REVIEW_FINDING_ESCALATED': {
        const findingId = asString(data.findingId);
        const reason = asString(data.reason) ?? '';
        const targetRole = asString(data.targetRole) ?? 'another role';
        entries.push({
          ...base,
          label: `Finding escalated to ${targetRole}: ${findingLabel(findingId)} — "${reason}"`,
          trace: findingId !== null ? { kind: 'finding', findingId } : undefined,
        });
        break;
      }
      case 'REVIEW_COMMENT_ADDED': {
        entries.push({ ...base, label: 'A reviewer comment was added' });
        break;
      }

      case 'POLICY_EVALUATED': {
        const findingId = asString(data.findingId);
        const policyVersion = asString(data.policyVersion) ?? '—';
        const outcome = asString(data.outcome) ?? 'evaluated';
        entries.push({
          ...base,
          label: `Policy evaluated (v${policyVersion}) for ${findingLabel(findingId)}: ${outcome}`,
          trace: findingId !== null ? { kind: 'finding', findingId } : undefined,
        });
        break;
      }

      default:
        // Unrecognized event type (e.g. Copilot activity, global policy-pack
        // lifecycle events not tied to a finding) — silently omitted, never
        // shown as a raw, unlabeled fallback string.
        break;
    }
  }

  return entries.sort((a, b) => a.occurredAt.localeCompare(b.occurredAt));
}
