import type { Meta, StoryObj } from '@storybook/react-vite';

import { StatusBadge } from './StatusBadge';

const meta: Meta<typeof StatusBadge> = {
  title: 'Design System/StatusBadge',
  component: StatusBadge,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof StatusBadge>;

export const OnTrack: Story = { args: { status: 'onTrack' } };
export const AtRisk: Story = { args: { status: 'atRisk' } };
export const Overdue: Story = { args: { status: 'overdue' } };
export const Blocked: Story = { args: { status: 'blocked' } };

export const AllStates: Story = {
  render: () => (
    <div className="flex gap-3">
      <StatusBadge status="onTrack" />
      <StatusBadge status="atRisk" />
      <StatusBadge status="overdue" />
      <StatusBadge status="blocked" />
    </div>
  ),
};
