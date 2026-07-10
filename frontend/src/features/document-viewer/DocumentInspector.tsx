/**
 * DocumentInspector (Product Experience phase, Phase 8 — "the Document
 * Viewer should evolve from displaying PDFs into the central investigation
 * workspace for a document"). A persistent panel beside `DocumentViewer`
 * (mounted in `ApplicationWorkspace.tsx`'s `DocumentsRegion`), scoped
 * entirely to whichever document is currently active — the document stays
 * the anchor; this panel is what makes everything already known *about*
 * it reachable without leaving the Documents region.
 *
 * Five tabs (`Tabs`/`TabsPanel`, the same primitive already wired into the
 * region nav) match exactly what the underlying data can honestly support
 * today — no sixth "Reviewer" tab was added for a comments feature that
 * doesn't exist (the backend's `ReviewComment` model has no HTTP route,
 * confirmed in this session's Phase 6 research):
 *
 * - **Metadata**: every real `Document` field already fetched by
 *   `useDocumentsForApplication` — zero new backend calls — plus the real
 *   assigned party (`usePartiesForApplication`, the same join
 *   `DocumentProcessingList` already does). This is what "reviewer
 *   context" honestly maps to: who this document is for, not a fabricated
 *   commentary feed.
 * - **Evidence**: this document's evidence items only
 *   (`groupEvidenceByDocument`, extracted from `EvidenceRegion` so both
 *   call sites share one implementation), rendered with the unchanged
 *   `EvidenceCard` component. Its own "used in findings" action is omitted
 *   here — the adjacent Findings tab already lists exactly those findings,
 *   one click away in the same panel, so a second identical action would
 *   be redundant, not a missing feature.
 * - **Findings**: findings whose `evidenceRefs` cite this document's
 *   evidence (`buildEvidenceToFindingsIndex`, reused from Phase 5/6/7, not
 *   reinvented) — there is no direct `Finding.documentId` field; a
 *   finding's connection to a document is always evidence-mediated.
 * - **Policy**: `groupFindingsByPolicyVersion` run over that same
 *   document-scoped finding subset — same honest "cannot show rules that
 *   passed silently" disclosure as the application-level Policy region,
 *   because the underlying backend limitation is identical here.
 * - **Timeline**: `buildDocumentTimeline` — genuinely new derivation (see
 *   that file's docstring), combining three real event shapes rather than
 *   reusing `findingReviewHistory.ts`'s single-predicate filter.
 *
 * "View finding" (Findings/Policy tabs) and evidence-chip clicks
 * (Evidence tab) reuse the exact same `focusFindingId`/`DocumentJumpTarget`
 * mechanisms already threaded through `ApplicationWorkspace.tsx` for the
 * Evidence/Findings/Policy regions — no new navigation channel.
 */

import { useState } from 'react';

import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { EvidenceChip } from '@design-system/components/EvidenceChip';
import { LoadingState } from '@design-system/components/LoadingState';
import { Tabs, TabsList, TabsPanel, TabsTrigger } from '@design-system/components/Tabs';
import { cn } from '@design-system/lib/cn';
import { useAuditTrail } from '@entities/audit/queries';
import type { Document } from '@entities/document/queries';
import { useEvidenceForApplication } from '@entities/evidence/queries';
import { useFindingsForApplication } from '@entities/finding/queries';
import { usePartiesForApplication } from '@entities/party/queries';
import { PARTY_TYPE_LABEL } from '@entities/party/types';
import { EvidenceCard } from '@features/application-workspace/EvidenceCard';
import { buildEvidenceToFindingsIndex } from '@features/application-workspace/evidenceFindingIndex';
import { STATE_CLASS_NAME, STATE_LABEL } from '@features/application-workspace/findingState';
import { groupEvidenceByDocument } from '@features/application-workspace/groupEvidenceByDocument';
import { groupFindingsByPolicyVersion } from '@features/application-workspace/groupFindingsByPolicyVersion';

import type { DocumentJumpTarget } from './DocumentViewer';
import { buildDocumentTimeline } from './documentTimeline';

type InspectorTab = 'metadata' | 'evidence' | 'findings' | 'policy' | 'timeline';

