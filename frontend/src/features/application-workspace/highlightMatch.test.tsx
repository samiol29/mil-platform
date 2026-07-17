import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { highlightMatch } from './highlightMatch';

describe('highlightMatch', () => {
  it('returns the original text unchanged when the query is empty', () => {
    const { container } = render(<>{highlightMatch('Daniel Carter', '')}</>);
    expect(container).toHaveTextContent('Daniel Carter');
    expect(container.querySelector('mark')).toBeNull();
  });

  it('returns the original text unchanged when there is no match', () => {
    const { container } = render(<>{highlightMatch('Daniel Carter', 'liabilities')}</>);
    expect(container).toHaveTextContent('Daniel Carter');
    expect(container.querySelector('mark')).toBeNull();
  });

  it('wraps only the matching substring in a <mark>, case-insensitively', () => {
    const { container } = render(<>{highlightMatch('Daniel Carter', 'carter')}</>);
    const mark = container.querySelector('mark');
    expect(mark).not.toBeNull();
    expect(mark).toHaveTextContent('Carter');
    expect(container).toHaveTextContent('Daniel Carter');
  });

  it('highlights every occurrence of the query', () => {
    const { container } = render(<>{highlightMatch('income income', 'income')}</>);
    expect(container.querySelectorAll('mark')).toHaveLength(2);
  });

  it('does not choke on regex special characters in the query', () => {
    const { container } = render(<>{highlightMatch('USD 6,200.00', '6,200.00')}</>);
    const mark = container.querySelector('mark');
    expect(mark).toHaveTextContent('6,200.00');
  });
});
