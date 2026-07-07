/**
 * FindingActions (spec 002 tasks.md T063; escalate added per the approved
 * Review/Escalation domain-design — see HANDOFF.md).
 *
 * Verify, override, and escalate action controls. All three open a
 * `Dialog` — the confirming action is always a distinct second step (a
 * "Review & Confirm" button inside the dialog), never implicit in clicking
 * the trigger button or in typing a reason (FR-078). The override and
 * escalate forms use React Hook Form + Zod: both block submission while
 * their reason is empty, and on a failed submission (a rejected mutation)
 * the entered values remain in the form — React Hook Form does not clear
 * field state on a failed `handleSubmit`, so no extra recovery logic is
 * needed for this guarantee.
 *
 * Verify/override/escalate remain enabled while `finding.state` is
 * `"unreviewed"` OR `"escalated"` — escalation is non-terminal, so an
 * escalated finding is still awaiting exactly the same resolving actions
 * (the backend enforces who may actually resolve it; disabling controls
 * here is a UX nicety, never the authorization boundary).
 *
 * Also opens in response to a Command Palette finding-action command (UX
 * audit §5): `useUiStore`'s `requestedFindingAction` is ephemeral UI state
 * (plan.md State Management) set when a palette command targeting this
 * exact finding is chosen. This effect only opens the same dialog a manual
 * button click opens — it never calls a mutation directly — so the
 * mandatory second-confirmation step (FR-078) is identical either way.
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { Dialog } from '@design-system/components/Dialog';
import { Input } from '@design-system/components/Input';
import { Select } from '@design-system/components/Select';
import { Textarea } from '@design-system/components/Textarea';
import type { Finding } from '@entities/finding/queries';
import {
  useEscalateFinding,
  useOverrideFinding,
  useVerifyFinding,
} from '@entities/finding/queries';

const overrideFormSchema = z.object({
  reason: z.string().min(1, 'A reason is required.'),
  previousValue: z.string(),
  newValue: z.string().min(1, 'The corrected value is required.'),
});

type OverrideFormValues = z.infer<typeof overrideFormSchema>;

/**
 * Roles a finding may plausibly be escalated to: holders of decision
 * authority over a finding today (UNDERWRITER, VERIFICATION_OFFICER) plus
 * the roles a compliance/risk concern would realistically go to. Excludes
 * ADMIN (a break-glass role, not a workflow target) and roles with no
 * plausible decision authority (RELATIONSHIP_MANAGER, CREDIT_ANALYST,
 * AUDIT_TEAM). Matches `src/mil/kernel/security.py`'s `Role` enum values.
 */
const ESCALATION_TARGET_ROLES = [
  'UNDERWRITER',
  'VERIFICATION_OFFICER',
  'RISK_ANALYST',
  'COMPLIANCE_OFFICER',
  'OPERATIONS_MANAGER',
] as const;

const escalateFormSchema = z.object({
  reason: z.string().min(1, 'A reason is required.'),
  targetRole: z.enum(ESCALATION_TARGET_ROLES),
});

type EscalateFormValues = z.infer<typeof escalateFormSchema>;

export interface FindingActionsProps {
  readonly applicationId: string;
  readonly finding: Finding;
}

