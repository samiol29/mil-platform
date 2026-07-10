import type { Meta, StoryObj } from '@storybook/react-vite';

import { AiSignalBadge } from './AiSignalBadge';

const meta: Meta<typeof AiSignalBadge> = {
  title: 'Design System/AiSignalBadge',
  component: AiSignalBadge,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof AiSignalBadge>;

export const Signal: Story = { args: { variant: 'signal' } };
export const Processing: Story = { args: { variant: 'processing' } };

export const BothStates: Story = {
  render: () => (
    <div className="flex gap-3">
      <AiSignalBadge variant="signal" />
      <AiSignalBadge variant="processing" />
    </div>
  ),
};
