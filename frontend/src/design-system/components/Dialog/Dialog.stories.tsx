import type { Meta, StoryObj } from '@storybook/react-vite';
import { useState } from 'react';

import { Button } from '@design-system/components/Button';

import { Dialog } from './Dialog';

const meta: Meta<typeof Dialog> = {
  title: 'Design System/Dialog',
  component: Dialog,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof Dialog>;

export const BlockingConfirmation: Story = {
  render: () => {
    function DialogDemo() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <Button
            onClick={() => {
              setOpen(true);
            }}
          >
            Withdraw Application
          </Button>
          <Dialog
            open={open}
            onOpenChange={setOpen}
            title="Withdraw this application?"
            description="This action cannot be undone. The application will move to a terminal WITHDRAWN state."
            primaryAction={{
              label: 'Withdraw',
              variant: 'danger',
              onClick: () => {
                setOpen(false);
              },
            }}
          />
        </>
      );
    }
    return <DialogDemo />;
  },
};

export const LoadingPrimaryAction: Story = {
  render: () => {
    function DialogDemo() {
      const [open, setOpen] = useState(true);
      return (
        <Dialog
          open={open}
          onOpenChange={setOpen}
          title="Submitting override"
          primaryAction={{ label: 'Submitting…', onClick: () => undefined, loading: true }}
        />
      );
    }
    return <DialogDemo />;
  },
};

export const NoDescription: Story = {
  render: () => {
    function DialogDemo() {
      const [open, setOpen] = useState(true);
      return (
        <Dialog
          open={open}
          onOpenChange={setOpen}
          title="Confirm action"
          primaryAction={{
            label: 'Confirm',
            onClick: () => {
              setOpen(false);
            },
          }}
        />
      );
    }
    return <DialogDemo />;
  },
};
