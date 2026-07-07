import type { Meta, StoryObj } from '@storybook/react-vite';

import { Input } from './Input';

const meta: Meta<typeof Input> = {
  title: 'Design System/Input',
  component: Input,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof Input>;

export const Default: Story = {
  args: { 'aria-label': 'Corrected value', placeholder: 'Corrected value' },
};

export const WithValue: Story = {
  args: { 'aria-label': 'Corrected value', defaultValue: '$412,000' },
};

export const Disabled: Story = {
  args: { 'aria-label': 'Corrected value', defaultValue: 'Not editable', disabled: true },
};

export const Invalid: Story = {
  args: {
    'aria-label': 'Corrected value',
    defaultValue: '',
    invalid: true,
    placeholder: 'The corrected value is required.',
  },
};
