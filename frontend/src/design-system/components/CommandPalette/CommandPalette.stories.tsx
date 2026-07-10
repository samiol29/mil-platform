import type { Meta, StoryObj } from '@storybook/react-vite';
import { useState } from 'react';

import { Button } from '@design-system/components/Button';

import { CommandGroup, CommandItem, CommandPalette } from './CommandPalette';

const meta: Meta<typeof CommandPalette> = {
  title: 'Design System/CommandPalette',
  component: CommandPalette,
  parameters: { layout: 'fullscreen' },
};
export default meta;

type Story = StoryObj<typeof CommandPalette>;

/**
 * Production default (tasks.md T032): the shell with no commands registered
 * yet — every query shows the empty state.
 */
export const Empty: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(true);
      return <CommandPalette open={open} onOpenChange={setOpen} />;
    }
    return <Demo />;
  },
};

/**
 * Demonstrates the shell's capacity to render registered commands (wired to
 * real commands in a later phase, tasks.md T080) — not part of this
 * component's production behavior today.
 */
export const WithSampleCommands: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(true);
      return (
        <CommandPalette open={open} onOpenChange={setOpen}>
          <CommandGroup heading="Navigation">
            <CommandItem>Go to Application Queue</CommandItem>
            <CommandItem>Go to Notifications</CommandItem>
          </CommandGroup>
        </CommandPalette>
      );
    }
    return <Demo />;
  },
};

export const ClosedTrigger: Story = {
  render: () => {
    function Demo() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <Button
            onClick={() => {
              setOpen(true);
            }}
          >
            Open Command Palette (⌘K)
          </Button>
          <CommandPalette open={open} onOpenChange={setOpen} />
        </>
      );
    }
    return <Demo />;
  },
};
