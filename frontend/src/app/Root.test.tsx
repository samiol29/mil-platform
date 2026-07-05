import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Root } from '@app/Root';

describe('Root', () => {
  it('renders the application name as an accessible heading', () => {
    render(<Root />);

    expect(
      screen.getByRole('heading', { name: 'MIL — Underwriter Workspace' }),
    ).toBeInTheDocument();
  });
});
