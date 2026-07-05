/**
 * AI-signal color family (spec 003 FR-024, FR-066) — marks content as
 * AI-generated or an AI process in progress, and ONLY that.
 *
 * Structurally and hue-distinct from Status (`color.status.ts`) and
 * Evidence/Confidence (`color.confidence.ts`) — a dedicated violet hue never
 * reused elsewhere. Every AI-generated value MUST carry this signal
 * persistently (not just on first view) and non-decoratively — a label, not
 * only an icon, so the meaning survives print/export where icon-only
 * treatments can be ambiguous (FR-066, Edge Cases).
 */

import { Loader2, Sparkles } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface AiSignalToken {
  readonly label: string;
  readonly bgClassName: string;
  readonly fgClassName: string;
  readonly borderClassName: string;
  readonly icon: LucideIcon;
}

/** Persistent, non-decorative "this is AI-generated" indicator. */
export const aiSignalToken: AiSignalToken = {
  label: 'AI-generated',
  bgClassName: 'bg-ai-signal-bg',
  fgClassName: 'text-ai-signal-fg',
  borderClassName: 'border-ai-signal-border',
  icon: Sparkles,
};

/** "An AI process is currently running" — same hue family, distinct icon. */
export const aiProcessingToken: Omit<AiSignalToken, 'bgClassName' | 'borderClassName'> = {
  label: 'AI processing',
  fgClassName: 'text-ai-processing-fg',
  icon: Loader2,
};
