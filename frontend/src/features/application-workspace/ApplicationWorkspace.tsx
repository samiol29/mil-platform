/**
 * Application Workspace shell (spec 002 tasks.md T061).
 *
 * Composes the overview/findings/evidence/documents regions with no full
 * page reload between them (002 FR-029) — region switching is client-side
 * (the active region is URL state owned by the route, tasks.md T069; see
 * `routes/applications.$applicationId.tsx`). Each region is wrapped in its
 * own `PanelErrorBoundary` (plan.md Error Boundaries, tier 3) so a failure
 * in one never blanks the others.
 *
 * **No Copilot region exists here.** Copilot integration is User Story 3
 * (tasks.md T083–T091), out of this session's scope — the region set below
 * is exactly what User Story 1 needs and no more; adding an inert "Copilot"
 * tab that does nothing would be exactly the placeholder UI this session
 * was told to avoid.
 *
 * The Document Viewer region renders `DocumentViewer` (tasks.md T064–T066):
 * PDF rendering, page/zoom navigation, and the evidence-highlight overlay.
 * Clicking an evidence chip in the Findings *or* Evidence region switches to
 * the Documents region and jumps the viewer directly to that evidence's
 * page and highlight (FR-039) — `jumpTarget` is lifted to this component
 * since it coordinates between regions. `focusDocumentId` (Product
 * Experience phase, Phase 5) is the same pattern in the opposite direction:
 * a Documents-region "View evidence" click carries which document to focus
 * once the Evidence region renders, closing the bidirectional-navigation
 * loop the investigation-workspace refinement calls for.
 *
 * The region nav below is `Tabs`/`TabsList`/`TabsTrigger`
 * (`design-system/components/Tabs`, built in Phase 0 but never actually
 * wired in until now) rather than the hand-rolled `role="tab"` button row
 * this file used before — real Arrow/Home/End keyboard navigation between
 * regions, one definition of the tab-nav pattern instead of two.
 */

import { ChevronDown, ChevronRight } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { EvidenceChip } from '@design-system/components/EvidenceChip';
import { LoadingState } from '@design-system/components/LoadingState';
import { ProcessingPipeline } from '@design-system/components/ProcessingPipeline';
import { SummaryGrid, type SummaryGridItem } from '@design-system/components/SummaryGrid';
import { Tabs, TabsList, TabsTrigger } from '@design-system/components/Tabs';
import { COLLAPSIBLE_GROUP_HEADER_CLASS } from '@design-system/lib/collapsibleGroupHeader';
import { cn } from '@design-system/lib/cn';
import type { Application } from '@entities/application/queries';
import { useApplication } from '@entities/application/queries';
import {
  APPLICATION_STATUS_CLASS_NAME,
  APPLICATION_STATUS_LABEL,
} from '@entities/application/statusLabel';
import { useAuditTrail } from '@entities/audit/queries';
import type { Document } from '@entities/document/queries';
import { useDocumentsForApplication } from '@entities/document/queries';
import { useEvidenceForApplication } from '@entities/evidence/queries';
import { useFindingsForApplication } from '@entities/finding/queries';
import { usePartiesForApplication } from '@entities/party/queries';
import { PARTY_TYPE_LABEL } from '@entities/party/types';
import { DocumentInspector } from '@features/document-viewer/DocumentInspector';
import { DocumentViewer, type DocumentJumpTarget } from '@features/document-viewer/DocumentViewer';
import { DocumentProcessingList } from '@features/document-upload/DocumentProcessingList';
import { UploadSection } from '@features/document-upload/UploadSection';
import { PanelErrorBoundary } from '@shared/errors/PanelErrorBoundary';

