import type { Meta, StoryObj } from '@storybook/react-vite';

import { Button } from '@design-system/components/Button';

import { EmptyState } from './EmptyState';

const meta: Meta<typeof EmptyState> = {
  title: 'Design System/EmptyState',
  component: EmptyState,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof EmptyState>;

export const Default: Story = {
  args: {
    title: 'No applications found',
  },
};

export const WithDescription: Story = {
  args: {
    title: 'No applications found',
    description: 'Try adjusting your filters or search terms.',
  },
};

export const WithAction: Story = {
  args: {
    title: 'No saved views yet',
    description: 'Save a filter combination to quickly return to it later.',
    action: <Button size="sm">Create saved view</Button>,
  },
};
