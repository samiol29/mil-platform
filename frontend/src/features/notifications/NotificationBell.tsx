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
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { useMarkNotificationRead, useNotifications } from '@entities/notification/queries';
import type { Notification } from '@entities/notification/types';

/**
 * Plain-language label derived from a real audit event type/data — the
 * same discipline `buildApplicationTimeline` already applies for the
 * Timeline region, narrowed to the handful of event types this wave's
 * modules actually notify about. `REVIEW_FINDING_*` cases (final product
 * polish sprint) cover the new Verify/Override/Escalate -> Notification
 * wiring — previously these actions never notified anyone at all, so no
 * label existed for them.
 */
function describeNotification(notification: Notification): string {
  switch (notification.eventType) {
    case 'REVIEW_COMMENT_ADDED':
      return 'You were mentioned in a comment';
    case 'REVIEW_FINDING_APPROVED':
      return 'A finding on your application was verified';
    case 'REVIEW_FINDING_OVERRIDDEN':
      return 'A finding on your application was overridden';
    case 'REVIEW_FINDING_ESCALATED':
      return 'A finding on your application was escalated';
    default:
      return `Update: ${notification.eventType.replaceAll('_', ' ').toLowerCase()}`;
  }
}

function formatDay(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/** Mirrors `ApplicationTimeline.tsx`'s `groupByDay` exactly — same grouping convention, not a second one. */
function groupByDay(
  notifications: readonly Notification[],
): readonly (readonly [string, readonly Notification[]])[] {
  const groups = new Map<string, Notification[]>();
  for (const notification of notifications) {
    const day = formatDay(notification.occurredAt);
    const existing = groups.get(day);
    if (existing) existing.push(notification);
    else groups.set(day, [notification]);
  }
  return Array.from(groups.entries());
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
        <div className="bg-surface-raised shadow-raised rounded-container border-border-subtle animate-panel-in absolute right-0 top-full z-50 mt-1 flex max-h-96 w-80 flex-col gap-2 overflow-y-auto border p-2">
          {notificationsQuery.isPending && <LoadingState label="Loading notifications…" />}
          {notificationsQuery.isError && (
            /*
             * Final product polish sprint (D2): before this, a failed fetch
             * rendered identically to "No notifications" — a real error was
             * indistinguishable from a genuinely empty inbox, which is
             * actively misleading rather than merely incomplete.
             */
            <ErrorState
              title="Could not load notifications"
              onRetry={() => {
                void notificationsQuery.refetch();
              }}
            />
          )}
          {notificationsQuery.isSuccess && notificationsQuery.data.items.length === 0 && (
            <EmptyState title="No notifications" description="You're all caught up." />
          )}
          {notificationsQuery.isSuccess &&
            notificationsQuery.data.items.length > 0 &&
            groupByDay(notificationsQuery.data.items).map(([day, dayNotifications]) => (
              <div key={day} className="flex flex-col gap-1">
                <p className="text-caption text-text-tertiary px-2 pt-1 tracking-wide uppercase">
                  {day}
                </p>
                {dayNotifications.map((notification) => (
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
                      {new Date(notification.occurredAt).toLocaleTimeString(undefined, {
                        hour: 'numeric',
                        minute: '2-digit',
                      })}
                    </span>
                  </button>
                ))}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