import { ApplicationTimeline } from './ApplicationTimeline';
import { AuditTimeline } from './AuditTimeline';
import { deriveApplicationStages, summarizeDocuments } from './applicationPipelineSummary';
import { buildApplicationTimeline } from './buildApplicationTimeline';
import { EvidenceCard } from './EvidenceCard';
import { buildEvidenceToFindingsIndex } from './evidenceFindingIndex';
import { FindingActions } from './FindingActions';
import { FindingCard } from './FindingCard';
import { groupReviewHistoryByFinding } from './findingReviewHistory';
import { STATE_CLASS_NAME, STATE_LABEL } from './findingState';
import { groupEvidenceByDocument } from './groupEvidenceByDocument';
import { groupFindingsByPolicyVersion } from './groupFindingsByPolicyVersion';
import { REGION_LABEL, WORKSPACE_REGIONS, type WorkspaceRegion } from './regions';
import { StaleRecordBanner } from './StaleRecordBanner';

export interface ApplicationWorkspaceProps {
  readonly applicationId: string;
  readonly region: WorkspaceRegion;
  readonly onRegionChange: (region: WorkspaceRegion) => void;
  /** Auditor/compliance role (spec 002 FR-037, tasks.md T128): no action controls render. */
  readonly readOnly?: boolean;
}

