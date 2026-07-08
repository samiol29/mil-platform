/**
 * Intake wizard — Step 3: Review (Product Experience phase, Phase 2).
 *
 * Read-only recap of what's about to be created, plus the one line of
 * explicit next-step framing that makes the hand-off into Phase 3 (Upload)
 * feel designed rather than incidental. This step doubles as the
 * submission's progress/retry surface — see `IntakeWizard.tsx` for the
 * sequencing this renders the state of.
 */

import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

import { Button } from '@design-system/components/Button';
import { cn } from '@design-system/lib/cn';
import { PARTY_TYPE_LABEL } from '@entities/party/types';

import type { IntakeFormValues } from './schema';

export type BorrowerRowStatus = 'idle' | 'pending' | 'success' | 'error';

export interface ReviewStepProps {
  readonly values: IntakeFormValues;
  /** One status per `values.borrowers` row, index-aligned. */
  readonly borrowerStatuses: readonly BorrowerRowStatus[];
  readonly applicationCreated: boolean;
  readonly applicationCreateError: boolean;
  readonly isSubmitting: boolean;
  readonly hasAttemptedSubmit: boolean;
  readonly onSubmit: () => void;
}

export function ReviewStep({
  values,
  borrowerStatuses,
  applicationCreated,
  applicationCreateError,
  isSubmitting,
  hasAttemptedSubmit,
  onSubmit,
}: ReviewStepProps) {
  const anyFailed = applicationCreateError || borrowerStatuses.some((s) => s === 'error');
  const buttonLabel = !hasAttemptedSubmit
    ? 'Create Application'
    : anyFailed
      ? 'Retry'
      : 'Create Application';

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-surface-secondary rounded-container p-3">
        <p className="text-caption text-text-tertiary tracking-wide uppercase">
          System-generated reference
        </p>
        <p className="text-body-emphasis text-text-primary">{values.losReference}</p>
        {values.loanNumber.length > 0 && (
          <p className="text-caption text-text-tertiary">Loan #{values.loanNumber}</p>
        )}
        {hasAttemptedSubmit && (
          <RowStatus
            status={applicationCreateError ? 'error' : applicationCreated ? 'success' : 'pending'}
            className="mt-2"
          />
        )}
      </div>

      <div className="bg-surface-secondary flex flex-col gap-2 rounded-container p-3">
        <p className="text-caption text-text-secondary">
          Borrowers ({values.borrowers.length})
        </p>
        {values.borrowers.map((borrower, index) => (
          <div key={index} className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-caption border-border-default text-text-secondary rounded-chip border px-2 py-0.5">
                {PARTY_TYPE_LABEL[borrower.partyType]}
              </span>
              <span className="text-body text-text-primary">{borrower.displayName}</span>
            </div>
            {hasAttemptedSubmit && <RowStatus status={borrowerStatuses[index] ?? 'idle'} />}
          </div>
        ))}
      </div>

      <p className="text-caption text-text-secondary">
        You'll upload this borrower's documents next.
      </p>

      {anyFailed && (
        <p className="text-caption text-text-critical">
          Something didn't go through. Already-created items are kept — Retry only resends what
          failed.
        </p>
      )}

      <Button variant="primary" loading={isSubmitting} onClick={onSubmit}>
        {buttonLabel}
      </Button>
    </div>
  );
}

function RowStatus({ status, className }: { readonly status: BorrowerRowStatus; readonly className?: string }) {
  if (status === 'idle') return null;
  if (status === 'pending') {
    return (
      <span className={cn('text-text-tertiary inline-flex items-center gap-1', className)}>
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
      </span>
    );
  }
  if (status === 'success') {
    return (
      <span className={cn('text-feedback-success-fg inline-flex items-center gap-1', className)}>
        <CheckCircle2 className="size-3.5" aria-hidden="true" />
      </span>
    );
  }
  return (
    <span className={cn('text-feedback-error-fg inline-flex items-center gap-1', className)}>
      <AlertCircle className="size-3.5" aria-hidden="true" />
    </span>
  );
}
