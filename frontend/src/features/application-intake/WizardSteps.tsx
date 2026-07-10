/**
 * Wizard step progress header (Product Experience phase, Phase 2) — a
 * linear, gated indicator ("Step 2 of 3 — Borrowers"), deliberately not the
 * `Tabs` design-system component: `Tabs` implies freely selectable,
 * non-linear navigation, while this wizard's steps are sequential and
 * validation-gated (you cannot jump ahead). Kept local to this feature
 * rather than promoted to `design-system/` — if a second wizard needs this
 * exact pattern later, that's the point to promote it, not before.
 */

import { cn } from '@design-system/lib/cn';

import { WIZARD_STEPS, type WizardStep } from './schema';

export interface WizardStepsProps {
  readonly current: WizardStep;
}

export function WizardSteps({ current }: WizardStepsProps) {
  const currentIndex = WIZARD_STEPS.findIndex((step) => step.id === current);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-caption text-text-secondary">
        Step {currentIndex + 1} of {WIZARD_STEPS.length} — {WIZARD_STEPS[currentIndex]?.label}
      </p>
      <div className="flex gap-1.5" role="presentation">
        {WIZARD_STEPS.map((step, index) => (
          <div
            key={step.id}
            className={cn(
              'h-1 flex-1 rounded-full',
              index <= currentIndex ? 'bg-interactive-primary-default' : 'bg-surface-disabled',
            )}
          />
        ))}
      </div>
    </div>
  );
}
