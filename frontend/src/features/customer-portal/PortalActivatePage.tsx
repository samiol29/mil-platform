/**
 * Customer Portal activation (spec 005-enterprise-platform §12, Wave 4).
 *
 * A deliberately calm, plain-language, consumer-banking-app register — not
 * a cut-down version of the internal Underwriter Workspace (spec §12.11).
 * `partyId`/`token` arrive as URL query parameters from the invitation
 * link an internal user relayed out-of-band (no email/SMS provider exists
 * in this platform today — see spec §12's implementation-correction note).
 */

import { useNavigate } from '@tanstack/react-router';
import { useState } from 'react';

import { Button } from '@design-system/components/Button';
import { ErrorState } from '@design-system/components/ErrorState';
import { useActivatePortalAccount } from '@entities/portal/queries';

interface PortalActivatePageProps {
  readonly partyId: string;
  readonly token: string;
}

export function PortalActivatePage({ partyId, token }: PortalActivatePageProps) {
  const activateMutation = useActivatePortalAccount();
  const navigate = useNavigate();
  const [attempted, setAttempted] = useState(false);

  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-6 px-6 py-16 text-center">
      <h1 className="text-display">Welcome</h1>
      <p className="text-body text-text-secondary">
        We&apos;ll help you keep track of what&apos;s needed for your mortgage application.
      </p>

      {activateMutation.isError && (
        <ErrorState
          title="We couldn't activate your account"
          description="This link may have expired or already been used. Please contact your loan officer for a new invitation."
        />
      )}

      <Button
        variant="primary"
        loading={activateMutation.isPending}
        onClick={() => {
          setAttempted(true);
          activateMutation.mutate(
            { partyId, token },
            {
              onSuccess: () => {
                void navigate({ to: '/portal' });
              },
            },
          );
        }}
      >
        {attempted && activateMutation.isError ? 'Try again' : 'Get started'}
      </Button>
    </div>
  );
}
