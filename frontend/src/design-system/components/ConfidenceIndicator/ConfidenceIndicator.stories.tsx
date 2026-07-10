import type { Meta, StoryObj } from '@storybook/react-vite';

import { ConfidenceIndicator } from './ConfidenceIndicator';

const meta: Meta<typeof ConfidenceIndicator> = {
  title: 'Design System/ConfidenceIndicator',
  component: ConfidenceIndicator,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof ConfidenceIndicator>;

export const High: Story = { args: { level: 'high' } };
export const Medium: Story = { args: { level: 'medium' } };
export const Low: Story = { args: { level: 'low' } };

export const AllBands: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      <ConfidenceIndicator level="high" />
      <ConfidenceIndicator level="medium" />
      <ConfidenceIndicator level="low" />
    </div>
  ),
};
