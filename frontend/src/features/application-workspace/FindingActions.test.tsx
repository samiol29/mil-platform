import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { useUiStore } from '@app/uiStore';
import type { Finding } from '@entities/finding/queries';

import { server } from '../../test/msw/server';
import { FindingActions } from './FindingActions';

const APPLICATION_ID = '11111111-1111-1111-a111-111111111111';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: '44444444-4444-4444-a444-444444444444',
    applicationId: APPLICATION_ID,
    what: 'Reported income does not match the pay stub on file.',
    why: 'The application states $6,500/month; the extracted value is $6,200/month.',
    evidenceRefs: ['33333333-3333-3333-a333-333333333333'],
    confidence: 'high',
    recommendedAction: 'Confirm current income with the borrower.',
    state: 'unreviewed',
    modelVersion: 'gpt-underwriting-2026.06',
    promptVersion: 'finding-v3',
    extractionVersion: '2026.06.1',
    policyVersion: 'policy-pack-2026.2',
    escalatedToRole: null,
    escalatedToUserId: null,
    createdAt: '2026-06-21T10:15:00Z',
    ...overrides,
  };
}

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('FindingActions', () => {
  afterEach(() => {
    server.resetHandlers();
  });

  it('blocks override submission when the reason is empty', async () => {
    const user = userEvent.setup();
    renderWithClient(<FindingActions applicationId={APPLICATION_ID} finding={makeFinding()} />);

    await user.click(screen.getByRole('button', { name: 'Override' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Corrected value'), '6200.00');
    await user.click(within(dialog).getByRole('button', { name: 'Review & Confirm' }));

    expect(await within(dialog).findByText('A reason is required.')).toBeInTheDocument();
    // The dialog must still be open — no confirmed write happened.
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('preserves entered values after a failed override submission', async () => {
    server.use(
      http.post('/v1/findings/:id/override', () =>
        HttpResponse.json({ code: 'SERVER_ERROR' }, { status: 500 }),
      ),
    );

    const user = userEvent.setup();
    renderWithClient(<FindingActions applicationId={APPLICATION_ID} finding={makeFinding()} />);

    await user.click(screen.getByRole('button', { name: 'Override' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Previous value'), '6500.00');
    await user.type(within(dialog).getByLabelText('Corrected value'), '6200.00');
    await user.type(within(dialog).getByLabelText('Reason'), 'Confirmed via payslip');
    await user.click(within(dialog).getByRole('button', { name: 'Review & Confirm' }));

    await waitFor(() => {
      expect(within(dialog).getByLabelText('Reason')).toHaveValue('Confirmed via payslip');
    });
    expect(within(dialog).getByLabelText('Previous value')).toHaveValue('6500.00');
    expect(within(dialog).getByLabelText('Corrected value')).toHaveValue('6200.00');
  });

  it('shows a distinguishing toast title on a 409 conflict, not the generic failure title (D6)', async () => {
    useUiStore.setState({ toasts: [] });
    server.use(
      http.post('/v1/findings/:id/override', () =>
        HttpResponse.json({ code: 'CONFLICT', message: 'Already overridden' }, { status: 409 }),
      ),
    );

    const user = userEvent.setup();
    renderWithClient(<FindingActions applicationId={APPLICATION_ID} finding={makeFinding()} />);

    await user.click(screen.getByRole('button', { name: 'Override' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Corrected value'), '6200.00');
    await user.type(within(dialog).getByLabelText('Reason'), 'Confirmed via payslip');
    await user.click(within(dialog).getByRole('button', { name: 'Review & Confirm' }));

    await waitFor(() => {
      const toasts = useUiStore.getState().toasts;
      expect(toasts.some((t) => t.title === 'This finding was already updated')).toBe(true);
    });
    // Never the generic, undifferentiated failure title for this real, distinguishable case.
    expect(
      useUiStore.getState().toasts.some((t) => t.title === 'Could not override this finding'),
    ).toBe(false);
  });

  it('disables verify/override/escalate once the finding has already been decided', () => {
    renderWithClient(
      <FindingActions
        applicationId={APPLICATION_ID}
        finding={makeFinding({ state: 'verified' })}
      />,
    );
    expect(screen.getByRole('button', { name: 'Verify' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Override' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Escalate' })).toBeDisabled();
  });

  it('keeps verify/override/escalate enabled for an escalated (non-terminal) finding', () => {
    renderWithClient(
      <FindingActions
        applicationId={APPLICATION_ID}
        finding={makeFinding({ state: 'escalated', escalatedToRole: 'COMPLIANCE_OFFICER' })}
      />,
    );
    expect(screen.getByRole('button', { name: 'Verify' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Override' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Escalate' })).toBeEnabled();
  });

  it('blocks escalate submission when the reason is empty', async () => {
    const user = userEvent.setup();
    renderWithClient(<FindingActions applicationId={APPLICATION_ID} finding={makeFinding()} />);

    await user.click(screen.getByRole('button', { name: 'Escalate' }));
    const dialog = screen.getByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Review & Confirm' }));

    expect(await within(dialog).findByText('A reason is required.')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('escalates a finding with a reason and target role', async () => {
    const user = userEvent.setup();
    renderWithClient(<FindingActions applicationId={APPLICATION_ID} finding={makeFinding()} />);

    await user.click(screen.getByRole('button', { name: 'Escalate' }));
    const dialog = screen.getByRole('dialog');
    await user.selectOptions(within(dialog).getByLabelText('Escalate to'), 'COMPLIANCE_OFFICER');
    await user.type(within(dialog).getByLabelText('Reason'), 'Possible fair-lending concern');
    await user.click(within(dialog).getByRole('button', { name: 'Review & Confirm' }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('preserves entered values after a failed escalate submission', async () => {
    server.use(
      http.post('/v1/findings/:id/escalate', () =>
        HttpResponse.json({ code: 'SERVER_ERROR' }, { status: 500 }),
      ),
    );

    const user = userEvent.setup();
    renderWithClient(<FindingActions applicationId={APPLICATION_ID} finding={makeFinding()} />);

    await user.click(screen.getByRole('button', { name: 'Escalate' }));
    const dialog = screen.getByRole('dialog');
    await user.selectOptions(within(dialog).getByLabelText('Escalate to'), 'RISK_ANALYST');
    await user.type(within(dialog).getByLabelText('Reason'), 'Please review this figure');
    await user.click(within(dialog).getByRole('button', { name: 'Review & Confirm' }));

    await waitFor(() => {
      expect(within(dialog).getByLabelText('Reason')).toHaveValue('Please review this figure');
    });
    expect(within(dialog).getByLabelText('Escalate to')).toHaveValue('RISK_ANALYST');
  });
});
