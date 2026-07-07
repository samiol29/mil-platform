import type { Meta, StoryObj } from '@storybook/react-vite';

import { Select } from './Select';

const meta: Meta<typeof Select> = {
  title: 'Design System/Select',
  component: Select,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof Select>;

const ROLE_OPTIONS = ['UNDERWRITER', 'VERIFICATION_OFFICER', 'RISK_ANALYST'] as const;

export const Default: Story = {
  render: (args) => (
    <Select {...args} aria-label="Escalate to">
      {ROLE_OPTIONS.map((role) => (
        <option key={role} value={role}>
          {role}
        </option>
      ))}
    </Select>
  ),
};

export const Disabled: Story = {
  render: (args) => (
    <Select {...args} aria-label="Escalate to" disabled>
      {ROLE_OPTIONS.map((role) => (
        <option key={role} value={role}>
          {role}
        </option>
      ))}
    </Select>
  ),
};

export const Invalid: Story = {
  render: (args) => (
    <Select {...args} aria-label="Escalate to" invalid>
      <option value="">Select a role…</option>
      {ROLE_OPTIONS.map((role) => (
        <option key={role} value={role}>
          {role}
        </option>
      ))}
    </Select>
  ),
};
