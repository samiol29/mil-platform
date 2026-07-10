import type { Meta, StoryObj } from '@storybook/react-vite';

import { SummaryGrid } from './SummaryGrid';

const meta: Meta<typeof SummaryGrid> = {
  title: 'Design System/SummaryGrid',
  component: SummaryGrid,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof SummaryGrid>;

export const ApplicationSummary: Story = {
  args: {
    items: [
      { label: 'Loan Number', value: '0091-4471-02', tabular: true },
      { label: 'LOS Reference', value: 'LOS-88213', tabular: true },
      { label: 'Parties', value: '2' },
      { label: 'Created', value: 'Jul 2, 2026, 9:14 AM' },
      { label: 'Last Updated', value: 'Jul 6, 2026, 4:52 PM' },
    ],
  },
};

export const SingleItem: Story = {
  args: {
    items: [{ label: 'Parties', value: '1' }],
  },
};

export const MissingValues: Story = {
  args: {
    items: [
      { label: 'Loan Number', value: '—' },
      { label: 'LOS Reference', value: '—' },
    ],
  },
};
