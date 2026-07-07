/**
 * Intake wizard form schema (Product Experience phase, Phase 2).
 *
 * One shared shape across all three steps (`useForm<IntakeFormValues>`) —
 * steps only control which fields render and which subset gets
 * step-scoped `trigger()` validation before advancing, so navigating Back
 * never loses data and there is no juggling of separate per-step form
 * instances.
 */

import { z } from 'zod';

import { PARTY_TYPES } from '@entities/party/types';

export const borrowerRowSchema = z.object({
  partyType: z.enum(PARTY_TYPES),
  displayName: z.string().min(1, 'Enter a name for this borrower.'),
});

export const intakeFormSchema = z.object({
  losReference: z.string().min(1, 'LOS reference is required.'),
  loanNumber: z.string(),
  borrowers: z.array(borrowerRowSchema).min(1, 'Add at least one borrower.'),
});

export type IntakeFormValues = z.infer<typeof intakeFormSchema>;
export type BorrowerRow = z.infer<typeof borrowerRowSchema>;

/** Field names step 1 ("Application") owns — passed to RHF's `trigger()` before advancing. */
export const APPLICATION_STEP_FIELDS = ['losReference', 'loanNumber'] as const;

export const DEFAULT_INTAKE_VALUES: IntakeFormValues = {
  losReference: '',
  loanNumber: '',
  borrowers: [{ partyType: 'APPLICANT', displayName: '' }],
};

export type WizardStep = 'application' | 'borrowers' | 'review';

export const WIZARD_STEPS: readonly { readonly id: WizardStep; readonly label: string }[] = [
  { id: 'application', label: 'Application' },
  { id: 'borrowers', label: 'Borrowers' },
  { id: 'review', label: 'Review' },
];
