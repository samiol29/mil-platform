/**
 * Borrower Profile route (spec 005-enterprise-platform §5, Wave 3) —
 * `/parties/$partyId/borrower-profile`. Entry point is a party id, since
 * every screen that links here (Overview borrower chips, RM portfolio)
 * already has one.
 */

import { createFileRoute } from '@tanstack/react-router';

import { BorrowerProfilePage } from '@features/borrower-identity/BorrowerProfilePage';

export const Route = createFileRoute('/parties/$partyId/borrower-profile')({
  component: BorrowerProfileRoute,
});

function BorrowerProfileRoute() {
  const { partyId } = Route.useParams();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <BorrowerProfilePage partyId={partyId} />
    </div>
  );
}
