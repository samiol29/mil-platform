/**
 * Evidence Search Sprint — substring highlighting for search results.
 *
 * Only wraps the matched substring(s) in `<mark>`; every other character is
 * returned untouched, so callers (`EvidenceCard`) don't need to change their
 * own typography — this only ever inserts inline `<mark>` spans into text
 * that already renders as-is.
 */

import type { ReactNode } from 'react';

function escapeRegExp(value: string): string {
  return value.replaceAll(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function highlightMatch(text: string, query: string): ReactNode {
  const normalizedQuery = query.trim();
  if (normalizedQuery === '' || text === '') return text;

  const pattern = new RegExp(`(${escapeRegExp(normalizedQuery)})`, 'ig');
  const parts = text.split(pattern);
  if (parts.length === 1) return text;

  return parts.map((part, index) =>
    part.toLowerCase() === normalizedQuery.toLowerCase() ? (
      <mark key={index} className="rounded-sm bg-feedback-warning-bg text-feedback-warning-fg">
        {part}
      </mark>
    ) : (
      <span key={index}>{part}</span>
    ),
  );
}
