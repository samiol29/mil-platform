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

/** Node fill/ring treatment per status — `md` size only (Phase 11's enterprise progress tracker). */
const NODE_CLASS_NAME: Readonly<Record<PipelineStepStatus, string>> = {
  pending: 'bg-surface-secondary text-text-tertiary',
  active: 'bg-surface-raised text-interactive-primary-default ring-2 ring-interactive-primary-default',
  complete: 'bg-feedback-success-bg text-feedback-success-fg',
  failed: 'bg-feedback-error-bg text-feedback-error-fg',
  skipped: 'bg-surface-secondary text-text-disabled',
};

export function ProcessingPipeline({ steps, size = 'md', className }: ProcessingPipelineProps) {
  if (size === 'sm') {
    return (
      <div
        role="group"
        aria-label="Processing pipeline"
        className={cn('flex items-center gap-1', className)}
      >
        {steps.map((step, index) => {
          const Icon = STATUS_ICON[step.status];
          const isLast = index === steps.length - 1;
          return (
            <div key={step.id} className="flex items-center">
              <div
                className="flex items-center gap-1"
                title={step.detail ?? `${step.label}: ${step.status}`}
              >
                <Icon
                  className={cn(
                    'size-3.5',
                    STATUS_CLASS_NAME[step.status],
                    step.status === 'active' && 'animate-spin',
                  )}
                  aria-hidden="true"
                />
                <span className="sr-only">{step.label}: {step.status}</span>
              </div>
              {!isLast && (
                <div
                  aria-hidden="true"
                  className={cn(
                    'bg-border-default mx-1 h-px w-3',
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

  // `md` (Phase 11): a proper workflow tracker — labeled nodes with filled
  // connectors — rather than a row of status icons. Same honest statuses,
  // no fabricated progress; `detail` (always real backend text) renders as
  // a caption under its step.
  return (
    <div role="group" aria-label="Processing pipeline" className={cn('flex items-start', className)}>
      {steps.map((step, index) => {
        const Icon = STATUS_ICON[step.status];
        const isLast = index === steps.length - 1;
        return (
          <div key={step.id} className={cn('flex items-start', !isLast && 'flex-1')}>
            <div
              className="flex max-w-40 flex-col items-center gap-1.5 text-center"
              title={step.detail ?? `${step.label}: ${step.status}`}
            >
              <span
                className={cn(
                  'flex size-7 items-center justify-center rounded-full',
                  NODE_CLASS_NAME[step.status],
                )}
              >
                <Icon
                  className={cn('size-4', step.status === 'active' && 'animate-spin')}
                  aria-hidden="true"
                />
              </span>
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
              {step.detail !== undefined && (
                <span className="text-caption text-text-tertiary">{step.detail}</span>
              )}
              <span className="sr-only">{step.label}: {step.status}</span>
            </div>
            {!isLast && (
              <div
                aria-hidden="true"
                className={cn(
                  'mx-2 mt-3.5 h-0.5 min-w-6 flex-1 rounded-full',
                  step.status === 'complete' || step.status === 'skipped'
                    ? 'bg-feedback-success-fg'
                    : 'bg-border-default',
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
