import type { Meta, StoryObj } from '@storybook/react-vite';
import { useState } from 'react';

import { Tabs, TabsList, TabsPanel, TabsTrigger } from './Tabs';

const meta: Meta<typeof Tabs> = {
  title: 'Design System/Tabs',
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof Tabs>;

function Demo() {
  const [value, setValue] = useState('overview');
  return (
    <Tabs value={value} onValueChange={setValue}>
      <TabsList aria-label="Example sections">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="findings">Findings</TabsTrigger>
        <TabsTrigger value="policy">Policy Checks</TabsTrigger>
      </TabsList>
      <TabsPanel value="overview" className="pt-4">
        Overview content.
      </TabsPanel>
      <TabsPanel value="findings" className="pt-4">
        Findings content.
      </TabsPanel>
      <TabsPanel value="policy" className="pt-4">
        Policy Checks content.
      </TabsPanel>
    </Tabs>
  );
}

export const Default: Story = { render: () => <Demo /> };
