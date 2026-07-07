/**
 * Application Queue table (Product Experience phase, Phase 1) — the
 * detailed operational view at `/applications`, replacing the fact that no
 * such view existed at all before this phase. Built around the field-
 * availability audit in the implementation plan: every column below is
 * either backed by a real `Application` field, a client-side derivation
 * from one (`Age`), or an explicit muted "—" placeholder for a field the
 * backend doesn't compute yet — never a guessed value.
 *
 * Uses the existing virtualized `Table` primitive
 * (`design-system/components/Table`) and `useApplicationSearch`
 * (`entities/application/queries.ts`), which already wires the backend's
 * `search`/`status` query params — no new query infrastructure here.
 *
 * `status` is owned by the route (`routes/applications.index.tsx`), the
 * same "active filter is URL state" convention
 * `applications.$applicationId.tsx` uses for its region — this lets a
 * Dashboard workload card link straight into a pre-filtered queue. The
 * free-text search box stays local component state (not URL state): it is
 * highly transient per-keystroke input, unlike a deliberate filter choice.
 */

import { useNavigate } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { Plus, Search } from 'lucide-react';
import { useState } from 'react';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Input } from '@design-system/components/Input';
import { Skeleton } from '@design-system/components/LoadingState';
import { Table } from '@design-system/components/Table';
import { cn } from '@design-system/lib/cn';
import { useApplicationSearch } from '@entities/application/queries';
import { APPLICATION_STATUS_CLASS_NAME, APPLICATION_STATUS_LABEL } from '@entities/application/statusLabel';
import type { Application, ApplicationStatus } from '@entities/application/types';

import { STATUS_FILTERS } from './filters';

function ageInDays(createdAt: string): number {
  const created = new Date(createdAt).getTime();
  const now = Date.now();
  return Math.max(0, Math.floor((now - created) / (1000 * 60 * 60 * 24)));
}

function formatDate(value: string | null): string {
  if (value === null) return '—';
  return new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

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
    accessorFn: (app) => app.status,
    cell: (info) => {
      const status = info.getValue<ApplicationStatus>();
      return (
        <span className={cn('text-label font-medium', APPLICATION_STATUS_CLASS_NAME[status])}>
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
    accessorFn: (app) => ageInDays(app.createdAt),
    cell: (info) => <span className="tabular-nums">{info.getValue<number>()}d</span>,
  },
  {
    id: 'updatedAt',
    header: 'Last Updated',
    accessorFn: (app) => app.updatedAt ?? app.createdAt,
    cell: (info) => formatDate(info.getValue<string>()),
  },
  {
    id: 'riskLevel',
    header: 'Risk',
    // Backend-dependent (see filters.ts's RESERVED_FILTERS) — no `Application.risk_level`
    // field exists yet. Rendered explicitly rather than omitted so the column layout
    // already reflects the target design.
    cell: () => (
      <span className="text-text-tertiary" title="Not yet available from the backend">
        —
      </span>
    ),
  },
];

export interface ApplicationQueueTableProps {
  readonly status: ApplicationStatus | null;
  readonly onStatusChange: (status: ApplicationStatus | null) => void;
}

export function ApplicationQueueTable({ status, onStatusChange }: ApplicationQueueTableProps) {
  const navigate = useNavigate();
  const openIntakeWizard = useUiStore((state) => state.openIntakeWizard);
  const [search, setSearch] = useState('');

  const applicationsQuery = useApplicationSearch({
    search: search.length > 0 ? search : undefined,
    status: status ?? undefined,
  });

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-heading-page text-text-primary">Application Queue</h1>
        <Button variant="primary" onClick={openIntakeWizard}>
          <Plus className="size-4" aria-hidden="true" />
          New Application
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search
            className="text-text-tertiary pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
            aria-hidden="true"
          />
          <Input
            type="search"
            placeholder="Search by borrower, loan #, LOS ref…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
            }}
            className="pl-9"
            aria-label="Search applications"
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by stage">
          <FilterChip
            label="All"
            isActive={status === null}
            onClick={() => {
              onStatusChange(null);
            }}
          />
          {STATUS_FILTERS.map((option) => (
            <FilterChip
              key={option.value}
              label={option.label}
              isActive={status === option.value}
              onClick={() => {
                onStatusChange(option.value);
              }}
            />
          ))}
        </div>
      </div>

      {applicationsQuery.isPending && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      )}

      {applicationsQuery.isError && (
        <ErrorState
          title="Could not load the queue"
          onRetry={() => {
            void applicationsQuery.refetch();
          }}
        />
      )}

      {applicationsQuery.isSuccess && (
        <Table
          ariaLabel="Application queue"
          data={applicationsQuery.data.items}
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
              title={search.length > 0 || status !== null ? 'No matching applications' : 'No applications yet'}
              description={
                search.length > 0 || status !== null
                  ? 'Try a different search term or clear the stage filter.'
                  : 'Applications created in the Loan Origination System will appear here.'
              }
            />
          }
        />
      )}
    </div>
  );
}

function FilterChip({
  label,
  isActive,
  onClick,
}: {
  readonly label: string;
  readonly isActive: boolean;
  readonly onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onClick}
      className={cn(
        'text-caption rounded-chip border px-2.5 py-1 font-medium transition-colors duration-micro ease-standard',
        'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
        isActive
          ? 'bg-interactive-primary-default text-text-on-brand border-transparent'
          : 'border-border-default text-text-secondary hover:bg-surface-secondary',
      )}
    >
      {label}
    </button>
  );
}
