/**
 * ProcessingPipeline (Product Experience phase, Phase 4 — the flagship
 * "AI work is visible" experience). One component, two densities: `size="sm"`
 * for a compact per-document row (`DocumentProcessingList.tsx`), `size="md"`
 * for the application-level summary (`ApplicationWorkspace.tsx`'s Overview
 * region) — Principle 2's "both levels, without overwhelming the interface"
 * is satisfied by reusing one component at different densities rather than
 * building two.
 *
 * This component has no opinion on what the steps *mean* — it only renders
 * whatever `steps` it's given. Every caller is responsible for deriving
 * honest steps from real data (see `deriveDocumentStages.ts` and
 * `applicationPipelineSummary.ts`) — this component cannot itself fabricate
 * a stage, by construction.
 */

import { AlertTriangle, CheckCircle2, Circle, Loader2, MinusCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@design-system/lib/cn';

export type PipelineStepStatus = 'pending' | 'active' | 'complete' | 'failed' | 'skipped';

export interface PipelineStep {
  readonly id: string;
  readonly label: string;
  readonly status: PipelineStepStatus;
  /** Real backend-provided detail (e.g. `ingestionError`) — never invented copy. Shown as a tooltip/caption. */
  readonly detail?: string;
}

export interface ProcessingPipelineProps {
  readonly steps: readonly PipelineStep[];
  readonly size?: 'sm' | 'md';
  readonly className?: string;
}

const STATUS_ICON: Readonly<Record<PipelineStepStatus, LucideIcon>> = {
  pending: Circle,
  active: Loader2,
  complete: CheckCircle2,
  failed: AlertTriangle,
  skipped: MinusCircle,
};

const STATUS_CLASS_NAME: Readonly<Record<PipelineStepStatus, string>> = {
  pending: 'text-text-tertiary',
  active: 'text-interactive-primary-default',
  complete: 'text-feedback-success-fg',
  failed: 'text-feedback-error-fg',
  skipped: 'text-text-disabled',
};

export function ProcessingPipeline({ steps, size = 'md', className }: ProcessingPipelineProps) {
  const isSmall = size === 'sm';

  return (
    <div
      role="group"
      aria-label="Processing pipeline"
      className={cn('flex items-center', isSmall ? 'gap-1' : 'gap-2', className)}
    >
      {steps.map((step, index) => {
        const Icon = STATUS_ICON[step.status];
        const isLast = index === steps.length - 1;
        return (
          <div key={step.id} className="flex items-center">
            <div
              className={cn('flex items-center', isSmall ? 'gap-1' : 'gap-1.5')}
              title={step.detail ?? `${step.label}: ${step.status}`}
            >
              <Icon
                className={cn(
                  isSmall ? 'size-3.5' : 'size-4',
                  STATUS_CLASS_NAME[step.status],
                  step.status === 'active' && 'animate-spin',
                )}
                aria-hidden="true"
              />
              {!isSmall && (
                <span
                  className={cn(
                    'text-caption font-medium',
                    step.status === 'pending' || step.status === 'skipped'
                      ? 'text-text-tertiary'
                      : 'text-text-primary',
                  )}
                >
                  {step.label}
                </span>
              )}
              {isSmall && <span className="sr-only">{step.label}: {step.status}</span>}
            </div>
            {!isLast && (
              <div
                aria-hidden="true"
                className={cn(
                  'bg-border-default',
                  isSmall ? 'mx-1 h-px w-3' : 'mx-2 h-px w-5',
                  (step.status === 'complete' || step.status === 'skipped') &&
                    'bg-feedback-success-fg',
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
