import type { Meta, StoryObj } from '@storybook/react-vite';

import { Skeleton, SkeletonRow, SkeletonText } from './SkeletonState';

const meta: Meta = {
  title: 'Design System/SkeletonState',
  parameters: { layout: 'padded' },
};
export default meta;

export const Block: StoryObj<typeof Skeleton> = {
  render: () => <Skeleton className="h-24 w-64" />,
};

export const TextSingleLine: StoryObj<typeof SkeletonText> = {
  render: () => <SkeletonText />,
};

export const TextMultiLine: StoryObj<typeof SkeletonText> = {
  render: () => <SkeletonText lines={3} />,
};

export const Row: StoryObj<typeof SkeletonRow> = {
  render: () => (
    <div className="w-full max-w-2xl">
      <SkeletonRow columns={5} />
      <SkeletonRow columns={5} />
      <SkeletonRow columns={5} />
    </div>
  ),
};
