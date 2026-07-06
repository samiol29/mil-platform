/**
 * AuditTimeline (spec 002 tasks.md T067; spec 003 FR-062).
 *
 * Read-only, chronological, immutable-feeling presentation of an
 * application's audit trail — no edit/delete affordance exists anywhere in
 * this component, reinforcing at the UI layer what `AuditTrailEntry`'s
 * type already guarantees at the type layer (no mutation hook exists to
 * call in the first place).
 */

import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { useAuditTrail } from '@entities/audit/queries';

export interface AuditTimelineProps {
  readonly applicationId: string;
}

export function AuditTimeline({ applicationId }: AuditTimelineProps) {
  const auditQuery = useAuditTrail(applicationId);

  if (auditQuery.isPending) return <LoadingState label="Loading audit trail…" />;
  if (auditQuery.isError) {
    return (
      <ErrorState
        title="Could not load the audit trail"
        onRetry={() => {
          void auditQuery.refetch();
        }}
      />
    );
  }
  if (auditQuery.data.length === 0) {
    return <EmptyState title="No audit events yet" />;
  }

  return (
    <ol className="border-border-subtle flex flex-col gap-3 border-l pl-4">
      {auditQuery.data.map((entry) => (
        <li key={entry.id} className="flex flex-col gap-0.5">
          <span className="text-label text-text-primary font-medium">{entry.eventType}</span>
          <span className="text-caption text-text-tertiary">
            {new Date(entry.occurredAt).toLocaleString()}
            {entry.actorType === 'SYSTEM' ? ' · System' : ' · Reviewer'}
          </span>
        </li>
      ))}
    </ol>
  );
}
