/**
 * Intake wizard orchestrator (Product Experience phase, Phase 2) — a
 * single Drawer-hosted, three-step, gated flow: Application → Borrowers →
 * Review. One shared `useForm<IntakeFormValues>` instance underneath all
 * three steps (see `schema.ts`) so Back never loses data.
 *
 * Mounted once, globally, in `routes/__root.tsx` (see `uiStore.ts`'s
 * `intakeWizardOpen` docstring for why) — "New Application" from the
 * Dashboard, the Queue header, and the Command Palette all just call
 * `openIntakeWizard()`.
 *
 * Submission is sequential and retry-safe (the one real correctness risk
 * in this feature): creating the application happens once — its id is
 * cached in local state immediately on success — and retrying after a
 * partial borrower-add failure never re-creates the application or
 * resubmits an already-succeeded borrower. On full success, the wizard
 * closes and navigates straight into the new application's Workspace at
 * `region: 'documents'` — the deliberate seam into Phase 3 (Upload).
 *
 * `IntakeWizard` (this component) is a thin, always-mounted shell around
 * the Drawer. Every step's form/mutation/submission state lives in
 * `IntakeWizardBody`, which is `key`-remounted each time the Drawer opens
 * (React's own recommended "resetting state" pattern — see
 * react.dev/learn/you-might-not-need-an-effect) instead of an effect that
 * calls several `setState`s to reset a previous session's leftover state.
 * The session key itself is bumped by adjusting state *during* render (the
 * "adjusting state when a prop changes" pattern react.dev documents — calling
 * a setter mid-render from the currently-rendering component is explicitly
 * sanctioned there), not via a ref or an effect.
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { Drawer } from '@design-system/components/Drawer';
import { useCreateApplication } from '@entities/application/queries';
import { useAddParty } from '@entities/party/queries';

import { ApplicationStep } from './ApplicationStep';
import { BorrowersStep } from './BorrowersStep';
import { generateDemoIdentifiers } from './generateDemoIdentifiers';
import type { BorrowerRowStatus } from './ReviewStep';
import { ReviewStep } from './ReviewStep';
import {
  DEFAULT_BORROWER_ROWS,
  intakeFormSchema,
  type IntakeFormValues,
  type WizardStep,
} from './schema';
import { WizardSteps } from './WizardSteps';

export function IntakeWizard() {
  const open = useUiStore((state) => state.intakeWizardOpen);
  const closeWizard = useUiStore((state) => state.closeIntakeWizard);

  // Bumped once per open — remounting `IntakeWizardBody` under a new key is
  // what gives every fresh open a clean slate, without an effect + a batch
  // of setState calls to manually zero everything out.
  const [sessionKey, setSessionKey] = useState(0);
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setSessionKey((key) => key + 1);
  }

  return (
    <Drawer
      open={open}
      onOpenChange={(next) => {
        if (!next) closeWizard();
      }}
      title="New Application"
      size="lg"
    >
      <IntakeWizardBody key={sessionKey} />
    </Drawer>
  );
}

function IntakeWizardBody() {
  const closeWizard = useUiStore((state) => state.closeIntakeWizard);
  const addToast = useUiStore((state) => state.addToast);
  const navigate = useNavigate();

  // Generated once per wizard session (this component remounts fresh under
  // a new `key` each time the Drawer opens — see the module docstring), not
  // recomputed on every render.
  const [identifiers] = useState(() => generateDemoIdentifiers());
  const form = useForm<IntakeFormValues>({
    resolver: zodResolver(intakeFormSchema),
    defaultValues: { ...identifiers, borrowers: DEFAULT_BORROWER_ROWS },
  });

  const [step, setStep] = useState<WizardStep>('application');
  const [createdApplicationId, setCreatedApplicationId] = useState<string | null>(null);
  const [applicationCreateError, setApplicationCreateError] = useState(false);
  const [borrowerStatuses, setBorrowerStatuses] = useState<readonly BorrowerRowStatus[]>([]);
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const createApplication = useCreateApplication();
  const addParty = useAddParty();

  function goToBorrowers() {
    // Nothing to validate on this step anymore — the identifiers are
    // system-generated, not typed.
    setStep('borrowers');
  }

  async function goToReview() {
    const valid = await form.trigger('borrowers');
    if (valid) setStep('review');
  }

  async function handleFinalSubmit() {
    const values = form.getValues();
    setHasAttemptedSubmit(true);
    setIsSubmitting(true);

    let applicationId = createdApplicationId;
    if (applicationId === null) {
      setApplicationCreateError(false);
      try {
        const loanNumber = values.loanNumber.trim();
        const application = await createApplication.mutateAsync({
          losReference: values.losReference,
          ...(loanNumber.length > 0 ? { loanNumber } : {}),
        });
        applicationId = application.id;
        setCreatedApplicationId(applicationId);
      } catch {
        setApplicationCreateError(true);
        setIsSubmitting(false);
        return;
      }
    }

    const statuses = [...borrowerStatuses];
    for (let index = 0; index < values.borrowers.length; index += 1) {
      if (statuses[index] === 'success') continue;
      statuses[index] = 'pending';
      setBorrowerStatuses([...statuses]);
      try {
        // Intentionally sequential (module docstring): each borrower add
        // waits for the previous one so retries can skip already-succeeded
        // rows precisely, rather than racing several requests at once.
        await addParty.mutateAsync({
          applicationId,
          partyType: values.borrowers[index].partyType,
          displayName: values.borrowers[index].displayName,
        });
        statuses[index] = 'success';
      } catch {
        statuses[index] = 'error';
      }
      setBorrowerStatuses([...statuses]);
    }

    setIsSubmitting(false);

    const allSucceeded = values.borrowers.every((_, index) => statuses[index] === 'success');
    if (allSucceeded) {
      addToast({ title: 'Application created', description: values.losReference, variant: 'success' });
      closeWizard();
      void navigate({
        to: '/applications/$applicationId',
        params: { applicationId },
        search: { region: 'documents' },
      });
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <WizardSteps current={step} />

      <div className="flex-1">
        {step === 'application' && <ApplicationStep form={form} />}
        {step === 'borrowers' && <BorrowersStep form={form} />}
        {step === 'review' && (
          <ReviewStep
            values={form.getValues()}
            borrowerStatuses={borrowerStatuses}
            applicationCreated={createdApplicationId !== null}
            applicationCreateError={applicationCreateError}
            isSubmitting={isSubmitting}
            hasAttemptedSubmit={hasAttemptedSubmit}
            onSubmit={() => void handleFinalSubmit()}
          />
        )}
      </div>

      {step !== 'review' && (
        <div className="border-border-subtle flex justify-between border-t pt-4">
          <Button
            variant="secondary"
            disabled={step === 'application'}
            onClick={() => {
              setStep('application');
            }}
          >
            Back
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              if (step === 'application') goToBorrowers();
              else void goToReview();
            }}
          >
            Continue
          </Button>
        </div>
      )}

      {step === 'review' && (
        <div className="border-border-subtle border-t pt-4">
          <Button
            variant="secondary"
            disabled={isSubmitting}
            onClick={() => {
              setStep('borrowers');
            }}
          >
            Back
          </Button>
        </div>
      )}
    </div>
  );
}
