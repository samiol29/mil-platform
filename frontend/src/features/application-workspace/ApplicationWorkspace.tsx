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
 * Clicking an evidence chip in the Findings region switches to the
 * Documents region and jumps the viewer directly to that evidence's page
 * and highlight (FR-039) — `jumpTarget` is lifted to this component since
 * it coordinates between the two regions.
 */

import { useState } from 'react';

import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { SummaryGrid, type SummaryGridItem } from '@design-system/components/SummaryGrid';
import type { Application } from '@entities/application/queries';
import { useApplication } from '@entities/application/queries';
import {
  APPLICATION_STATUS_CLASS_NAME,
  APPLICATION_STATUS_LABEL,
} from '@entities/application/statusLabel';
import { useEvidenceForApplication } from '@entities/evidence/queries';
import { useFindingsForApplication } from '@entities/finding/queries';
import { usePartiesForApplication } from '@entities/party/queries';
import { PARTY_TYPE_LABEL } from '@entities/party/types';
import { DocumentViewer, type DocumentJumpTarget } from '@features/document-viewer/DocumentViewer';
import { PanelErrorBoundary } from '@shared/errors/PanelErrorBoundary';

import { AuditTimeline } from './AuditTimeline';
import { FindingActions } from './FindingActions';
import { FindingCard } from './FindingCard';
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

  return (
    <div className="flex flex-col gap-4 p-6">
      <nav
        aria-label="Application Workspace sections"
        className="border-border-subtle flex gap-1 border-b"
      >
        {WORKSPACE_REGIONS.map((candidate) => (
          <button
            key={candidate}
            type="button"
            role="tab"
            aria-selected={candidate === region}
            onClick={() => {
              onRegionChange(candidate);
            }}
            className={
              candidate === region
                ? 'text-label border-interactive-primary-default text-text-primary border-b-2 px-3 py-2 font-medium'
                : 'text-label text-text-secondary hover:text-text-primary border-b-2 border-transparent px-3 py-2'
            }
          >
            {REGION_LABEL[candidate]}
          </button>
        ))}
      </nav>

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
              <OverviewRegion applicationId={applicationId} application={applicationQuery.data} />
            </PanelErrorBoundary>
          )}

          {region === 'findings' && (
            <PanelErrorBoundary panelName="Findings">
              <FindingsRegion
                applicationId={applicationId}
                readOnly={readOnly}
                onEvidenceChipActivate={(jump) => {
                  setJumpTarget(jump);
                  onRegionChange('documents');
                }}
              />
            </PanelErrorBoundary>
          )}

          {region === 'evidence' && (
            <PanelErrorBoundary panelName="Evidence">
              <EvidenceRegion applicationId={applicationId} />
            </PanelErrorBoundary>
          )}

          {region === 'documents' && (
            <PanelErrorBoundary panelName="Documents">
              <DocumentViewer applicationId={applicationId} jumpTarget={jumpTarget} />
            </PanelErrorBoundary>
          )}
        </>
      )}
    </div>
  );
}

function FindingsRegion({
  applicationId,
  readOnly,
  onEvidenceChipActivate,
}: {
  applicationId: string;
  readOnly: boolean;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
}) {
  const findingsQuery = useFindingsForApplication(applicationId);
  const evidenceQuery = useEvidenceForApplication(applicationId);

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
        <FindingCard
          key={finding.id}
          finding={finding}
          evidenceItems={evidenceItems}
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
      ))}
    </div>
  );
}

function EvidenceRegion({ applicationId }: { applicationId: string }) {
  const evidenceQuery = useEvidenceForApplication(applicationId);

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

  const items: SummaryGridItem[] = evidenceQuery.data.map((item) => ({
    id: item.id,
    label: item.evidenceType,
    value: item.valueText ?? item.valueNumeric ?? '—',
    tabular: item.valueNumeric !== null,
  }));

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-heading-section text-text-primary">Evidence</h2>
      <SummaryGrid items={items} />
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
}: {
  applicationId: string;
  application: Application;
}) {
  const applicationQuery = useApplication(applicationId);

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

      <SummaryGrid items={summaryItems} />

      <div className="border-border-subtle bg-surface-raised rounded-container border p-5">
        <h3 className="text-heading-section text-text-primary mb-3">Borrowers</h3>
        <BorrowersSummary applicationId={applicationId} />
      </div>

      <div className="border-border-subtle bg-surface-raised rounded-container border p-5">
        <h3 className="text-heading-section text-text-primary mb-3">Activity</h3>
        <AuditTimeline applicationId={applicationId} />
      </div>
    </section>
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
