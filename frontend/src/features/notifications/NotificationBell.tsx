/**
 * Notification bell (spec 005-enterprise-platform §13, Wave 2). Mounted in
 * the persistent header shell, next to the existing ⌘K search button and
 * `UserMenu` — same "always-visible global affordance" register as those,
 * not a new chrome pattern.
 *
 * Every notification's message is derived from its real, referenced
 * `AuditEvent` (`eventType`/`eventData`) — never a bespoke title/body the
 * frontend invents, matching the backend model's own "no duplicate event
 * model" discipline.
 */

import { useState } from 'react';
import { Bell } from 'lucide-react';

import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { useMarkNotificationRead, useNotifications } from '@entities/notification/queries';
import type { Notification } from '@entities/notification/types';

/**
 * Plain-language label derived from a real audit event type/data — the
 * same discipline `buildApplicationTimeline` already applies for the
 * Timeline region, narrowed to the handful of event types this wave's
 * modules actually notify about.
 */
function describeNotification(notification: Notification): string {
  switch (notification.eventType) {
    case 'REVIEW_COMMENT_ADDED':
      return 'You were mentioned in a comment';
    default:
      return `Update: ${notification.eventType.replaceAll('_', ' ').toLowerCase()}`;
  }
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const notificationsQuery = useNotifications();
  const markRead = useMarkNotificationRead();

  const unreadCount = notificationsQuery.data?.unreadCount ?? 0;

  return (
    <div className="relative">
      <Button
        variant="secondary"
        size="sm"
        onClick={() => {
          setOpen((v) => !v);
        }}
        aria-label={`Notifications${unreadCount > 0 ? ` (${String(unreadCount)} unread)` : ''}`}
      >
        <Bell className="size-3.5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="bg-feedback-error-fg text-caption rounded-full px-1 text-white">
            {unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <div className="bg-surface-raised shadow-raised rounded-container border-border-subtle absolute right-0 top-full z-50 mt-1 flex max-h-96 w-80 flex-col gap-1 overflow-y-auto border p-2">
          {(notificationsQuery.data?.items ?? []).length === 0 ? (
            <EmptyState title="No notifications" description="You're all caught up." />
          ) : (
            (notificationsQuery.data?.items ?? []).map((notification) => (
              <button
                key={notification.id}
                type="button"
                onClick={() => {
                  if (notification.readAt === null) {
                    markRead.mutate(notification.id);
                  }
                }}
                className={`text-caption rounded-interactive flex flex-col items-start gap-0.5 p-2 text-left outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2 ${
                  notification.readAt === null
                    ? 'bg-surface-secondary text-text-primary'
                    : 'text-text-tertiary'
                }`}
              >
                <span>{describeNotification(notification)}</span>
                <span className="text-text-tertiary">
                  {new Date(notification.occurredAt).toLocaleString()}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
