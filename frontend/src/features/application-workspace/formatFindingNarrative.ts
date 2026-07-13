/**
 * Lightweight, dependency-free formatting for `Finding.why` (final polish
 * sprint). The Gemini-generated narrative arrives as loose markdown
 * (`**bold**`, `*   ` bullet lines) with inline evidence citations as raw
 * bracketed UUID lists (e.g. `[f1d3b9b6-..., 09b08bb6-...]`) — rendered
 * verbatim as plain text, this was an unreadable wall of literal asterisks
 * and 36-character IDs. No markdown library is introduced for this (a new
 * dependency would be architecture expansion for one field); this parses
 * only the handful of constructs this generator actually produces.
 *
 * Citations are condensed to a short "(N sources)" marker rather than
 * dropped outright — full traceability is preserved by the Supporting
 * Evidence chips already rendered below, which list every one of
 * `finding.evidenceRefs`; this is a display simplification of the prose,
 * not a loss of the underlying citation data.
 */

const CITATION_BRACKET = /\s*\[[0-9a-f]{8}-[0-9a-f-]{27}(?:,\s*[0-9a-f]{8}-[0-9a-f-]{27})*\]/gi;

export interface FindingNarrativeSegment {
  readonly text: string;
  readonly bold: boolean;
}

export type FindingNarrativeBlock =
  | { readonly kind: 'paragraph'; readonly segments: readonly FindingNarrativeSegment[] }
  | { readonly kind: 'list'; readonly items: readonly (readonly FindingNarrativeSegment[])[] };

function condenseCitations(line: string): string {
  return line.replace(CITATION_BRACKET, (match) => {
    const count = match.split(',').length;
    return ` (${String(count)} source${count === 1 ? '' : 's'})`;
  });
}

function splitBold(line: string): readonly FindingNarrativeSegment[] {
  return line
    .split(/(\*\*[^*]+\*\*)/)
    .filter((part) => part.length > 0)
    .map((part) =>
      part.startsWith('**') && part.endsWith('**')
        ? { text: part.slice(2, -2), bold: true }
        : { text: part, bold: false },
    );
}

/** Parses `finding.why` into paragraph/list blocks with bold spans and condensed citations. */
export function formatFindingNarrative(why: string): readonly FindingNarrativeBlock[] {
  const blocks: FindingNarrativeBlock[] = [];
  const rawBlocks = why.split(/\n\s*\n/).map((block) => block.trim()).filter((block) => block.length > 0);

  for (const rawBlock of rawBlocks) {
    const lines = rawBlock.split('\n').map((line) => line.trim());
    const isList = lines.every((line) => /^\*\s+/.test(line));

    if (isList) {
      blocks.push({
        kind: 'list',
        items: lines.map((line) => splitBold(condenseCitations(line.replace(/^\*\s+/, '')))),
      });
    } else {
      // A block can mix a top-level bullet with indented sub-bullets/continuation
      // lines (this generator nests sub-bullets under a bullet rather than using
      // a blank line between them) — strip any leading bullet marker per line
      // before joining so a literal "*" never survives into the rendered text.
      const joined = lines.map((line) => line.replace(/^\*\s+/, '')).join(' ');
      blocks.push({
        kind: 'paragraph',
        segments: splitBold(condenseCitations(joined)),
      });
    }
  }

  return blocks;
}
