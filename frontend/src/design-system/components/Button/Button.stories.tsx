import type { Meta, StoryObj } from '@storybook/react-vite';

import { Button } from './Button';

const meta: Meta<typeof Button> = {
  title: 'Design System/Button',
  component: Button,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: { variant: 'primary', children: 'Verify Finding' },
};

export const Secondary: Story = {
  args: { variant: 'secondary', children: 'Cancel' },
};

export const Danger: Story = {
  args: { variant: 'danger', children: 'Withdraw Application' },
};

export const Disabled: Story = {
  args: { variant: 'primary', children: 'Verify Finding', disabled: true },
};

export const Loading: Story = {
  args: { variant: 'primary', children: 'Submitting…', loading: true },
};

export const Small: Story = {
  args: { variant: 'primary', size: 'sm', children: 'Small' },
};

export const Large: Story = {
  args: { variant: 'primary', size: 'lg', children: 'Large' },
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-col gap-4">
      <div className="flex gap-3">
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="danger">Danger</Button>
      </div>
      <div className="flex gap-3">
        <Button variant="primary" disabled>
          Disabled
        </Button>
        <Button variant="primary" loading>
          Loading
        </Button>
      </div>
    </div>
  ),
};
