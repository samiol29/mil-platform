/**
 * Intake wizard — Step 2: Borrowers (Product Experience phase, Phase 2).
 *
 * Repeatable rows (`useFieldArray`), not a long form — starts with one
 * pre-added APPLICANT row. `Enter` in the last row's name field adds
 * another row (Notion/Linear-style quick add), the "keyboard efficiency"
 * requirement rather than a generic multi-field form. A row can only be
 * removed down to a minimum of one (an intake with zero borrowers isn't a
 * meaningful state to leave this step in).
 *
 * The APPLICANT-required hint is deliberately non-blocking: the backend
 * only enforces "at least one APPLICANT" at `submit_application` time, not
 * at creation — inventing a hard validation rule here would misrepresent
 * what the API actually requires.
 */

import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { useRef } from 'react';
import type { KeyboardEvent, RefObject } from 'react';
import type { UseFormRegister, UseFormReturn } from 'react-hook-form';
import { useFieldArray } from 'react-hook-form';

import { Input } from '@design-system/components/Input';
import { Select } from '@design-system/components/Select';
import { cn } from '@design-system/lib/cn';
import { PARTY_TYPE_LABEL, PARTY_TYPES } from '@entities/party/types';

import type { IntakeFormValues } from './schema';

export interface BorrowersStepProps {
  readonly form: UseFormReturn<IntakeFormValues>;
}

export function BorrowersStep({ form }: BorrowersStepProps) {
  const {
    control,
    register,
    watch,
    formState: { errors },
  } = form;
  const { fields, append, remove } = useFieldArray({ control, name: 'borrowers' });
  const borrowers = watch('borrowers');
  const hasApplicant = borrowers.some((row) => row.partyType === 'APPLICANT');
  const lastNameInputRef = useRef<HTMLInputElement | null>(null);

  function addRow() {
    append({ partyType: 'CO_APPLICANT', displayName: '' });
  }

  function handleLastRowKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      addRow();
      // Focus moves to the new row's name field once it mounts.
      requestAnimationFrame(() => {
        lastNameInputRef.current?.focus();
      });
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body text-text-secondary">
        Add every borrower on this application — a primary applicant, co-applicants, guarantors, or
        a corporate entity.
      </p>

      <div className="flex flex-col gap-3">
        {fields.map((field, index) => {
          const isLast = index === fields.length - 1;
          const rowErrors = errors.borrowers?.[index];
          return (
            <div
              key={field.id}
              className="bg-surface-secondary flex flex-col gap-2 rounded-container p-3 sm:flex-row sm:items-start"
            >
              <div className="w-full sm:w-40 sm:shrink-0">
                <Select
                  {...register(`borrowers.${String(index)}.partyType` as `borrowers.${number}.partyType`)}
                >
                  {PARTY_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {PARTY_TYPE_LABEL[type]}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex flex-1 flex-col gap-1">
                <NameField
                  index={index}
                  isLast={isLast}
                  register={register}
                  invalid={rowErrors?.displayName !== undefined}
                  onLastRowKeyDown={handleLastRowKeyDown}
                  lastNameInputRef={lastNameInputRef}
                />
                {rowErrors?.displayName !== undefined && (
                  <span className="text-caption text-text-critical">
                    {rowErrors.displayName.message}
                  </span>
                )}
              </div>
              <button
                type="button"
                aria-label="Remove borrower"
                disabled={fields.length === 1}
                onClick={() => {
                  remove(index);
                }}
                className={cn(
                  'rounded-interactive text-text-tertiary shrink-0 self-end p-2 sm:self-auto',
                  'hover:bg-surface-disabled hover:text-text-critical disabled:pointer-events-none disabled:opacity-40',
                  'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
                )}
              >
                <Trash2 className="size-4" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={addRow}
        className={cn(
          'text-label border-border-default text-text-secondary hover:bg-surface-secondary flex items-center justify-center gap-1.5 rounded-interactive border border-dashed py-2 font-medium',
          'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
        )}
      >
        <Plus className="size-4" aria-hidden="true" />
        Add another borrower
      </button>

      {!hasApplicant && (
        <div className="text-caption border-feedback-warning-fg bg-feedback-warning-bg text-feedback-warning-fg flex items-start gap-2 rounded-container border p-3">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>
            No borrower is marked Applicant yet. You can continue, but the application will need at
            least one Applicant before it can be submitted for review.
          </span>
        </div>
      )}
    </div>
  );
}

interface NameFieldProps {
  readonly index: number;
  readonly isLast: boolean;
  readonly invalid: boolean;
  readonly register: UseFormRegister<IntakeFormValues>;
  readonly onLastRowKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  readonly lastNameInputRef: RefObject<HTMLInputElement | null>;
}

/** Registers once and composes RHF's ref with the "focus the newest row" ref the quick-add flow needs. */
function NameField({
  index,
  isLast,
  invalid,
  register,
  onLastRowKeyDown,
  lastNameInputRef,
}: NameFieldProps) {
  const { ref, ...field } = register(
    `borrowers.${String(index)}.displayName` as `borrowers.${number}.displayName`,
  );
  return (
    <Input
      placeholder="Borrower name"
      invalid={invalid}
      onKeyDown={isLast ? onLastRowKeyDown : undefined}
      {...field}
      ref={(node) => {
        ref(node);
        if (isLast) lastNameInputRef.current = node;
      }}
    />
  );
}
