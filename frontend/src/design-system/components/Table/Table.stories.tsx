import type { Meta, StoryObj } from '@storybook/react-vite';
import type { ColumnDef } from '@tanstack/react-table';

import { EmptyState } from '@design-system/components/EmptyState';
import { StatusBadge } from '@design-system/components/StatusBadge';

import { Table } from './Table';

interface DemoRow {
  id: string;
  borrowerName: string;
  loanNumber: string;
  status: 'onTrack' | 'atRisk' | 'overdue' | 'blocked';
}

const columns: ColumnDef<DemoRow>[] = [
  { accessorKey: 'borrowerName', header: 'Borrower' },
  { accessorKey: 'loanNumber', header: 'Loan Number' },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: (info) => <StatusBadge status={info.getValue() as DemoRow['status']} />,
  },
];

const rows: DemoRow[] = [
  { id: '1', borrowerName: 'Jordan Alvarez', loanNumber: '4009123456', status: 'onTrack' },
  { id: '2', borrowerName: 'Priya Chandrasekaran', loanNumber: '4009123457', status: 'atRisk' },
  { id: '3', borrowerName: 'Marcus Webb', loanNumber: '4009123458', status: 'overdue' },
  { id: '4', borrowerName: 'Sofia Reyes', loanNumber: '4009123459', status: 'blocked' },
];

const meta: Meta<typeof Table<DemoRow>> = {
  title: 'Design System/Table',
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof Table<DemoRow>>;

export const Default: Story = {
  render: () => (
    <Table
      data={rows}
      columns={columns}
      getRowId={(row) => row.id}
      ariaLabel="Sample application queue"
    />
  ),
};

export const WithSelectedRow: Story = {
  render: () => (
    <Table
      data={rows}
      columns={columns}
      getRowId={(row) => row.id}
      selectedRowId="2"
      onRowClick={() => undefined}
      ariaLabel="Sample application queue with a selected row"
    />
  ),
};

export const Empty: Story = {
  render: () => (
    <Table
      data={[]}
      columns={columns}
      ariaLabel="Empty application queue"
      emptyState={<EmptyState title="No applications found" />}
    />
  ),
};
