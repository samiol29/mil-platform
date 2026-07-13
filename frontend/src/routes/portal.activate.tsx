/**
 * Customer Portal activation route (spec 005-enterprise-platform §12,
 * Wave 4) — `/portal/activate?partyId=...&token=...`. Deliberately outside
 * the internal app's nav/auth shell — a borrower never sees `PrimaryNav`
 * or any internal-staff chrome.
 */

import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';

import { PortalActivatePage } from '@features/customer-portal/PortalActivatePage';

const searchSchema = z.object({
  partyId: z.uuid(),
  token: z.string().min(1),
});

export const Route = createFileRoute('/portal/activate')({
  validateSearch: searchSchema,
  component: PortalActivateRoute,
});

function PortalActivateRoute() {
  const { partyId, token } = Route.useSearch();
  return <PortalActivatePage partyId={partyId} token={token} />;
}
