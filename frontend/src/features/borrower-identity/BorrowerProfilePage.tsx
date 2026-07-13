/**
 * Borrower Profile (spec 005-enterprise-platform §5, Wave 3 — Borrower
 * Identity Resolution).
 *
 * Entry point is a `partyId` (the one concrete thing every screen that
 * links here already has — an Overview region borrower chip, an RM
 * portfolio row). Two states:
 *
 * - No resolved identity yet: shows this party's pending match candidates
 *   (if any have been computed) with Confirm/Reject actions, plus a
 *   "Check for matches" action that computes candidates against every
 *   other party in the tenant. Every match is advisory — nothing here
 *   auto-merges (Principle I).
 * - A resolved identity exists: shows the identity summary and every
 *   linked application (via `BorrowerIdentityMember`), each a direct link
 *   into that application's Workspace — deliberately terse (application id
 *   + link), not a full case dump, matching the least-privilege framing
 *   already established for cross-application views elsewhere in this spec.
 *
 * Reused, not rebuilt: `Button`, `EmptyState`, `ErrorState`, `Skeleton`
 * (design-system), the existing `useApplication` entity hook for resolving
 * a linked application's loan number.
 */

import { useNavigate } from '@tanstack/react-router';

import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import { useApplication } from '@entities/application/queries';
import {
  useBorrowerIdentity,
  useBorrowerIdentityForParty,
  useBorrowerIdentityMembers,
  useComputeMatchCandidates,
  useConfirmMatch,
  useCrossApplicationSignals,
  useMatchCandidatesForParty,
  useRejectMatch,
} from '@entities/borrower-identity/queries';
import type { IdentityMatchCandidate } from '@entities/borrower-identity/types';

interface BorrowerProfilePageProps {
  readonly partyId: string;
}

export function BorrowerProfilePage({ partyId }: BorrowerProfilePageProps) {
  const identityQuery = useBorrowerIdentityForParty(partyId);

  if (identityQuery.isPending) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (identityQuery.isError) {
    return (
      <ErrorState
        title="Failed to load borrower identity"
        description={
          identityQuery.error instanceof Error ? identityQuery.error.message : 'Unknown error'
        }
        onRetry={() => void identityQuery.refetch()}
      />
    );
  }

  if (identityQuery.data === null) {
    return <UnresolvedIdentity partyId={partyId} />;
  }

  return <ResolvedIdentity identityId={identityQuery.data.id} />;
}

