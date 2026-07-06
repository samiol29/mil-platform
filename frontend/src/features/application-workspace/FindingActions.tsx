/**
 * FindingActions (spec 002 tasks.md T063).
 *
 * Verify and override action controls. Both open a `Dialog` — the
 * confirming action is always a distinct second step (a "Review & Confirm"
 * button inside the dialog), never implicit in clicking the trigger button
 * or in typing a reason (FR-078). The override reason form uses React Hook
 * Form + Zod: it blocks submission while the reason is empty, and on a
 * failed submission (a rejected mutation) the entered values remain in the
 * form — React Hook Form does not clear field state on a failed
 * `handleSubmit`, so no extra recovery logic is needed for this guarantee.
 *
 * **No escalate control exists here.** See `entities/finding/queries.ts`
 * and `HANDOFF.md`: no backend endpoint exists for escalation yet.
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@design-system/components/Button';
import { Dialog } from '@design-system/components/Dialog';
import type { Finding } from '@entities/finding/queries';
import { useOverrideFinding, useVerifyFinding } from '@entities/finding/queries';

const overrideFormSchema = z.object({
  reason: z.string().min(1, 'A reason is required.'),
  previousValue: z.string(),
  newValue: z.string().min(1, 'The corrected value is required.'),
});

type OverrideFormValues = z.infer<typeof overrideFormSchema>;

export interface FindingActionsProps {
  readonly applicationId: string;
  readonly finding: Finding;
}

export function FindingActions({ applicationId, finding }: FindingActionsProps) {
  const [verifyDialogOpen, setVerifyDialogOpen] = useState(false);
  const [overrideDialogOpen, setOverrideDialogOpen] = useState(false);

  const verifyMutation = useVerifyFinding(applicationId);
  const overrideMutation = useOverrideFinding(applicationId);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<OverrideFormValues>({
    resolver: zodResolver(overrideFormSchema),
    defaultValues: { reason: '', previousValue: '', newValue: '' },
  });

  const alreadyDecided = finding.state !== 'unreviewed';

  const onOverrideSubmit = handleSubmit((values) => {
    overrideMutation.mutate(
      { findingId: finding.id, ...values },
      {
        onSuccess: () => {
          setOverrideDialogOpen(false);
        },
      },
    );
  });

  return (
    <div className="flex gap-3">
      <Button
        variant="primary"
        size="sm"
        disabled={alreadyDecided}
        onClick={() => {
          setVerifyDialogOpen(true);
        }}
      >
        Verify
      </Button>
      <Button
        variant="danger"
        size="sm"
        disabled={alreadyDecided}
        onClick={() => {
          setOverrideDialogOpen(true);
        }}
      >
        Override
      </Button>

      <Dialog
        open={verifyDialogOpen}
        onOpenChange={setVerifyDialogOpen}
        title="Verify this finding?"
        description="This records your confirmation permanently against this finding."
        primaryAction={{
          label: 'Review & Confirm',
          loading: verifyMutation.isPending,
          onClick: () => {
            verifyMutation.mutate(finding.id, {
              onSuccess: () => {
                setVerifyDialogOpen(false);
              },
            });
          },
        }}
      />

      <Dialog
        open={overrideDialogOpen}
        onOpenChange={setOverrideDialogOpen}
        title="Override this finding"
        description="Explain why this finding is being overridden. This is recorded permanently."
        primaryAction={{
          label: 'Review & Confirm',
          variant: 'danger',
          loading: overrideMutation.isPending,
          onClick: () => {
            void onOverrideSubmit();
          },
        }}
      >
        <form className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-label text-text-primary">Previous value</span>
            <input
              {...register('previousValue')}
              className="border-border-default rounded-interactive text-body bg-surface-background border px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-label text-text-primary">Corrected value</span>
            <input
              {...register('newValue')}
              className="border-border-default rounded-interactive text-body bg-surface-background border px-3 py-2"
            />
            {errors.newValue !== undefined && (
              <span className="text-caption text-text-critical">{errors.newValue.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-label text-text-primary">Reason</span>
            <textarea
              {...register('reason')}
              rows={3}
              className="border-border-default rounded-interactive text-body bg-surface-background border px-3 py-2"
            />
            {errors.reason !== undefined && (
              <span className="text-caption text-text-critical">{errors.reason.message}</span>
            )}
          </label>
        </form>
      </Dialog>
    </div>
  );
}
