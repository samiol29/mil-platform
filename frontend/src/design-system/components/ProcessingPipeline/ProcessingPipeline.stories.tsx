import type { Meta, StoryObj } from '@storybook/react-vite';

import { ProcessingPipeline } from './ProcessingPipeline';
import type { PipelineStep } from './ProcessingPipeline';

const meta: Meta<typeof ProcessingPipeline> = {
  title: 'Design System/ProcessingPipeline',
  component: ProcessingPipeline,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof ProcessingPipeline>;

const documentSteps: readonly PipelineStep[] = [
  { id: 'upload', label: 'Upload', status: 'complete' },
  { id: 'processing', label: 'Processing', status: 'active' },
  { id: 'evidence', label: 'Evidence', status: 'pending' },
  { id: 'ready', label: 'Ready', status: 'pending' },
];

const failedSteps: readonly PipelineStep[] = [
  { id: 'upload', label: 'Upload', status: 'complete' },
  {
    id: 'processing',
    label: 'Processing',
    status: 'failed',
    detail: 'Gemini API returned HTTP 400: The document has no pages.',
  },
  { id: 'evidence', label: 'Evidence', status: 'skipped' },
  { id: 'ready', label: 'Ready', status: 'skipped' },
];

const completeSteps: readonly PipelineStep[] = [
  { id: 'upload', label: 'Upload', status: 'complete' },
  { id: 'processing', label: 'Processing', status: 'complete' },
  { id: 'evidence', label: 'Evidence', status: 'complete' },
  { id: 'ready', label: 'Ready', status: 'complete' },
];

const applicationSteps: readonly PipelineStep[] = [
  { id: 'findings', label: 'Findings', status: 'complete' },
  { id: 'policy', label: 'Policy', status: 'complete' },
  { id: 'ready-for-review', label: 'Ready for Review (estimated)', status: 'active' },
];

export const MediumInProgress: Story = { args: { steps: documentSteps, size: 'md' } };
export const MediumComplete: Story = { args: { steps: completeSteps, size: 'md' } };
export const MediumFailed: Story = { args: { steps: failedSteps, size: 'md' } };
export const SmallCompact: Story = { args: { steps: documentSteps, size: 'sm' } };
export const ApplicationLevel: Story = { args: { steps: applicationSteps, size: 'md' } };
