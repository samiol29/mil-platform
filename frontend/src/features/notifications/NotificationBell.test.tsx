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
              occurredAt: '2026-07-11T00:00:00Z',
              readAt: null,
              createdAt: '2026-07-11T00:00:00Z',
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
