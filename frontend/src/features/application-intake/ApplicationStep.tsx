/**
 * Intake wizard — Step 1: Application (Product Experience phase, Phase 2;
 * identifiers auto-generated in Phase 12). MIL operates standalone today, so
 * the LOS reference and loan number are generated client-side
 * (`generateDemoIdentifiers.ts`) rather than typed by the user — the exact
 * same two fields a future LOS integration would supply instead, with no
 * other change anywhere in this flow. This step is a read-only recap; there
 * is nothing left to validate before advancing.
 */

import type { UseFormReturn } from 'react-hook-form';

import type { IntakeFormValues } from './schema';

export interface ApplicationStepProps {
  readonly form: UseFormReturn<IntakeFormValues>;
}

export function ApplicationStep({ form }: ApplicationStepProps) {
  const losReference = form.watch('losReference');
  const loanNumber = form.watch('loanNumber');

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body text-text-secondary">
        MIL has generated the identifiers this application will be known by.
      </p>

      <div className="bg-surface-secondary flex flex-col gap-3 rounded-container p-3">
        <div>
          <p className="text-caption text-text-tertiary tracking-wide uppercase">LOS reference</p>
          <p className="text-body-emphasis text-text-primary">{losReference}</p>
        </div>
        <div>
          <p className="text-caption text-text-tertiary tracking-wide uppercase">Loan number</p>
          <p className="text-body-emphasis text-text-primary">{loanNumber}</p>
        </div>
      </div>

      <p className="text-caption text-text-tertiary">
        System-generated for this standalone demo. Once connected to a Loan Origination System,
        these will come directly from the LOS instead.
      </p>
    </div>
  );
}
