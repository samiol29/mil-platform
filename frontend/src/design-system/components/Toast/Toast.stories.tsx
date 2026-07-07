import type { Meta, StoryObj } from '@storybook/react-vite';

import { ToastViewport } from './Toast';

const meta: Meta<typeof ToastViewport> = {
  title: 'Design System/Toast',
  component: ToastViewport,
  parameters: { layout: 'fullscreen' },
};
export default meta;

type Story = StoryObj<typeof ToastViewport>;

export const Success: Story = {
  args: {
    toasts: [
      { id: '1', title: 'Application created', variant: 'success' },
    ],
    onDismiss: () => undefined,
  },
};

export const Error: Story = {
  args: {
    toasts: [
      {
        id: '1',
        title: 'Upload failed',
        description: '3 of 5 files could not be uploaded — check the summary for details.',
        variant: 'error',
      },
    ],
    onDismiss: () => undefined,
  },
};

export const Info: Story = {
  args: {
    toasts: [{ id: '1', title: 'Session ended', description: 'Sign back in to continue.', variant: 'info' }],
    onDismiss: () => undefined,
  },
};

export const Stacked: Story = {
  args: {
    toasts: [
      { id: '1', title: 'Application created', variant: 'success' },
      { id: '2', title: '12 documents uploaded', description: '1 flagged as a likely duplicate', variant: 'info' },
      { id: '3', title: 'Upload failed', description: 'bank-statement.pdf exceeded the size limit', variant: 'error' },
    ],
    onDismiss: () => undefined,
  },
};
