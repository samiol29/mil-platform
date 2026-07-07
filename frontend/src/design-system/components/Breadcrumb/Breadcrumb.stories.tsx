import type { Meta, StoryObj } from '@storybook/react-vite';

import { Breadcrumb } from './Breadcrumb';

const meta: Meta<typeof Breadcrumb> = {
  title: 'Design System/Breadcrumb',
  component: Breadcrumb,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof Breadcrumb>;

export const TopLevel: Story = {
  args: { items: [{ label: 'Dashboard' }] },
};

export const InWorkspace: Story = {
  args: {
    items: [
      { label: 'Dashboard', onClick: () => undefined },
      { label: 'Queue', onClick: () => undefined },
      { label: 'Loan #48213 — J. Alvarez' },
    ],
  },
};
