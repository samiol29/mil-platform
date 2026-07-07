import type { Meta, StoryObj } from '@storybook/react-vite';

import { Dropzone } from './Dropzone';

const meta: Meta<typeof Dropzone> = {
  title: 'Design System/Dropzone',
  component: Dropzone,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof Dropzone>;

export const Default: Story = {
  args: { onFilesSelected: () => undefined },
};

export const Disabled: Story = {
  args: { onFilesSelected: () => undefined, disabled: true },
};
