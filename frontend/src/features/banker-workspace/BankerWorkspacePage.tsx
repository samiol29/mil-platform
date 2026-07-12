/**
 * RM / Banker Workspace (spec 005-enterprise-platform §1, Wave 2).
 *
 * The Relationship Manager's own landing surface — a portfolio of the
 * applications they own (`GET /v1/rm/portfolio`, backed by the new
 * Assignment bounded context), plus a "New Application" entry point that
 * reuses the *existing*, already-built `IntakeWizard` (`uiStore
 * .openIntakeWizard()`) rather than a second intake flow — Wave 1/MVP
 * already delivered application creation + borrower intake in full.
 *
 * Deliberately read-plus-originate, not a second review surface: this page
 * does not render Findings/Evidence/Policy detail — an RM's own workspace
 * is about portfolio visibility and getting a case started, not case
 * review (that stays the Underwriter Workspace, unmodified).
 */

import { useNavigate } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import { Table } from '@design-system/components/Table';
import type { Application } from '@entities/application/types';
import {
  APPLICATION_STATUS_CHIP_BASE_CLASS,
  APPLICATION_STATUS_CHIP_CLASS_NAME,
  APPLICATION_STATUS_LABEL,
} from '@entities/application/statusLabel';
import { useRmPortfolio } from '@entities/assignment/queries';

function ageInDays(createdAt: string): number {
  return Math.max(
    0,
    Math.floor((Date.now() - new Date(createdAt).getTime()) / (1000 * 60 * 60 * 24)),
  );
}

export function BankerWorkspacePage() {
  const portfolioQuery = useRmPortfolio();
  const openIntakeWizard = useUiStore((state) => state.openIntakeWizard);
  const navigate = useNavigate();

  const columns: ColumnDef<Application>[] = [
    {
      id: 'reference',
      header: 'Loan # / LOS Ref',
      accessorFn: (app) => app.loanNumber ?? app.losReference ?? app.id,
      cell: (info) => <span className="tabular-nums">{info.getValue<string>()}</span>,
    },
    {
      id: 'status',
      header: 'Stage',
      cell: (info) => {
        const status = info.row.original.status;
        return (
          <span
            className={`${APPLICATION_STATUS_CHIP_BASE_CLASS} ${APPLICATION_STATUS_CHIP_CLASS_NAME[status]}`}
          >
            {APPLICATION_STATUS_LABEL[status]}
          </span>
        );
      },
    },
    {
      id: 'parties',
      header: 'Parties',
      accessorFn: (app) => app.partyCount,
    },
    {
      id: 'age',
      header: 'Age',
      cell: (info) => `${String(ageInDays(info.row.original.createdAt))}d`,
    },
  ];

  if (portfolioQuery.isPending) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (portfolioQuery.isError) {
    return (
      <ErrorState
        title="Failed to load your portfolio"
        description={
          portfolioQuery.error instanceof Error ? portfolioQuery.error.message : 'Unknown error'
        }
        onRetry={() => void portfolioQuery.refetch()}
      />
    );
  }

  const applications = portfolioQuery.data.items;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-heading">My Portfolio</h2>
        <Button variant="primary" onClick={openIntakeWizard}>
          New Application
        </Button>
      </div>
      <Table
        ariaLabel="My portfolio"
        data={applications}
        columns={columns}
        getRowId={(app) => app.id}
        onRowClick={(app) => {
          void navigate({
            to: '/applications/$applicationId',
            params: { applicationId: app.id },
            search: { region: 'overview' },
          });
        }}
        emptyState={
          <EmptyState
            title="No applications in your portfolio yet"
            description="Originate a new application to get started — it will appear here once assigned to you."
          />
        }
      />
    </div>
  );
}