function UnresolvedIdentity({ partyId }: { partyId: string }) {
  const candidatesQuery = useMatchCandidatesForParty(partyId);
  const computeMutation = useComputeMatchCandidates();
  const confirmMutation = useConfirmMatch();
  const rejectMutation = useRejectMatch();

  if (candidatesQuery.isPending) {
    return <Skeleton className="h-9 w-full" />;
  }
  if (candidatesQuery.isError) {
    return (
      <ErrorState
        title="Failed to load match candidates"
        description={
          candidatesQuery.error instanceof Error ? candidatesQuery.error.message : 'Unknown error'
        }
        onRetry={() => void candidatesQuery.refetch()}
      />
    );
  }

  const pending = candidatesQuery.data.items.filter((c) => c.status === 'PENDING');

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-heading">Borrower Profile</h2>
        <Button
          variant="secondary"
          loading={computeMutation.isPending}
          onClick={() => {
            computeMutation.mutate(partyId);
          }}
        >
          Check for matches
        </Button>
      </div>

      {pending.length === 0 ? (
        <EmptyState
          title="No resolved identity yet"
          description="This borrower has not been matched to any other application. Use “Check for matches” to look for candidates across this tenant's other applications."
        />
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Match candidates">
          {pending.map((candidate: IdentityMatchCandidate) => (
            <li
              key={candidate.id}
              className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-2 p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-body font-medium">
                  Possible match — {(candidate.matchScore * 100).toFixed(0)}% confidence
                </span>
              </div>
              <p className="text-caption text-text-tertiary">
                Basis:{' '}
                {Object.entries(candidate.matchBasis)
                  .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
                  .join(', ')}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  loading={confirmMutation.isPending}
                  onClick={() => {
                    confirmMutation.mutate(candidate.id);
                  }}
                >
                  Confirm match
                </Button>
                <Button
                  variant="secondary"
                  loading={rejectMutation.isPending}
                  onClick={() => {
                    rejectMutation.mutate({ candidateId: candidate.id });
                  }}
                >
                  Reject
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ResolvedIdentity({ identityId }: { identityId: string }) {
  const identityQuery = useBorrowerIdentity(identityId);
  const membersQuery = useBorrowerIdentityMembers(identityId);

  if (identityQuery.isPending || membersQuery.isPending) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (identityQuery.isError) {
    return (
      <ErrorState
        title="Failed to load borrower identity"
        description={
          identityQuery.error instanceof Error ? identityQuery.error.message : 'Unknown error'
        }
        onRetry={() => void identityQuery.refetch()}
      />
    );
  }
  if (membersQuery.isError) {
    return (
      <ErrorState
        title="Failed to load linked applications"
        description={
          membersQuery.error instanceof Error ? membersQuery.error.message : 'Unknown error'
        }
        onRetry={() => void membersQuery.refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-heading">
          {identityQuery.data.primaryDisplayName || 'Borrower Profile'}
        </h2>
        <p className="text-caption text-text-tertiary">
          Resolved identity — {membersQuery.data.items.length} linked application
          {membersQuery.data.items.length === 1 ? '' : 's'}
        </p>
      </div>
      <ul className="flex flex-col gap-1" aria-label="Linked applications">
        {membersQuery.data.items.map((member) => (
          <LinkedApplicationRow
            key={member.id}
            applicationId={member.applicationId}
            linkedAt={member.linkedAt}
          />
        ))}
      </ul>
      <CrossApplicationSignals identityId={identityId} />
    </div>
  );
}

/**
 * Cross-Application Intelligence (spec 005 §6, Wave 3) — observations only,
 * never a decision; each cites its own supporting application/document/
 * finding ids rather than a bare score (Principle III).
 */
function CrossApplicationSignals({ identityId }: { identityId: string }) {
  const signalsQuery = useCrossApplicationSignals(identityId);

  if (signalsQuery.isPending) {
    return <Skeleton className="h-9 w-full" />;
  }
  if (signalsQuery.isError) {
    return (
      <ErrorState
        title="Failed to load cross-application signals"
        description={
          signalsQuery.error instanceof Error ? signalsQuery.error.message : 'Unknown error'
        }
        onRetry={() => void signalsQuery.refetch()}
      />
    );
  }

  const observations = signalsQuery.data.items;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-heading">Cross-Application Signals</h3>
      {observations.length === 0 ? (
        <EmptyState
          title="No cross-application patterns observed"
          description="No reused documents, repeated finding types, or prior review history were found across this borrower's linked applications."
        />
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Cross-application signals">
          {observations.map((observation, index) => (
            <li
              key={`${observation.kind}-${String(index)}`}
              className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-1 p-3"
            >
              <span className="text-caption text-text-tertiary uppercase tracking-wide">
                {observation.kind.replaceAll('_', ' ')}
              </span>
              <p className="text-body">{observation.description}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LinkedApplicationRow({
  applicationId,
  linkedAt,
}: {
  readonly applicationId: string;
  readonly linkedAt: string;
}) {
  const applicationQuery = useApplication(applicationId);
  const navigate = useNavigate();

  const label =
    applicationQuery.data?.loanNumber ?? applicationQuery.data?.losReference ?? applicationId;

  return (
    <li className="bg-surface-raised shadow-raised rounded-container flex items-center justify-between p-3">
      <div>
        <span className="text-body tabular-nums font-medium">{label}</span>
        <span className="text-caption text-text-tertiary ml-2">
          linked {new Date(linkedAt).toLocaleDateString()}
        </span>
      </div>
      <Button
        variant="secondary"
        onClick={() =>
          void navigate({
            to: '/applications/$applicationId',
            params: { applicationId },
            search: { region: 'overview' },
          })
        }
      >
        Open
      </Button>
    </li>
  );
}
