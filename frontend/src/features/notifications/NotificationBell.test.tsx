import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';

import { queryClient } from '@app/queryClient';
import { ThemeProvider } from '@design-system/theme/ThemeProvider';

import { server } from '../../test/msw/server';
import { NotificationBell } from './NotificationBell';

function renderBell() {
  return render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <NotificationBell />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe('NotificationBell (spec 005 §13, Wave 2)', () => {
  afterEach(() => {
    server.resetHandlers();
    queryClient.clear();
  });

  it('shows the unread count and a derived message from the real audit event', async () => {
    server.use(
      http.get('/v1/notifications', () =>
        HttpResponse.json({
          unreadCount: 1,
          items: [
            {
              id: '11111111-1111-4111-8111-111111111111',
              recipientUserId: '22222222-2222-4222-8222-222222222222',
              auditEventId: '33333333-3333-4333-8333-333333333333',
              eventType: 'REVIEW_COMMENT_ADDED',
              eventData: { commentId: 'abc' },
              occurredAt: '2026-07-11T12:00:00Z',
              readAt: null,
              createdAt: '2026-07-11T12:00:00Z',
            },
          ],
        }),
      ),
    );

    renderBell();
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Notifications/ }));

    expect(await screen.findByText('You were mentioned in a comment')).toBeInTheDocument();
  });

  it('shows real labels for the new review-action notification types (final product polish sprint)', async () => {
    server.use(
      http.get('/v1/notifications', () =>
        HttpResponse.json({
          unreadCount: 3,
          items: [
            {
              id: '11111111-1111-4111-8111-111111111111',
              recipientUserId: '22222222-2222-4222-8222-222222222222',
              auditEventId: '33333333-3333-4333-8333-333333333333',
              eventType: 'REVIEW_FINDING_APPROVED',
              eventData: {},
              occurredAt: '2026-07-11T12:00:00Z',
              readAt: null,
              createdAt: '2026-07-11T12:00:00Z',
            },
            {
              id: '44444444-4444-4444-8444-444444444444',
              recipientUserId: '22222222-2222-4222-8222-222222222222',
              auditEventId: '55555555-5555-4555-8555-555555555555',
              eventType: 'REVIEW_FINDING_OVERRIDDEN',
              eventData: {},
              occurredAt: '2026-07-11T12:05:00Z',
              readAt: null,
              createdAt: '2026-07-11T12:05:00Z',
            },
            {
              id: '66666666-6666-4666-8666-666666666666',
              recipientUserId: '22222222-2222-4222-8222-222222222222',
              auditEventId: '77777777-7777-4777-8777-777777777777',
              eventType: 'REVIEW_FINDING_ESCALATED',
              eventData: {},
              occurredAt: '2026-07-11T12:10:00Z',
              readAt: null,
              createdAt: '2026-07-11T12:10:00Z',
            },
          ],
        }),
      ),
    );

    renderBell();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Notifications/ }));

    expect(
      await screen.findByText('A finding on your application was verified'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('A finding on your application was overridden'),
    ).toBeInTheDocument();
    expect(screen.getByText('A finding on your application was escalated')).toBeInTheDocument();
  });

  it('groups notifications by day', async () => {
    server.use(
      http.get('/v1/notifications', () =>
        HttpResponse.json({
          unreadCount: 2,
          items: [
            {
              id: '11111111-1111-4111-8111-111111111111',
              recipientUserId: '22222222-2222-4222-8222-222222222222',
              auditEventId: '33333333-3333-4333-8333-333333333333',
              eventType: 'REVIEW_COMMENT_ADDED',
              eventData: {},
              occurredAt: '2026-07-11T12:00:00Z',
              readAt: null,
              createdAt: '2026-07-11T12:00:00Z',
            },
            {
              id: '44444444-4444-4444-8444-444444444444',
              recipientUserId: '22222222-2222-4222-8222-222222222222',
              auditEventId: '55555555-5555-4555-8555-555555555555',
              eventType: 'REVIEW_COMMENT_ADDED',
              eventData: {},
              occurredAt: '2026-06-01T12:00:00Z',
              readAt: null,
              createdAt: '2026-06-01T12:00:00Z',
            },
          ],
        }),
      ),
    );

    renderBell();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Notifications/ }));

    expect(await screen.findByText('July 11, 2026')).toBeInTheDocument();
    expect(screen.getByText('June 1, 2026')).toBeInTheDocument();
  });

  it('shows an error state (not a misleading empty state) when the fetch fails', async () => {
    /* Final product polish sprint (D2): before this, a failed fetch rendered
     * identically to "No notifications" — a real error was indistinguishable
     * from a genuinely empty inbox. */
    server.use(http.get('/v1/notifications', () => HttpResponse.json(null, { status: 500 })));

    renderBell();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Notifications' }));

    await waitFor(
      () => {
        expect(screen.getByText('Could not load notifications')).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
    expect(screen.queryByText('No notifications')).not.toBeInTheDocument();
  });

  it('shows an honest empty state with no notifications', async () => {
    server.use(
      http.get('/v1/notifications', () => HttpResponse.json({ unreadCount: 0, items: [] })),
    );

    renderBell();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Notifications' }));

    expect(await screen.findByText('No notifications')).toBeInTheDocument();
  });
});