export function ApplicationWorkspace({
  applicationId,
  region,
  onRegionChange,
  readOnly = false,
}: ApplicationWorkspaceProps) {
  const applicationQuery = useApplication(applicationId);
  const [jumpTarget, setJumpTarget] = useState<DocumentJumpTarget | null>(null);
  const [focusDocumentId, setFocusDocumentId] = useState<string | null>(null);
  const [focusFindingId, setFocusFindingId] = useState<string | null>(null);

  function activateEvidenceJump(jump: DocumentJumpTarget) {
    setJumpTarget(jump);
    onRegionChange('documents');
  }

  function viewFinding(findingId: string) {
    setFocusFindingId(findingId);
    onRegionChange('findings');
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <Tabs value={region} onValueChange={onRegionChange}>
        <TabsList aria-label="Application Workspace sections">
          {WORKSPACE_REGIONS.map((candidate) => (
            <TabsTrigger key={candidate} value={candidate}>
              {REGION_LABEL[candidate]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {applicationQuery.isPending && <LoadingState label="Loading application…" />}
      {applicationQuery.isError && (
        <ErrorState
          title="Could not load this application"
          onRetry={() => {
            void applicationQuery.refetch();
          }}
        />
      )}

      {applicationQuery.data !== undefined && (
        <>
          <StaleRecordBanner
            queryKey={['application', applicationId]}
            dataUpdatedAt={applicationQuery.dataUpdatedAt}
          />

          {region === 'overview' && (
            <PanelErrorBoundary panelName="Overview">
              <OverviewRegion
                applicationId={applicationId}
                application={applicationQuery.data}
                onRegionChange={onRegionChange}
              />
            </PanelErrorBoundary>
          )}

          {region === 'findings' && (
            <PanelErrorBoundary panelName="Findings">
              <FindingsRegion
                applicationId={applicationId}
                readOnly={readOnly}
                focusFindingId={focusFindingId}
                onEvidenceChipActivate={activateEvidenceJump}
              />
            </PanelErrorBoundary>
          )}

          {region === 'evidence' && (
            <PanelErrorBoundary panelName="Evidence">
              <EvidenceRegion
                applicationId={applicationId}
                focusDocumentId={focusDocumentId}
                onEvidenceChipActivate={activateEvidenceJump}
                onViewFindings={() => {
                  onRegionChange('findings');
                }}
              />
            </PanelErrorBoundary>
          )}

          {region === 'documents' && (
            <PanelErrorBoundary panelName="Documents">
              <DocumentsRegion
                applicationId={applicationId}
                jumpTarget={jumpTarget}
                onViewEvidence={(documentId) => {
                  setFocusDocumentId(documentId);
                  onRegionChange('evidence');
                }}
                onEvidenceChipActivate={activateEvidenceJump}
                onViewFinding={viewFinding}
              />
            </PanelErrorBoundary>
          )}

          {region === 'policy' && (
            <PanelErrorBoundary panelName="Policy">
              <PolicyRegion
                applicationId={applicationId}
                onEvidenceChipActivate={activateEvidenceJump}
                onViewFinding={viewFinding}
              />
            </PanelErrorBoundary>
          )}

          {region === 'timeline' && (
            <PanelErrorBoundary panelName="Timeline">
              <TimelineRegion
                applicationId={applicationId}
                onEvidenceChipActivate={activateEvidenceJump}
                onViewFinding={viewFinding}
              />
            </PanelErrorBoundary>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Findings region. `focusFindingId` (Product Experience phase, Phase 7 —
 * set by a Policy-region "View finding" click) scrolls the target finding
 * into view on arrival, mirroring `EvidenceRegion`'s existing
 * `focusDocumentId` handling exactly (same ref-map + scroll-into-view
 * pattern, not a third navigation mechanism).
 */
function FindingsRegion({
  applicationId,
  readOnly,
  focusFindingId = null,
  onEvidenceChipActivate,
}: {
  applicationId: string;
  readOnly: boolean;
  focusFindingId?: string | null;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
}) {
  const findingsQuery = useFindingsForApplication(applicationId);
  const evidenceQuery = useEvidenceForApplication(applicationId);
  const auditQuery = useAuditTrail(applicationId);
  const findingRefs = useRef(new Map<string, HTMLDivElement>());

  // One O(audit entries) pass for every finding's review history, computed
  // once per render (Product Experience phase, Phase 10 audit) rather than
  // one re-scan-and-sort per finding in the render loop below.
  const reviewHistoryByFinding = useMemo(
    () => groupReviewHistoryByFinding(auditQuery.data ?? []),
    [auditQuery.data],
  );

  useEffect(() => {
    if (focusFindingId === null) return;
    const node = findingRefs.current.get(focusFindingId);
    node?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [focusFindingId]);

  if (findingsQuery.isPending) return <LoadingState label="Loading findings…" />;
  if (findingsQuery.isError) {
    return (
      <ErrorState
        title="Could not load findings"
        onRetry={() => {
          void findingsQuery.refetch();
        }}
      />
    );
  }
  if (findingsQuery.data.length === 0) {
    return (
      <EmptyState
        title="No findings yet"
        description="Findings appear once evidence has been evaluated."
      />
    );
  }

  const evidenceItems = evidenceQuery.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-heading-section text-text-primary">Findings</h2>
      {findingsQuery.data.map((finding) => (
        <div
          key={finding.id}
          ref={(node) => {
            if (node) findingRefs.current.set(finding.id, node);
            else findingRefs.current.delete(finding.id);
          }}
        >
          <FindingCard
            finding={finding}
            evidenceItems={evidenceItems}
            reviewHistory={reviewHistoryByFinding.get(finding.id) ?? []}
            onEvidenceChipActivate={(item) => {
              onEvidenceChipActivate({
                documentId: item.documentId,
                pageNumber: item.pageNumber ?? 1,
                boundingBox: item.fieldLocation?.boundingBox ?? null,
                label: item.evidenceType,
              });
            }}
            actions={
              readOnly ? undefined : (
                <FindingActions applicationId={applicationId} finding={finding} />
              )
            }
          />
        </div>
      ))}
    </div>
  );
}

/**
 * Evidence region (Product Experience phase, Phase 5 — investigation-grade,
 * replacing the previous flat `SummaryGrid`). Groups evidence by its source
 * document — "which document produced it" is the organizing question the
 * investigation-workspace refinement asks for — with each group headed by
 * the real filename (resolved against `useDocumentsForApplication`, not a
 * bare document id).
 *
 * `focusDocumentId` (set by a Documents-region "View evidence" click) is
 * the return half of the bidirectional navigation loop: it ensures that
 * document's group is expanded and scrolled into view on arrival.
 */
function EvidenceRegion({
  applicationId,
  focusDocumentId,
  onEvidenceChipActivate,
  onViewFindings,
}: {
  applicationId: string;
  focusDocumentId: string | null;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
  onViewFindings: () => void;
}) {
  const evidenceQuery = useEvidenceForApplication(applicationId);
  const documentsQuery = useDocumentsForApplication(applicationId);
  const findingsQuery = useFindingsForApplication(applicationId);
  const [collapsedGroups, setCollapsedGroups] = useState<ReadonlySet<string>>(new Set());
  const groupRefs = useRef(new Map<string, HTMLDivElement>());
  const [previousFocusDocumentId, setPreviousFocusDocumentId] = useState(focusDocumentId);

  // A Documents-region "View evidence" click always wins: ensure the target
  // group is expanded and scroll it into view. Adjusting state during
  // render (react.dev's own pattern, already used for `jumpTarget` in
  // `DocumentViewer.tsx`) rather than an effect avoids an extra post-commit
  // render.
  if (focusDocumentId !== previousFocusDocumentId) {
    setPreviousFocusDocumentId(focusDocumentId);
    if (focusDocumentId !== null) {
      setCollapsedGroups((prev) => {
        if (!prev.has(focusDocumentId)) return prev;
        const next = new Set(prev);
        next.delete(focusDocumentId);
        return next;
      });
    }
  }

  useEffect(() => {
    if (focusDocumentId === null) return;
    const node = groupRefs.current.get(focusDocumentId);
    node?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [focusDocumentId]);

  if (evidenceQuery.isPending) return <LoadingState label="Loading evidence…" />;
  if (evidenceQuery.isError) {
    return (
      <ErrorState
        title="Could not load evidence"
        onRetry={() => {
          void evidenceQuery.refetch();
        }}
      />
    );
  }
  if (evidenceQuery.data.length === 0) {
    return <EmptyState title="No evidence extracted yet" />;
  }

  const documents = documentsQuery.data ?? [];
  const evidenceToFindings = buildEvidenceToFindingsIndex(findingsQuery.data ?? []);
  const evidenceById = new Map(evidenceQuery.data.map((item) => [item.id, item]));
  const groups = groupEvidenceByDocument(evidenceQuery.data);

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-heading-section text-text-primary">Evidence</h2>
      <div className="flex flex-col gap-4">
        {Array.from(groups.entries()).map(([documentId, items]) => {
          const isCollapsed = collapsedGroups.has(documentId);
          const filename = documents.find((doc) => doc.id === documentId)?.filename ?? 'Document';
          return (
            <div
              key={documentId}
              ref={(node) => {
                if (node) groupRefs.current.set(documentId, node);
                else groupRefs.current.delete(documentId);
              }}
              className="border-border-subtle rounded-container border"
            >
              <button
                type="button"
                onClick={() => {
                  setCollapsedGroups((prev) => {
                    const next = new Set(prev);
                    if (next.has(documentId)) next.delete(documentId);
                    else next.add(documentId);
                    return next;
                  });
                }}
                className={cn(COLLAPSIBLE_GROUP_HEADER_CLASS, 'rounded-t-container')}
              >
                {isCollapsed ? (
                  <ChevronRight className="size-3.5" aria-hidden="true" />
                ) : (
                  <ChevronDown className="size-3.5" aria-hidden="true" />
                )}
                {filename}
                <span className="text-text-tertiary">({items.length})</span>
              </button>
              {!isCollapsed && (
                <div className="grid grid-cols-1 gap-3 p-3 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((item) => {
                    const supersededItem =
                      item.supersedesId !== null ? evidenceById.get(item.supersedesId) : undefined;
                    const relatedFindings = evidenceToFindings.get(item.id) ?? [];
                    return (
                      <EvidenceCard
                        key={item.id}
                        item={item}
                        supersededItem={supersededItem}
                        relatedFindingsCount={relatedFindings.length}
                        onViewInDocument={() => {
                          onEvidenceChipActivate({
                            documentId: item.documentId,
                            pageNumber: item.pageNumber ?? 1,
                            boundingBox: item.fieldLocation?.boundingBox ?? null,
                            label: item.evidenceType,
                          });
                        }}
                        onViewFindings={relatedFindings.length > 0 ? onViewFindings : undefined}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Documents region (Product Experience phase, Phase 3) — mounts the
 * upload workflow above the viewer. `uploadExpanded` starts `true` when the
 * application has zero documents (so the empty state and the expanded
 * upload panel appear together) and is otherwise lifted here so
 * `DocumentViewer`'s empty-state action can expand it on demand.
 *
 * `selectedDocumentId` (Product Experience phase, Phase 4.5) is lifted here
 * so `DocumentProcessingList`'s rows can drive `DocumentViewer`'s active
 * document — the two are no longer independent, unconnected lists.
 *
 * `activeDocument` (Product Experience phase, Phase 8) is set by
 * `DocumentViewer`'s new `onActiveDocumentChange` callback — its own
 * already-existing `jumpTarget`/`selectedDocumentId` precedence logic is
 * reused, not duplicated, to know which document `DocumentInspector`
 * should scope to. The viewer and its inspector sit side by side (a
 * persistent split, not a `Drawer` overlay — the inspector must stay
 * visible alongside the PDF at all times) so the document remains the
 * anchor of the investigation, per this phase's guiding principle.
 */
function DocumentsRegion({
  applicationId,
  jumpTarget,
  onViewEvidence,
  onEvidenceChipActivate,
  onViewFinding,
}: {
  applicationId: string;
  jumpTarget: DocumentJumpTarget | null;
  onViewEvidence: (documentId: string) => void;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
  onViewFinding: (findingId: string) => void;
}) {
  const documentsQuery = useDocumentsForApplication(applicationId);
  const [uploadExpanded, setUploadExpanded] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [activeDocument, setActiveDocument] = useState<Document | null>(null);
  const hasNoDocuments = (documentsQuery.data ?? []).length === 0;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-heading-section text-text-primary">Documents</h2>
      <UploadSection
        applicationId={applicationId}
        expanded={uploadExpanded || hasNoDocuments}
        onExpandedChange={setUploadExpanded}
      />
      <DocumentProcessingList
        applicationId={applicationId}
        selectedDocumentId={selectedDocumentId}
        onSelectDocument={setSelectedDocumentId}
        onViewEvidence={onViewEvidence}
      />
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_380px]">
        <DocumentViewer
          applicationId={applicationId}
          jumpTarget={jumpTarget}
          selectedDocumentId={selectedDocumentId}
          onRequestUpload={() => {
            setUploadExpanded(true);
          }}
          onActiveDocumentChange={setActiveDocument}
        />
        {activeDocument !== null && (
          <DocumentInspector
            applicationId={applicationId}
            document={activeDocument}
            onEvidenceChipActivate={onEvidenceChipActivate}
            onViewFinding={onViewFinding}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Policy region (Product Experience phase, Phase 7) — the fourth link in
 * the investigation chain (Document → Evidence → Finding → **Policy**).
 * Not the decision-maker: **AI identified → Policy evaluated → Human
 * decided** — this region shows the middle step only.
 *
 * Ground truth (confirmed by direct backend inspection): no policy-pack
 * HTTP route exists anywhere — `Application.activePolicyPackId` reaches
 * the frontend as a bare, unresolvable UUID, and `Finding.policyVersion`
 * (independently set per finding) is the only real "which evaluation" the
 * backend exposes. Critically, **the backend has no concept of a rule
 * passing** — a satisfied policy check produces no `Finding` at all, so
 * this region can never show "which rules passed"; the permanent
 * disclosure below states that plainly rather than omitting it silently.
 * `awaitingJudgmentCount`/`resolvedCount` reuse `Finding.state` — the only
 * real "has a human judged this yet" signal (`escalated` is non-terminal,
 * still awaiting resolution, per `src/mil/review/service.py`'s own
 * docstring).
 *
 * Grouping reuses `groupFindingsByPolicyVersion`'s `policyVersion !== null`
 * signal — the same one `applicationPipelineSummary.ts`'s
 * `deriveApplicationStages` already uses for the Overview pipeline's
 * "Policy" stage. Evidence chips and the "View finding" action reuse the
 * exact same `DocumentJumpTarget`/scroll-into-view mechanisms Evidence and
 * Findings already use — no new navigation channel.
 *
 * Deliberately not built (no backend endpoint exists for any of it):
 * individual rule cards, rule rationale, version comparison, regulatory
 * references. This region's summary-header-plus-version-groups shape is
 * the seam a future rule-level endpoint would extend into, not a
 * placeholder graphic simulating one.
 */
function PolicyRegion({
  applicationId,
  onEvidenceChipActivate,
  onViewFinding,
}: {
  applicationId: string;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
  onViewFinding: (findingId: string) => void;
}) {
  const applicationQuery = useApplication(applicationId);
  const findingsQuery = useFindingsForApplication(applicationId);
  const evidenceQuery = useEvidenceForApplication(applicationId);

  if (findingsQuery.isPending) return <LoadingState label="Loading policy evaluation…" />;
  if (findingsQuery.isError) {
    return (
      <ErrorState
        title="Could not load policy evaluation"
        onRetry={() => {
          void findingsQuery.refetch();
        }}
      />
    );
  }

  const findings = findingsQuery.data;
  const evidenceById = new Map((evidenceQuery.data ?? []).map((item) => [item.id, item]));
  const groups = groupFindingsByPolicyVersion(findings);
  const evaluatedCount = findings.filter((f) => f.policyVersion !== null).length;
  const awaitingJudgmentCount = findings.filter(
    (f) => f.state === 'unreviewed' || f.state === 'escalated',
  ).length;
  const activePolicyPackId = applicationQuery.data?.activePolicyPackId ?? null;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-heading-section text-text-primary">Policy</h2>

      <div className="border-border-subtle bg-surface-raised rounded-container flex flex-col gap-3 border p-5">
        <div>
          <p className="text-caption text-text-secondary">Active policy pack</p>
          <p className="text-body text-text-primary font-mono">
            {activePolicyPackId ?? 'No active policy pack'}
          </p>
          {activePolicyPackId !== null && (
            <p className="text-caption text-text-tertiary">
              No policy pack registry endpoint exists yet to resolve this to a name.
            </p>
          )}
        </div>

        <div className="border-border-subtle grid grid-cols-2 gap-4 border-t pt-3 sm:grid-cols-4">
          <div>
            <p className="text-caption text-text-secondary">Findings</p>
            <p className="text-heading-section text-text-primary">{findings.length}</p>
          </div>
          <div>
            <p className="text-caption text-text-secondary">Evaluated</p>
            <p className="text-heading-section text-text-primary">{evaluatedCount}</p>
          </div>
          <div>
            <p className="text-caption text-text-secondary">Awaiting judgment</p>
            <p className="text-heading-section text-text-primary">{awaitingJudgmentCount}</p>
          </div>
          <div>
            <p className="text-caption text-text-secondary">Resolved</p>
            <p className="text-heading-section text-text-primary">
              {findings.length - awaitingJudgmentCount}
            </p>
          </div>
        </div>
      </div>

      <div className="border-feedback-warning-border bg-feedback-warning-bg rounded-container border p-4">
        <p className="text-caption text-feedback-warning-fg">
          This workspace shows findings that were flagged during policy evaluation. It cannot show
          checks that passed silently, individual rule names, or rule-level rationale — no such
          data exists in the backend today.
        </p>
      </div>

      {findings.length === 0 ? (
        <EmptyState title="No findings to evaluate against policy yet" />
      ) : (
        groups.map((group) => (
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
                {group.awaitingJudgmentCount > 0 &&
                  ` · ${String(group.awaitingJudgmentCount)} awaiting judgment`}
              </span>
            </div>
            <ul className="flex flex-col gap-1 p-3">
              {group.findings.map((finding) => (
                <li
                  key={finding.id}
                  className="border-border-subtle flex flex-col gap-1.5 border-b pb-3 last:border-b-0 last:pb-0"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="text-body text-text-primary">{finding.what}</span>
                    <span className={cn('text-caption font-medium', STATE_CLASS_NAME[finding.state])}>
                      {STATE_LABEL[finding.state]}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {finding.evidenceRefs.map((evidenceId) => {
                      const item = evidenceById.get(evidenceId);
                      return (
                        <EvidenceChip
                          key={evidenceId}
                          label={item !== undefined ? item.evidenceType : 'Evidence'}
                          onClick={
                            item !== undefined
                              ? () => {
                                  onEvidenceChipActivate({
                                    documentId: item.documentId,
                                    pageNumber: item.pageNumber ?? 1,
                                    boundingBox: item.fieldLocation?.boundingBox ?? null,
                                    label: item.evidenceType,
                                  });
                                }
                              : undefined
                          }
                          disabled={item === undefined}
                        />
                      );
                    })}
                    <button
                      type="button"
                      onClick={() => {
                        onViewFinding(finding.id);
                      }}
                      className="text-caption text-text-secondary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                    >
                      View finding →
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </div>
  );
}

/**
 * Timeline region (Product Experience phase, Phase 9) — "the Timeline
 * should evolve beyond an audit log into the application's case history."
 * A pure client-side transform (`buildApplicationTimeline`) of the exact
 * same data `AuditTimeline`/`useAuditTrail` already fetch — not a second
 * source of truth. `AuditTimeline` itself, mounted in `OverviewRegion`'s
 * "Activity" card, is completely unchanged: it remains the immutable,
 * verbatim compliance record, one click away.
 *
 * Trace actions reuse the exact same `activateEvidenceJump`/`viewFinding`
 * callbacks every other region already receives — a document trace builds
 * a plain `DocumentJumpTarget` (page 1, no highlight, since a timeline
 * entry doesn't concern a specific field location) through the same
 * mechanism Evidence/Findings/Policy chips already use.
 */
function TimelineRegion({
  applicationId,
  onEvidenceChipActivate,
  onViewFinding,
}: {
  applicationId: string;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
  onViewFinding: (findingId: string) => void;
}) {
  const auditQuery = useAuditTrail(applicationId);
  const documentsQuery = useDocumentsForApplication(applicationId);
  const findingsQuery = useFindingsForApplication(applicationId);

  if (auditQuery.isPending) return <LoadingState label="Loading case history…" />;
  if (auditQuery.isError) {
    return (
      <ErrorState
        title="Could not load case history"
        onRetry={() => {
          void auditQuery.refetch();
        }}
      />
    );
  }

  const documents = documentsQuery.data ?? [];
  const documentsById = new Map(documents.map((doc) => [doc.id, doc]));
  const timeline = buildApplicationTimeline(auditQuery.data, documents, findingsQuery.data ?? []);

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-heading-section text-text-primary">Timeline</h2>
      <ApplicationTimeline
        entries={timeline}
        onTraceDocument={(documentId) => {
          const filename = documentsById.get(documentId)?.filename ?? 'Document';
          onEvidenceChipActivate({ documentId, pageNumber: 1, boundingBox: null, label: filename });
        }}
        onTraceFinding={onViewFinding}
      />
    </div>
  );
}

/**
 * Overview region (UX audit §5) — a header row (loan number as page title,
 * a refresh action, and the lifecycle-status label using the exact
 * `FindingCard`-precedented plain-colored-label pattern, never
 * `StatusBadge`), a fact-summary grid of every field the Application entity
 * already returns, and an "Activity" card wrapping the audit trail — two
 * grouped sections instead of a bare heading, per the reference-frontend
 * and Stripe/Vercel-Dashboard-benchmark "header + grouped facts" pattern
 * (see the UX audit doc, §3/§4).
 */
function OverviewRegion({
  applicationId,
  application,
  onRegionChange,
}: {
  applicationId: string;
  application: Application;
  onRegionChange: (region: WorkspaceRegion) => void;
}) {
  const applicationQuery = useApplication(applicationId);
  const documentsQuery = useDocumentsForApplication(applicationId);
  const findingsQuery = useFindingsForApplication(applicationId);

  const summaryItems: SummaryGridItem[] = [
    { label: 'Loan Number', value: application.loanNumber ?? '—', tabular: true },
    { label: 'LOS Reference', value: application.losReference ?? '—', tabular: true },
    { label: 'Parties', value: application.partyCount },
    { label: 'Created', value: new Date(application.createdAt).toLocaleString() },
    {
      label: 'Last Updated',
      value:
        application.updatedAt !== null ? new Date(application.updatedAt).toLocaleString() : '—',
    },
  ];

  return (
    <section aria-label="Overview" className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h2 className="text-heading-page text-text-primary">
            Application {application.loanNumber ?? application.id}
          </h2>
          <span
            className={`text-caption border-border-subtle rounded-chip border px-2 py-0.5 font-medium ${APPLICATION_STATUS_CLASS_NAME[application.status]}`}
          >
            {APPLICATION_STATUS_LABEL[application.status]}
          </span>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void applicationQuery.refetch();
          }}
        >
          Refresh
        </Button>
      </div>

      {documentsQuery.data !== undefined && (
        <div className="border-border-subtle bg-surface-raised rounded-container flex flex-col gap-3 border p-5">
          <h3 className="text-heading-section text-text-primary">Processing Pipeline</h3>
          <ProcessingPipeline
            steps={deriveApplicationStages(documentsQuery.data, findingsQuery.data ?? [])}
            size="md"
          />
          <DocumentAggregateSummary counts={summarizeDocuments(documentsQuery.data)} />
        </div>
      )}

      <SummaryGrid items={summaryItems} />

      <div className="border-border-subtle bg-surface-raised rounded-container border p-5">
        <h3 className="text-heading-section text-text-primary mb-3">Borrowers</h3>
        <BorrowersSummary applicationId={applicationId} />
      </div>

      <div className="border-border-subtle bg-surface-raised rounded-container border p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-heading-section text-text-primary">Activity</h3>
          <button
            type="button"
            onClick={() => {
              onRegionChange('timeline');
            }}
            className="text-caption text-text-secondary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
          >
            View full timeline →
          </button>
        </div>
        <AuditTimeline applicationId={applicationId} />
      </div>
    </section>
  );
}

/** Aggregate document counts (Product Experience phase, Phase 4) — real counts, computed client-side from `useDocumentsForApplication`. */
function DocumentAggregateSummary({
  counts,
}: {
  counts: { readonly total: number; readonly ready: number; readonly processing: number; readonly failed: number };
}) {
  if (counts.total === 0) return null;
  return (
    <p className="text-caption text-text-secondary">
      {counts.ready} of {counts.total} document{counts.total === 1 ? '' : 's'} ready
      {counts.processing > 0 && ` · ${String(counts.processing)} processing`}
      {counts.failed > 0 && (
        <span className="text-feedback-error-fg"> · {counts.failed} failed</span>
      )}
    </p>
  );
}

/**
 * Borrowers card (Product Experience phase, Phase 2) — reflects the parties
 * captured by the intake wizard (`features/application-intake/`). Kept as a
 * small supplementary panel rather than a full region: party counts are
 * typically small and read-only here (editing parties post-creation is out
 * of this phase's scope).
 */
function BorrowersSummary({ applicationId }: { applicationId: string }) {
  const partiesQuery = usePartiesForApplication(applicationId);

  if (partiesQuery.isPending) return <LoadingState label="Loading borrowers…" />;
  if (partiesQuery.isError) {
    return (
      <ErrorState
        title="Could not load borrowers"
        onRetry={() => {
          void partiesQuery.refetch();
        }}
      />
    );
  }
  if (partiesQuery.data.length === 0) {
    return <EmptyState title="No borrowers registered yet" />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {partiesQuery.data.map((party) => (
        <li key={party.id} className="flex items-center gap-2">
          <span className="text-caption border-border-default text-text-secondary rounded-chip border px-2 py-0.5">
            {PARTY_TYPE_LABEL[party.partyType]}
          </span>
          <span className="text-body text-text-primary">{party.displayName}</span>
        </li>
      ))}
    </ul>
  );
}