const INGESTION_STATUS_LABEL: Record<Document['ingestionStatus'], string> = {
  PENDING: 'Queued for processing',
  IN_PROGRESS: 'Processing…',
  COMPLETED: 'Ready',
  FAILED: 'Processing failed',
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export interface DocumentInspectorProps {
  readonly applicationId: string;
  readonly document: Document;
  readonly onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
  readonly onViewFinding: (findingId: string) => void;
}

export function DocumentInspector({
  applicationId,
  document,
  onEvidenceChipActivate,
  onViewFinding,
}: DocumentInspectorProps) {
  const [tab, setTab] = useState<InspectorTab>('metadata');
  const evidenceQuery = useEvidenceForApplication(applicationId);
  const findingsQuery = useFindingsForApplication(applicationId);
  const auditQuery = useAuditTrail(applicationId);
  const partiesQuery = usePartiesForApplication(applicationId);

  if (evidenceQuery.isError || findingsQuery.isError) {
    return (
      <div className="bg-surface-raised shadow-raised rounded-container p-4">
        <ErrorState variant="inline" title="Could not load this document's investigation context" />
      </div>
    );
  }
  if (evidenceQuery.isPending || findingsQuery.isPending) {
    return (
      <div className="bg-surface-raised shadow-raised rounded-container p-4">
        <LoadingState label="Loading investigation context…" />
      </div>
    );
  }

  const evidenceItems = evidenceQuery.data;
  const findings = findingsQuery.data;
  const auditEntries = auditQuery.data ?? [];
  const parties = partiesQuery.data ?? [];

  const documentEvidence = groupEvidenceByDocument(evidenceItems).get(document.id) ?? [];
  const evidenceToFindings = buildEvidenceToFindingsIndex(findings);

  const documentFindingsById = new Map<string, (typeof findings)[number]>();
  for (const item of documentEvidence) {
    for (const finding of evidenceToFindings.get(item.id) ?? []) {
      documentFindingsById.set(finding.id, finding);
    }
  }
  const documentFindings = Array.from(documentFindingsById.values());
  const policyGroups = groupFindingsByPolicyVersion(documentFindings);
  const timeline = buildDocumentTimeline(auditEntries, document.id, evidenceItems, findings);
  const assignedParty =
    document.partyId !== null ? parties.find((party) => party.id === document.partyId) : undefined;

  return (
    <div className="bg-surface-raised shadow-raised rounded-container flex flex-col">
      <Tabs
        value={tab}
        onValueChange={(value) => {
          setTab(value as InspectorTab);
        }}
      >
        <TabsList aria-label="Document inspector sections">
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
          <TabsTrigger value="evidence">Evidence ({documentEvidence.length})</TabsTrigger>
          <TabsTrigger value="findings">Findings ({documentFindings.length})</TabsTrigger>
          <TabsTrigger value="policy">Policy</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <TabsPanel value="metadata" className="flex flex-col gap-3 p-4">
          <dl className="text-caption grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
            <dt className="text-text-tertiary">Document type</dt>
            <dd className="text-text-primary">{document.documentType}</dd>
            <dt className="text-text-tertiary">Status</dt>
            <dd className="text-text-primary">
              {INGESTION_STATUS_LABEL[document.ingestionStatus]}
            </dd>
            <dt className="text-text-tertiary">Uploaded</dt>
            <dd className="text-text-primary">{formatDateTime(document.uploadedAt)}</dd>
            <dt className="text-text-tertiary">Pages</dt>
            <dd className="text-text-primary">{document.pageCount ?? '—'}</dd>
            <dt className="text-text-tertiary">Evidence extracted</dt>
            <dd className="text-text-primary">{document.evidenceItemCount}</dd>
            <dt className="text-text-tertiary">Content hash</dt>
            <dd className="text-text-primary truncate font-mono" title={document.contentHash}>
              {document.contentHash.slice(0, 16)}…
            </dd>
            <dt className="text-text-tertiary">Assigned to</dt>
            <dd className="text-text-primary">
              {assignedParty !== undefined
                ? `${PARTY_TYPE_LABEL[assignedParty.partyType]} — ${assignedParty.displayName}`
                : 'Unassigned'}
            </dd>
          </dl>
          {document.ingestionStatus === 'FAILED' && (
            <p className="text-caption text-feedback-error-fg">
              {document.ingestionError ?? 'Processing failed.'}
            </p>
          )}
        </TabsPanel>

        <TabsPanel value="evidence" className="p-4">
          {documentEvidence.length === 0 ? (
            <EmptyState
              title="No evidence extracted from this document yet"
              description="Evidence appears here once this document finishes processing."
            />
          ) : (
            <div className="flex flex-col gap-3">
              {documentEvidence.map((item) => (
                <EvidenceCard
                  key={item.id}
                  item={item}
                  relatedFindingsCount={0}
                  onViewInDocument={() => {
                    onEvidenceChipActivate({
                      documentId: item.documentId,
                      pageNumber: item.pageNumber ?? 1,
                      boundingBox: item.fieldLocation?.boundingBox ?? null,
                      label: item.evidenceType,
                    });
                  }}
                />
              ))}
            </div>
          )}
        </TabsPanel>

        <TabsPanel value="findings" className="p-4">
          {documentFindings.length === 0 ? (
            <EmptyState
              title="No findings cite this document's evidence yet"
              description="Findings appear here once evidence from this document has been evaluated."
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {documentFindings.map((finding) => (
                <li
                  key={finding.id}
                  className="border-border-subtle flex flex-col gap-1.5 border-b pb-3 last:border-b-0 last:pb-0"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="text-body text-text-primary">{finding.what}</span>
                    <span
                      className={cn('text-caption font-medium', STATE_CLASS_NAME[finding.state])}
                    >
                      {STATE_LABEL[finding.state]}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onViewFinding(finding.id);
                    }}
                    className="text-caption text-text-secondary hover:text-text-primary self-start outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                  >
                    View finding →
                  </button>
                </li>
              ))}
            </ul>
          )}
        </TabsPanel>

        <TabsPanel value="policy" className="flex flex-col gap-3 p-4">
          <p className="text-caption text-feedback-warning-fg bg-feedback-warning-bg border-feedback-warning-border rounded-container border p-3">
            This shows findings on this document that were flagged during policy evaluation. It
            cannot show checks that passed silently, individual rule names, or rule-level rationale
            — no such data exists in the backend today.
          </p>
          {documentFindings.length === 0 ? (
            <EmptyState
              title="No findings to evaluate against policy yet"
              description="This document has no flagged findings, so there is nothing to group by policy version."
            />
          ) : (
            policyGroups.map((group) => (
              <div
                key={group.policyVersion ?? '__not_evaluated__'}
                className="border-border-subtle rounded-container border"
              >
                <div className="bg-surface-secondary rounded-t-container flex items-center justify-between gap-2 px-3 py-2">
                  <span className="text-label text-text-primary font-medium">
                    {group.policyVersion !== null
                      ? `Policy ${group.policyVersion}`
                      : 'Not yet evaluated'}
                  </span>
                  <span className="text-caption text-text-secondary">
                    {group.findings.length} finding{group.findings.length === 1 ? '' : 's'}
                  </span>
                </div>
                <ul className="flex flex-col gap-1 p-3">
                  {group.findings.map((finding) => (
                    <li
                      key={finding.id}
                      className="text-caption text-text-secondary flex items-center justify-between gap-2"
                    >
                      <span className="truncate">{finding.what}</span>
                      <EvidenceChip
                        label="View"
                        onClick={() => {
                          onViewFinding(finding.id);
                        }}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </TabsPanel>

        <TabsPanel value="timeline" className="p-4">
          {timeline.length === 0 ? (
            <EmptyState
              title="No timeline events for this document yet"
              description="Uploads, processing, evidence, and review activity will appear here as they happen."
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {timeline.map((entry) => (
                <li key={entry.id} className="text-caption text-text-secondary">
                  <span className="text-text-primary">{entry.label}</span> —{' '}
                  {formatDateTime(entry.occurredAt)}{' '}
                  <span className="text-text-tertiary">
                    ({entry.actorType === 'SYSTEM' ? 'system' : 'reviewer'})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </TabsPanel>
      </Tabs>
    </div>
  );
}
