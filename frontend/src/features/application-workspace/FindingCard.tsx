/**
 * FindingCard (spec 002 tasks.md T062; plan.md Constitution Check —
 * Principle III, Explainability by Default).
 *
 * Type-gated on all five explainability fields (`what`, `why`,
 * `evidenceRefs`, `confidence`, `recommendedAction`) being present: its
 * `finding` prop requires the full `Finding` type — there is no optional
 * variant, no partial-finding prop shape. A caller cannot compile a call
 * site that renders this component from incomplete data (plan.md:
 * "a partial Finding cannot compile-time-satisfy the render component's
 * required props").
 *
 * Always carries the `AiSignalBadge` (every Finding is AI-generated,
 * Constitution Principle III) and renders its five explainability elements
 * in the same fixed order and grouping every time (spec 003 FR-060) — never
 * reordered or partially presented per screen.
 */

import type { ReactNode } from 'react';

import { AiSignalBadge } from '@design-system/components/AiSignalBadge';
import { ConfidenceIndicator } from '@design-system/components/ConfidenceIndicator';
import { EvidenceChip } from '@design-system/components/EvidenceChip';
import { cn } from '@design-system/lib/cn';
import type { EvidenceItem } from '@entities/evidence/queries';
import type { Finding } from '@entities/finding/queries';

const STATE_LABEL: Record<Finding['state'], string> = {
  unreviewed: 'Unreviewed',
  verified: 'Verified',
  overridden: 'Overridden',
  escalated: 'Escalated',
};

const STATE_CLASS_NAME: Record<Finding['state'], string> = {
  unreviewed: 'text-text-secondary',
  verified: 'text-feedback-success-fg',
  overridden: 'text-feedback-warning-fg',
  escalated: 'text-feedback-error-fg',
};

export interface FindingCardProps {
  readonly finding: Finding;
  /** Evidence items this finding cites, for resolving each `EvidenceChip`'s label. */
  readonly evidenceItems: readonly EvidenceItem[];
  readonly onEvidenceChipActivate: (evidenceItem: EvidenceItem) => void;
  readonly actions?: ReactNode;
  readonly className?: string;
}

export function FindingCard({
  finding,
  evidenceItems,
  onEvidenceChipActivate,
  actions,
  className,
}: FindingCardProps) {
  const evidenceById = new Map(evidenceItems.map((item) => [item.id, item]));

  return (
    <article
      className={cn(
        'border-border-subtle bg-surface-raised flex flex-col gap-3 rounded-container border p-5',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <AiSignalBadge variant="signal" />
        <span className={cn('text-label font-medium', STATE_CLASS_NAME[finding.state])}>
          {STATE_LABEL[finding.state]}
          {finding.state === 'escalated' && finding.escalatedToRole !== null && (
            <> &mdash; {finding.escalatedToRole}</>
          )}
        </span>
      </div>

      <h3 className="text-heading-section text-text-primary">{finding.what}</h3>

      <p className="text-body text-text-secondary max-w-[68ch]">{finding.why}</p>

      <div className="flex flex-wrap items-center gap-2">
        {finding.evidenceRefs.map((evidenceId) => {
          const item = evidenceById.get(evidenceId);
          return (
            <EvidenceChip
              key={evidenceId}
              label={item !== undefined ? item.evidenceType : 'Evidence'}
              onClick={
                item !== undefined
                  ? () => {
                      onEvidenceChipActivate(item);
                    }
                  : undefined
              }
              disabled={item === undefined}
            />
          );
        })}
      </div>

      <ConfidenceIndicator level={finding.confidence} />

      <p className="text-label text-text-primary">
        <span className="text-text-secondary">Recommended action: </span>
        {finding.recommendedAction}
      </p>

      {actions !== undefined && <div className="mt-1">{actions}</div>}
    </article>
  );
}
