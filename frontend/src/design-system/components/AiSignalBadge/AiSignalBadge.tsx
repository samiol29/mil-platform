/**
 * AiSignalBadge (spec 003 T027, FR-024, FR-066) — the persistent,
 * non-decorative indicator marking content as AI-generated or an AI process
 * in progress. Every AI-generated value in the product MUST carry this
 * signal; it is never omitted after "the first time" a user sees it
 * (FR-066).
 *
 * Two states only: `signal` (static — "this value/finding was AI-generated")
 * and `processing` (an AI operation is currently running). Both use the
 * dedicated violet AI hue (`color.ai.ts`), structurally distinct from Status
 * and Confidence — this badge is never repurposed to indicate workflow
 * status or extraction confidence (FR-024).
 */

import { aiProcessingToken, aiSignalToken } from '@design-system/tokens/color.ai';
import { cn } from '@design-system/lib/cn';

export interface AiSignalBadgeProps {
  readonly variant?: 'signal' | 'processing';
  readonly className?: string;
}

export function AiSignalBadge({ variant = 'signal', className }: AiSignalBadgeProps) {
  if (variant === 'processing') {
    const Icon = aiProcessingToken.icon;
    return (
      <span
        role="status"
        aria-live="polite"
        className={cn(
          'inline-flex items-center gap-1.5 rounded-chip px-2.5 py-1 text-caption font-medium',
          'bg-ai-signal-bg border-ai-signal-border border',
          aiProcessingToken.fgClassName,
          className,
        )}
      >
        <Icon className="size-3.5 animate-spin" aria-hidden="true" />
        {aiProcessingToken.label}
      </span>
    );
  }

  const Icon = aiSignalToken.icon;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-caption font-medium',
        aiSignalToken.bgClassName,
        aiSignalToken.fgClassName,
        aiSignalToken.borderClassName,
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {aiSignalToken.label}
    </span>
  );
}
