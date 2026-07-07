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

export function ApplicationTimeline({ entries, onTraceDocument, onTraceFinding }: ApplicationTimelineProps) {
  if (entries.length === 0) {
    return <EmptyState title="No case history yet" />;
  }

  return (
    <div className="flex flex-col gap-4">
      {groupByDay(entries).map(([day, dayEntries]) => (
        <div key={day}>
          <p className="text-caption text-text-tertiary mb-2">{day}</p>
          <ul className="flex flex-col gap-2">
            {dayEntries.map((entry) => (
              <li
                key={entry.id}
                className="border-border-subtle flex flex-wrap items-center justify-between gap-2 border-b pb-2 last:border-b-0 last:pb-0"
              >
                <span className="text-body text-text-primary">{entry.label}</span>
                <div className="flex items-center gap-3">
                  <span className="text-caption text-text-tertiary">
                    {formatTime(entry.occurredAt)} · {entry.actorType === 'SYSTEM' ? 'System' : 'Reviewer'}
                  </span>
                  {entry.trace !== undefined && (
                    <button
                      type="button"
                      onClick={() => {
                        if (entry.trace?.kind === 'document') onTraceDocument(entry.trace.documentId);
                        else if (entry.trace?.kind === 'finding') onTraceFinding(entry.trace.findingId);
                      }}
                      className="text-caption text-text-secondary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
                    >
                      {entry.trace.kind === 'document' ? 'View document →' : 'View finding →'}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