export function FindingActions({ applicationId, finding }: FindingActionsProps) {
  const [verifyDialogOpen, setVerifyDialogOpen] = useState(false);
  const [overrideDialogOpen, setOverrideDialogOpen] = useState(false);
  const [escalateDialogOpen, setEscalateDialogOpen] = useState(false);

  const verifyMutation = useVerifyFinding(applicationId);
  const overrideMutation = useOverrideFinding(applicationId);
  const escalateMutation = useEscalateFinding(applicationId);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<OverrideFormValues>({
    resolver: zodResolver(overrideFormSchema),
    defaultValues: { reason: '', previousValue: '', newValue: '' },
  });

  const {
    register: registerEscalate,
    handleSubmit: handleEscalateSubmit,
    formState: { errors: escalateErrors },
  } = useForm<EscalateFormValues>({
    resolver: zodResolver(escalateFormSchema),
    defaultValues: { reason: '', targetRole: ESCALATION_TARGET_ROLES[0] },
  });

  const requestedFindingAction = useUiStore((state) => state.requestedFindingAction);
  const clearRequestedFindingAction = useUiStore((state) => state.clearRequestedFindingAction);

  // Render-phase state adjustment (react.dev's own pattern for this case,
  // already used by `DocumentViewer.tsx`'s `jumpTarget` handling) rather
  // than a `useEffect` that calls `setState` synchronously in its body —
  // opens the same dialog a manual button click opens the moment a
  // matching command-palette request appears, without an extra
  // post-commit render.
  const [previousRequestedFindingAction, setPreviousRequestedFindingAction] =
    useState(requestedFindingAction);
  if (requestedFindingAction !== previousRequestedFindingAction) {
    setPreviousRequestedFindingAction(requestedFindingAction);
    if (requestedFindingAction?.findingId === finding.id) {
      if (requestedFindingAction.action === 'verify') setVerifyDialogOpen(true);
      if (requestedFindingAction.action === 'override') setOverrideDialogOpen(true);
      if (requestedFindingAction.action === 'escalate') setEscalateDialogOpen(true);
    }
  }

  // Clearing the shared request is an external-store side effect (not this
  // component's own render-phase state), so it belongs in an effect.
  useEffect(() => {
    if (requestedFindingAction?.findingId === finding.id) {
      clearRequestedFindingAction();
    }
  }, [requestedFindingAction, finding.id, clearRequestedFindingAction]);

  const alreadyDecided = finding.state === 'verified' || finding.state === 'overridden';

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

  const onEscalateSubmit = handleEscalateSubmit((values) => {
    escalateMutation.mutate(
      { findingId: finding.id, reason: values.reason, targetRole: values.targetRole },
      {
        onSuccess: () => {
          setEscalateDialogOpen(false);
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
      <Button
        variant="secondary"
        size="sm"
        disabled={alreadyDecided}
        onClick={() => {
          setEscalateDialogOpen(true);
        }}
      >
        Escalate
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
          <label className="flex flex-col gap-1" htmlFor="override-previous-value">
            <span className="text-label text-text-primary">Previous value</span>
            <Input id="override-previous-value" {...register('previousValue')} />
          </label>
          <label className="flex flex-col gap-1" htmlFor="override-new-value">
            <span className="text-label text-text-primary">Corrected value</span>
            <Input
              id="override-new-value"
              {...register('newValue')}
              invalid={errors.newValue !== undefined}
            />
            {errors.newValue !== undefined && (
              <span className="text-caption text-text-critical">{errors.newValue.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1" htmlFor="override-reason">
            <span className="text-label text-text-primary">Reason</span>
            <Textarea
              id="override-reason"
              {...register('reason')}
              invalid={errors.reason !== undefined}
            />
            {errors.reason !== undefined && (
              <span className="text-caption text-text-critical">{errors.reason.message}</span>
            )}
          </label>
        </form>
      </Dialog>

      <Dialog
        open={escalateDialogOpen}
        onOpenChange={setEscalateDialogOpen}
        title="Escalate this finding"
        description="Move this finding to another role's queue. This is recorded permanently."
        primaryAction={{
          label: 'Review & Confirm',
          loading: escalateMutation.isPending,
          onClick: () => {
            void onEscalateSubmit();
          },
        }}
      >
        <form className="flex flex-col gap-3">
          <label className="flex flex-col gap-1" htmlFor="escalate-target-role">
            <span className="text-label text-text-primary">Escalate to</span>
            <Select id="escalate-target-role" {...registerEscalate('targetRole')}>
              {ESCALATION_TARGET_ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1" htmlFor="escalate-reason">
            <span className="text-label text-text-primary">Reason</span>
            <Textarea
              id="escalate-reason"
              {...registerEscalate('reason')}
              invalid={escalateErrors.reason !== undefined}
            />
            {escalateErrors.reason !== undefined && (
              <span className="text-caption text-text-critical">
                {escalateErrors.reason.message}
              </span>
            )}
          </label>
        </form>
      </Dialog>
    </div>
  );
}
