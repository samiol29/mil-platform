/**
 * Escalation Queue route (final product polish sprint, A5) —
 * `/escalation-queue`. Gated by `navConfig.ts`'s `roles` filter; the
 * backend's own RBAC (`read:application`) is the real enforcement boundary.
 */

import { createFileRoute } from '@tanstack/react-router';

import { EscalationQueuePage } from '@features/escalation-queue/EscalationQueuePage';

export const Route = createFileRoute('/escalation-queue/')({
  component: EscalationQueuePage,
});
