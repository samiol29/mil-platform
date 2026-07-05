import type { Meta, StoryObj } from '@storybook/react-vite';

import { EvidenceChip } from './EvidenceChip';

const meta: Meta<typeof EvidenceChip> = {
  title: 'Design System/EvidenceChip',
  component: EvidenceChip,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof EvidenceChip>;

export const Default: Story = {
  args: {
    label: 'Pay Stub — Page 2',
    onClick: () => {
      // Storybook demonstration only.
    },
  },
};

export const Disabled: Story = {
  args: {
    label: 'Pay Stub — Page 2',
    disabled: true,
  },
};
