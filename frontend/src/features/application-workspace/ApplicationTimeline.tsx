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

import { useEffect, useState } from 'react';

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

/**
 * Rail-dot color per entry category (final polish sprint) — with every
 * event on the rail the same neutral gray dot, a hundred-plus-line day
 * quickly reads as one undifferentiated wall. Derived only from `trace.kind`
 * (already a real discriminated union built from the entry's own event
 * type, not a label guess) plus the existing failure check — document
 * events in one color, finding/review/policy events in another, pure
 * application-level events (created, status change, comments) staying the
 * existing neutral dot.
 */
function railDotClassName(entry: ApplicationTimelineEntry): string {
  if (isFailureEntry(entry)) return 'bg-feedback-error-fg';
  if (entry.trace?.kind === 'document') return 'bg-interactive-primary-default';
  if (entry.trace?.kind === 'finding') return 'bg-ai-signal-fg';
  return 'bg-border-strong';
}

export function ApplicationTimeline({
  entries,
  onTraceDocument,
  onTraceFinding,
}: ApplicationTimelineProps) {
  // Motion should reinforce chronology, not run continuously (executive
  // review pass): a real review action (verify/override/escalate, a
  // document finishing processing) refetches this list and a genuinely new
  // entry appears — that entry alone gets the enter transition, the same
  // `animate-panel-in` token every other "content just appeared" moment in
  // the product uses. Entries already on screen never re-animate on an
  // unrelated refetch, and opening the Timeline for the first time never
  // animates the entire history at once.
  //
  // Uses React's own "adjust state during render" pattern (react.dev,
  // *Storing information from previous renders*) rather than a ref read
  // during render — comparing `entries` against the last snapshot mid-render
  // is compiler-safe; a ref read here is not. `newIds` is cleared via a
  // plain timer (matching `--duration-panel`'s 200ms) rather than as soon as
  // React notices the list changed, so the CSS animation always finishes
  // before its triggering class is removed.
  const [previousEntries, setPreviousEntries] = useState(entries);
  const [newIds, setNewIds] = useState<ReadonlySet<string>>(new Set());

  if (entries !== previousEntries) {
    const previousIds = new Set(previousEntries.map((entry) => entry.id));
    const addedIds = new Set(
      entries.filter((entry) => !previousIds.has(entry.id)).map((entry) => entry.id),
    );
    setPreviousEntries(entries);
    // Skip the initial mount (`previousEntries` starts empty) — only ids
    // added after the Timeline was already showing something count as new.
    setNewIds(previousEntries.length > 0 ? addedIds : new Set());
  }

  useEffect(() => {
    if (newIds.size === 0) return;
    const timer = window.setTimeout(() => {
      setNewIds(new Set());
    }, 220);
    return () => {
      window.clearTimeout(timer);
    };
  }, [newIds]);

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
              <li
                key={entry.id}
                className={cn(
                  'relative flex items-baseline gap-3 py-1.5 pl-4',
                  newIds.has(entry.id) && 'animate-panel-in',
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute top-3 -left-[3.5px] size-1.5 rounded-full',
                    railDotClassName(entry),
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
