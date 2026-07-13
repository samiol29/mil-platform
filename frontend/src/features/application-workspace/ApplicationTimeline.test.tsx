import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ApplicationTimeline } from './ApplicationTimeline';
import type { ApplicationTimelineEntry } from './buildApplicationTimeline';

function makeEntry(overrides: Partial<ApplicationTimelineEntry> = {}): ApplicationTimelineEntry {
  return {
    id: 'entry-1',
    occurredAt: '2026-07-13T11:27:00Z',
    actorType: 'SYSTEM',
    label: 'Application created',
    ...overrides,
  };
}

function renderTimeline(entries: readonly ApplicationTimelineEntry[]) {
  return render(
    <ApplicationTimeline entries={entries} onTraceDocument={vi.fn()} onTraceFinding={vi.fn()} />,
  );
}

describe('ApplicationTimeline motion (final polish sprint — Timeline Motion)', () => {
  it('does not animate any entry on the very first render', () => {
    const { container } = renderTimeline([
      makeEntry({ id: 'a', label: 'Application created' }),
      makeEntry({ id: 'b', label: 'Document uploaded: file.pdf', occurredAt: '2026-07-13T11:28:00Z' }),
    ]);
    expect(container.querySelectorAll('.animate-panel-in')).toHaveLength(0);
  });

  it('animates only a genuinely new entry added after the initial render', () => {
    const initial = [makeEntry({ id: 'a', label: 'Application created' })];
    const { container, rerender } = render(
      <ApplicationTimeline entries={initial} onTraceDocument={vi.fn()} onTraceFinding={vi.fn()} />,
    );

    const withNewEntry = [
      ...initial,
      makeEntry({ id: 'b', label: 'Document uploaded: file.pdf', occurredAt: '2026-07-13T11:28:00Z' }),
    ];
    rerender(
      <ApplicationTimeline
        entries={withNewEntry}
        onTraceDocument={vi.fn()}
        onTraceFinding={vi.fn()}
      />,
    );

    expect(container.querySelectorAll('.animate-panel-in')).toHaveLength(1);
    expect(screen.getByText(/Document uploaded/).closest('li')).toHaveClass('animate-panel-in');
    expect(screen.getByText('Application created').closest('li')).not.toHaveClass(
      'animate-panel-in',
    );
  });

  it('does not re-animate on an unrelated re-render with the same entries', () => {
    const entries = [makeEntry({ id: 'a', label: 'Application created' })];
    const { container, rerender } = render(
      <ApplicationTimeline entries={entries} onTraceDocument={vi.fn()} onTraceFinding={vi.fn()} />,
    );

    // A new array reference with identical ids (e.g. a background refetch
    // returning the same data) must not be treated as a new entry.
    rerender(
      <ApplicationTimeline
        entries={[...entries]}
        onTraceDocument={vi.fn()}
        onTraceFinding={vi.fn()}
      />,
    );

    expect(container.querySelectorAll('.animate-panel-in')).toHaveLength(0);
  });
});
