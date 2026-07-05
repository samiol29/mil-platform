import type { Meta, StoryObj } from '@storybook/react-vite';

import { ErrorState } from './ErrorState';

const meta: Meta<typeof ErrorState> = {
  title: 'Design System/ErrorState',
  component: ErrorState,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof ErrorState>;

export const Default: Story = {};

export const WithRetry: Story = {
  args: {
    onRetry: () => {
      // Storybook demonstration only.
    },
  },
};

export const WithTechnicalDetails: Story = {
  args: {
    onRetry: () => {
      // Storybook demonstration only.
    },
    details: 'GET /v1/applications/123/findings — 503 Service Unavailable',
  },
};

export const CustomMessage: Story = {
  args: {
    title: 'Evidence could not be loaded',
    description: 'The source document may still be processing. Try again in a moment.',
  },
};
