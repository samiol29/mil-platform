import type { Meta, StoryObj } from '@storybook/react-vite';

import { Textarea } from './Textarea';

const meta: Meta<typeof Textarea> = {
  title: 'Design System/Textarea',
  component: Textarea,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof Textarea>;

export const Default: Story = {
  args: { 'aria-label': 'Reason', placeholder: 'Explain why this finding is being overridden.' },
};

export const Disabled: Story = {
  args: { 'aria-label': 'Reason', defaultValue: 'Not editable', disabled: true },
};

export const Invalid: Story = {
  args: {
    'aria-label': 'Reason',
    defaultValue: '',
    invalid: true,
    placeholder: 'A reason is required.',
  },
};
