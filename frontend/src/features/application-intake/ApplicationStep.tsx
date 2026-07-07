/**
 * Intake wizard — Step 1: Application (Product Experience phase, Phase 2).
 * Two fields only: `losReference` (required, per `CreateApplicationRequest`)
 * and `loanNumber` (optional). `Enter` in either field advances to the
 * Borrowers step when valid — the keyboard-efficiency requirement, matching
 * a natural single-step form's Enter-to-submit feel.
 */

import { useEffect, useRef } from 'react';
import type { KeyboardEvent } from 'react';
import type { UseFormReturn } from 'react-hook-form';

import { Input } from '@design-system/components/Input';

import type { IntakeFormValues } from './schema';

export interface ApplicationStepProps {
  readonly form: UseFormReturn<IntakeFormValues>;
  readonly onNext: () => void;
}

export function ApplicationStep({ form, onNext }: ApplicationStepProps) {
  const {
    register,
    formState: { errors },
  } = form;
  const losReferenceRef = useRef<HTMLInputElement | null>(null);
  const { ref: registerLosRef, ...losReferenceField } = register('losReference');

  useEffect(() => {
    losReferenceRef.current?.focus();
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      onNext();
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body text-text-secondary">
        Start with the two identifiers this application is known by.
      </p>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="intake-los-reference" className="text-label text-text-primary font-medium">
          LOS reference
        </label>
        <Input
          id="intake-los-reference"
          placeholder="e.g. LOS-0000042"
          invalid={errors.losReference !== undefined}
          onKeyDown={handleKeyDown}
          {...losReferenceField}
          ref={(node) => {
            registerLosRef(node);
            losReferenceRef.current = node;
          }}
        />
        {errors.losReference !== undefined && (
          <span className="text-caption text-text-critical">{errors.losReference.message}</span>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="intake-loan-number" className="text-label text-text-primary font-medium">
          Loan number <span className="text-text-tertiary font-normal">(optional)</span>
        </label>
        <Input
          id="intake-loan-number"
          placeholder="e.g. 4009123456"
          onKeyDown={handleKeyDown}
          {...register('loanNumber')}
        />
      </div>
    </div>
  );
}
