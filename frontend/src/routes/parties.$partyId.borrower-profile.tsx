/**
 * Borrower Profile route (spec 005-enterprise-platform §5, Wave 3) —
 * `/parties/$partyId/borrower-profile`. Entry point is a party id, since
 * every screen that links here (Overview borrower chips, RM portfolio)
 * already has one.
 */

import { createFileRoute } from '@tanstack/react-router';

import { PageContainer } from '@design-system/components/PageContainer';
import { BorrowerProfilePage } from '@features/borrower-identity/BorrowerProfilePage';

export const Route = createFileRoute('/parties/$partyId/borrower-profile')({
  component: BorrowerProfileRoute,
});

function BorrowerProfileRoute() {
  const { partyId } = Route.useParams();

  return (
    <PageContainer variant="workspace">
      <BorrowerProfilePage partyId={partyId} />
    </PageContainer>
  );
}
