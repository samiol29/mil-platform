/**
 * ApplicationTimeline (Product Experience phase, Phase 9) — the rendering
 * layer for `buildApplicationTimeline`'s case-history entries. Day-grouped,
 * each entry showing its real label, real timestamp, real `actorType`
 * (`SYSTEM`/`USER` — no name resolution exists, same disclosed gap as
 * every prior phase), and — when the underlying event carries one — a
 * trace action reusing the exact navigation `ApplicationWorkspace.tsx`
 * already lifts for Evidence/Findings/Policy (`activateEvidenceJump`/
 * `viewFinding`), never a new mechanism.
 */

import { EmptyState } from '@design-system/components/EmptyState';
import { cn } from '@design-system/lib/cn';

import type { ApplicationTimelineEntry } from './buildApplicationTimeline';

function formatDay(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

function groupByDay(
  entries: readonly ApplicationTimelineEntry[],
): readonly (readonly [string, readonly ApplicationTimelineEntry[]])[] {
  const groups = new Map<string, ApplicationTimelineEntry[]>();
  for (const entry of entries) {
    const day = formatDay(entry.occurredAt);
    const existing = groups.get(day);
    if (existing) existing.push(entry);
    else groups.set(day, [entry]);
  }
  return Array.from(groups.entries());
}

export interface ApplicationTimelineProps {
  readonly entries: readonly ApplicationTimelineEntry[];
  readonly onTraceDocument: (documentId: string) => void;
  readonly onTraceFinding: (findingId: string) => void;
}

/** Failure entries get an error-tinted rail dot — the one color signal on the rail. */
function isFailureEntry(entry: ApplicationTimelineEntry): boolean {
  return entry.label.startsWith('Processing failed');
}

export function ApplicationTimeline({
  entries,
  onTraceDocument,
  onTraceFinding,
}: ApplicationTimelineProps) {
  if (entries.length === 0) {
    return <EmptyState title="No case history yet" />;
  }

  return (
    <div className="flex flex-col gap-6">
      {groupByDay(entries).map(([day, dayEntries]) => (
        <div key={day}>
          <p className="text-caption text-text-tertiary mb-3 tracking-wide uppercase">{day}</p>
          <ul className="border-border-subtle ml-20 flex flex-col border-l">
            {dayEntries.map((entry) => (
              <li key={entry.id} className="relative flex items-baseline gap-3 py-1.5 pl-4">
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute top-3 -left-[3.5px] size-1.5 rounded-full',
                    isFailureEntry(entry) ? 'bg-feedback-error-fg' : 'bg-border-strong',
                  )}
                />
                <span className="text-caption text-text-tertiary absolute -left-20 w-16 text-right tabular-nums">
                  {formatTime(entry.occurredAt)}
                </span>
                <span className="text-body text-text-primary min-w-0 flex-1">
                  {entry.label}{' '}
                  <span className="text-caption text-text-tertiary whitespace-nowrap">
                    · {entry.actorType === 'SYSTEM' ? 'System' : 'Reviewer'}
                  </span>
                </span>
                {entry.trace !== undefined && (
                  <button
                    type="button"
                    onClick={() => {
                      if (entry.trace?.kind === 'document') onTraceDocument(entry.trace.documentId);
                      else if (entry.trace?.kind === 'finding')
                        onTraceFinding(entry.trace.findingId);
                    }}
                    className="text-caption text-text-secondary hover:text-text-primary shrink-0 outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                  >
                    {entry.trace.kind === 'document' ? 'View document →' : 'View finding →'}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
