/**
 * ConfidenceIndicator (spec 003 T026, FR-023, FR-061) — the single confidence
 * scale used identically everywhere extraction confidence is shown. No
 * different confidence visualization may be introduced per screen or data
 * type (FR-061).
 *
 * Non-color signal (FR-026): a three-segment fill bar whose *count* of
 * filled segments (3/2/1) encodes the band — structurally distinct from
 * `StatusBadge`'s icon-plus-label treatment, so confidence and status remain
 * distinguishable even displayed adjacently (Edge Cases). The paired icon
 * (`SignalHigh`/`SignalMedium`/`SignalLow`) reinforces the same structure.
 */

import { confidenceTokens, type ConfidenceLevel } from '@design-system/tokens/color.confidence';
import { cn } from '@design-system/lib/cn';

export interface ConfidenceIndicatorProps {
  readonly level: ConfidenceLevel;
  readonly className?: string;
}

const SEGMENT_COUNT = 3;

export function ConfidenceIndicator({ level, className }: ConfidenceIndicatorProps) {
  const token = confidenceTokens[level];
  const Icon = token.icon;

  return (
    <div
      role="meter"
      aria-label="Extraction confidence"
      aria-valuenow={token.filledSegments}
      aria-valuemin={1}
      aria-valuemax={SEGMENT_COUNT}
      aria-valuetext={token.label}
      className={cn('inline-flex items-center gap-1.5', className)}
    >
      <Icon className={cn('size-3.5', token.fgClassName)} aria-hidden="true" />
      <div className="flex items-center gap-0.5" aria-hidden="true">
        {Array.from({ length: SEGMENT_COUNT }, (_, index) => (
          <span
            key={index}
            className={cn(
              'h-2.5 w-1.5 rounded-full',
              index < token.filledSegments ? token.fillClassName : 'bg-surface-disabled',
            )}
          />
        ))}
      </div>
      <span className={cn('text-caption font-medium', token.fgClassName)}>{token.label}</span>
    </div>
  );
}
