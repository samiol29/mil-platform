import { describe, expect, it } from 'vitest';

import { formatFindingNarrative } from './formatFindingNarrative';

describe('formatFindingNarrative', () => {
  it('renders a plain paragraph as-is', () => {
    const blocks = formatFindingNarrative('A simple sentence with no markdown.');
    expect(blocks).toEqual([
      {
        kind: 'paragraph',
        segments: [{ text: 'A simple sentence with no markdown.', bold: false }],
      },
    ]);
  });

  it('splits bold spans out of a paragraph', () => {
    const blocks = formatFindingNarrative('This has **bold text** in the middle.');
    expect(blocks).toEqual([
      {
        kind: 'paragraph',
        segments: [
          { text: 'This has ', bold: false },
          { text: 'bold text', bold: true },
          { text: ' in the middle.', bold: false },
        ],
      },
    ]);
  });

  it('renders a pure bullet block as a list', () => {
    const blocks = formatFindingNarrative('*   First item.\n*   Second item.');
    expect(blocks).toEqual([
      {
        kind: 'list',
        items: [[{ text: 'First item.', bold: false }], [{ text: 'Second item.', bold: false }]],
      },
    ]);
  });

  it('condenses a single-id citation bracket to a source count', () => {
    const blocks = formatFindingNarrative(
      'Borrower name is Daniel Carter [f1d3b9b6-3ffe-4389-8781-7bee0aab32f8].',
    );
    expect(blocks[0]).toEqual({
      kind: 'paragraph',
      segments: [{ text: 'Borrower name is Daniel Carter (1 source).', bold: false }],
    });
  });

  it('condenses a multi-id citation bracket to a plural source count', () => {
    const blocks = formatFindingNarrative(
      'Consistent across documents [f1d3b9b6-3ffe-4389-8781-7bee0aab32f8, 09b08bb6-d8db-4340-ad4f-1e57662ee2f4].',
    );
    expect(blocks[0]).toEqual({
      kind: 'paragraph',
      segments: [{ text: 'Consistent across documents (2 sources).', bold: false }],
    });
  });

  it('strips a stray bullet marker out of a mixed sub-bullet block instead of leaving a literal asterisk', () => {
    const blocks = formatFindingNarrative(
      '*   Top item:\n    *   Sub item one.\n    *   Sub item two.\n    Continuation line.',
    );
    expect(blocks).toEqual([
      {
        kind: 'paragraph',
        segments: [
          {
            text: 'Top item: Sub item one. Sub item two. Continuation line.',
            bold: false,
          },
        ],
      },
    ]);
  });

  it('separates blocks on blank lines', () => {
    const blocks = formatFindingNarrative('First paragraph.\n\nSecond paragraph.');
    expect(blocks).toHaveLength(2);
  });
});
