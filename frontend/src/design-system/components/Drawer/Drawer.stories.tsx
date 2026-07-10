import type { Meta, StoryObj } from '@storybook/react-vite';
import { useState } from 'react';

import { Button } from '@design-system/components/Button';

import { Drawer } from './Drawer';

const meta: Meta<typeof Drawer> = {
  title: 'Design System/Drawer',
  component: Drawer,
  parameters: { layout: 'fullscreen' },
};
export default meta;

type Story = StoryObj<typeof Drawer>;

export const Right: Story = {
  render: () => {
    function DrawerDemo() {
      const [open, setOpen] = useState(false);
      return (
        <div className="p-6">
          <Button
            onClick={() => {
              setOpen(true);
            }}
          >
            Open Evidence Item
          </Button>
          <Drawer open={open} onOpenChange={setOpen} title="Evidence Item">
            <p className="text-body text-text-secondary">
              Monthly Income — $6,200.00, extracted from Pay Stub, page 2.
            </p>
          </Drawer>
        </div>
      );
    }
    return <DrawerDemo />;
  },
};

export const Left: Story = {
  render: () => {
    function DrawerDemo() {
      const [open, setOpen] = useState(true);
      return (
        <Drawer open={open} onOpenChange={setOpen} title="Filters" side="left" size="sm">
          <p className="text-body text-text-secondary">Filter controls render here.</p>
        </Drawer>
      );
    }
    return <DrawerDemo />;
  },
};

export const Large: Story = {
  render: () => {
    function DrawerDemo() {
      const [open, setOpen] = useState(true);
      return (
        <Drawer open={open} onOpenChange={setOpen} title="Relationship View" size="lg">
          <p className="text-body text-text-secondary">Knowledge graph renders here.</p>
        </Drawer>
      );
    }
    return <DrawerDemo />;
  },
};
