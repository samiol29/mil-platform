/**
 * Table (spec 003 T031, FR-054) — the single virtualized table primitive
 * used by every data surface in the product (Application Queue, Evidence
 * Explorer list view, Audit Trail, Notifications — plan.md Table
 * Virtualization). A TanStack Table (headless model/sorting) + TanStack
 * Virtual (windowed row rendering) composition: the full dataset is never
 * held in the DOM at once, at any scale (plan.md: "an architectural
 * invariant," not an optimization applied only where convenient).
 *
 * Standard treatment applied identically regardless of data type (FR-054):
 * a fixed row height (`rowHeightPx`, default 40px — an expert, all-day,
 * data-dense default per FR-017, not a consumer-app default), a sticky
 * header with a consistent sort-indicator icon, and a selection-state
 * treatment (`selectedRowId`) using both a background color AND an
 * `aria-selected` attribute — never color alone.
 */

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ChevronDown, ChevronsUpDown, ChevronUp } from 'lucide-react';
import { useRef, useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';

export interface TableProps<TData> {
  readonly data: readonly TData[];
  readonly columns: ColumnDef<TData>[];
  readonly getRowId?: (row: TData, index: number) => string;
  readonly onRowClick?: (row: TData) => void;
  readonly selectedRowId?: string;
  readonly rowHeightPx?: number;
  /** Rendered when `data` is empty — typically an `<EmptyState>`. */
  readonly emptyState?: ReactNode;
  readonly ariaLabel: string;
  readonly className?: string;
}

export function Table<TData>({
  data,
  columns,
  getRowId,
  onRowClick,
  selectedRowId,
  rowHeightPx = 40,
  emptyState,
  ariaLabel,
  className,
}: TableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const table = useReactTable({
    data: data as TData[],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    ...(getRowId !== undefined ? { getRowId } : {}),
  });

  const rows = table.getRowModel().rows;

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => rowHeightPx,
    overscan: 10,
  });

  const virtualRows = virtualizer.getVirtualItems();
  const totalHeight = virtualizer.getTotalSize();
  const paddingTop = virtualRows[0]?.start ?? 0;
  const paddingBottom = totalHeight - (virtualRows[virtualRows.length - 1]?.end ?? totalHeight);

  function handleRowActivate(row: TData) {
    onRowClick?.(row);
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLDivElement>, row: TData) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleRowActivate(row);
    }
  }

  if (data.length === 0 && emptyState !== undefined) {
    return <div className={className}>{emptyState}</div>;
  }

  return (
    <div
      ref={scrollRef}
      role="table"
      aria-label={ariaLabel}
      aria-rowcount={rows.length}
      className={cn(
        'border-border-subtle relative overflow-auto rounded-container border',
        className,
      )}
    >
      <div
        role="rowgroup"
        className="bg-surface-secondary border-border-subtle sticky top-0 z-10 border-b"
      >
        {table.getHeaderGroups().map((headerGroup) => (
          <div key={headerGroup.id} role="row" className="flex" style={{ height: rowHeightPx }}>
            {headerGroup.headers.map((header) => {
              const sortState = header.column.getIsSorted();
              const canSort = header.column.getCanSort();
              return (
                <div
                  key={header.id}
                  role="columnheader"
                  aria-sort={
                    sortState === 'asc' ? 'ascending' : sortState === 'desc' ? 'descending' : 'none'
                  }
                  className="text-label flex flex-1 items-center gap-1 px-3 text-text-secondary select-none"
                >
                  {canSort ? (
                    <button
                      type="button"
                      onClick={header.column.getToggleSortingHandler()}
                      className="hover:text-text-primary inline-flex items-center gap-1 outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                      {sortState === 'asc' && <ChevronUp className="size-3.5" aria-hidden="true" />}
                      {sortState === 'desc' && (
                        <ChevronDown className="size-3.5" aria-hidden="true" />
                      )}
                      {sortState === false && (
                        <ChevronsUpDown className="size-3.5 opacity-40" aria-hidden="true" />
                      )}
                    </button>
                  ) : header.isPlaceholder ? null : (
                    flexRender(header.column.columnDef.header, header.getContext())
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <div role="rowgroup" style={{ height: totalHeight, position: 'relative' }}>
        <div style={{ height: paddingTop }} />
        {virtualRows.map((virtualRow) => {
          const row = rows[virtualRow.index];
          const isSelected = selectedRowId !== undefined && row.id === selectedRowId;
          const isInteractive = onRowClick !== undefined;
          return (
            <div
              key={row.id}
              role="row"
              aria-selected={isSelected}
              tabIndex={isInteractive ? 0 : undefined}
              onClick={
                isInteractive
                  ? () => {
                      handleRowActivate(row.original);
                    }
                  : undefined
              }
              onKeyDown={
                isInteractive
                  ? (event) => {
                      handleRowKeyDown(event, row.original);
                    }
                  : undefined
              }
              className={cn(
                'border-border-subtle flex items-center border-b',
                // Selected state (Product Experience phase, Phase 11): a
                // brand left edge + subtle fill — unmistakable without
                // washing the whole row in color.
                isSelected
                  ? 'border-l-interactive-primary-default bg-surface-secondary border-l-2'
                  : 'border-l-2 border-l-transparent',
                isInteractive &&
                  'hover:bg-surface-secondary cursor-pointer outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:-outline-offset-2',
              )}
              style={{ height: rowHeightPx }}
            >
              {row.getVisibleCells().map((cell) => (
                <div key={cell.id} role="cell" className="text-body flex-1 truncate px-3">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </div>
              ))}
            </div>
          );
        })}
        <div style={{ height: paddingBottom }} />
      </div>
    </div>
  );
}
