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
 * required props"). All five keep the same content and relative order on
 * every render (spec 003 FR-060's actual invariant is consistency across
 * findings, not a frozen layout) — each carries an explicit micro-label
 * ("Issue"/"Why it matters"/"Supporting evidence"/"Impact"/"Recommended
 * reviewer action") making the narrative legible instead of relying on bare
 * heading/paragraph styling to imply it.
 *
 * **Three visual bands (Product Experience phase, Phase 6.5)** literally
 * operationalize this platform's own decision chain — "AI identifies →
 * Policy evaluates → Humans decide":
 * 1. **AI identified** — Issue/Why it matters/Supporting evidence/Impact
 *    (`deriveFindingImpact`, a UI-only synthesis of `confidence` + evidence
 *    count, explicitly captioned as derived — no backend severity field
 *    exists)/`ConfidenceIndicator`.
 * 2. **Policy evaluated** — the real `policyVersion` field (fetched since
 *    Phase 1, first rendered in Phase 6): "Evaluated under policy X" or an
 *    honest "Not yet evaluated against policy" when null. No policy-pack
 *    HTTP route exists anywhere in the backend (confirmed) — this is
 *    deliberately the only policy signal shown, not a placeholder for
 *    rule-level detail that doesn't exist yet.
 * 3. **Your decision** — `recommendedAction` sits directly above the
 *    `actions` slot (`FindingActions`' Verify/Override/Escalate), so the
 *    AI's suggestion and the human's actual decision are visually
 *    adjacent. This band renders before the supplementary disclosures
 *    below, not after — Phase 6.5's whole point: a reviewer should reach
 *    "what should I do?" before wading through AI/audit metadata.
 *
 * **AI details** / **Review history** (collapsed by default, same
 * expandable pattern as `DocumentProcessingList`'s "Details" disclosure)
 * are the deferred "implementation details": real `modelVersion`/
 * `promptVersion`/`extractionVersion`, and a chronological list built by
 * `buildFindingReviewHistory` from the application's already-fetched audit
 * trail — the reviewer's own typed override/escalate rationale, visible
 * after the fact instead of disappearing once the confirm dialog closes. A
 * future comments/discussion thread or policy rule-level detail would
 * extend these two disclosures without a redesign — neither is built here
 * since neither has a backend endpoint yet.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';

import { AiSignalBadge } from '@design-system/components/AiSignalBadge';
import { ConfidenceIndicator } from '@design-system/components/ConfidenceIndicator';
import { EvidenceChip } from '@design-system/components/EvidenceChip';
import { cn } from '@design-system/lib/cn';
import type { EvidenceItem } from '@entities/evidence/queries';
import type { Finding } from '@entities/finding/queries';

import { CommentThread } from './CommentThread';
import { deriveFindingImpact } from './deriveFindingImpact';
import { STATE_CLASS_NAME, STATE_LABEL } from './findingState';
import type { ReviewHistoryEntry } from './findingReviewHistory';
import { formatFindingNarrative } from './formatFindingNarrative';

/**
 * Renders `finding.why` as real paragraphs/lists with bold emphasis instead
 * of the raw markdown-ish text Gemini produces (final polish sprint) — see
 * `formatFindingNarrative`'s own docstring for why no markdown library is
 * introduced for this.
 */
function FindingNarrative({ why }: { readonly why: string }) {
  const blocks = formatFindingNarrative(why);
  return (
    <div className="text-body text-text-secondary flex max-w-[68ch] flex-col gap-2">
      {blocks.map((block, index) =>
        block.kind === 'list' ? (
          <ul key={index} className="list-disc space-y-1 pl-5">
            {block.items.map((segments, itemIndex) => (
              <li key={itemIndex}>
                {segments.map((segment, segmentIndex) =>
                  segment.bold ? (
                    <strong key={segmentIndex} className="text-text-primary font-medium">
                      {segment.text}
                    </strong>
                  ) : (
                    segment.text
                  ),
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p key={index}>
            {block.segments.map((segment, segmentIndex) =>
              segment.bold ? (
                <strong key={segmentIndex} className="text-text-primary font-medium">
                  {segment.text}
                </strong>
              ) : (
                segment.text
              ),
            )}
          </p>
        ),
      )}
    </div>
  );
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function reviewHistoryLine(entry: ReviewHistoryEntry): string {
  const actor = entry.actorType === 'SYSTEM' ? 'the system' : 'a reviewer';
  const when = formatDate(entry.occurredAt);
  switch (entry.kind) {
    case 'verified':
      return `Verified by ${actor} on ${when}.`;
    case 'overridden':
      return `Overridden by ${actor} on ${when}: "${entry.reason ?? ''}" (was ${entry.previousValue ?? '—'} → ${entry.newValue ?? '—'}).`;
    case 'escalated':
      return `Escalated to ${entry.targetRole ?? 'another role'} by ${actor} on ${when}: "${entry.reason ?? ''}".`;
  }
}

export interface FindingCardProps {
  readonly finding: Finding;
  /** Evidence items this finding cites, for resolving each `EvidenceChip`'s label. */
  readonly evidenceItems: readonly EvidenceItem[];
  readonly onEvidenceChipActivate: (evidenceItem: EvidenceItem) => void;
  /** Product Experience phase, Phase 6 — this finding's decision trail, built from the application's audit trail. */
  readonly reviewHistory?: readonly ReviewHistoryEntry[];
  readonly actions?: ReactNode;
  readonly className?: string;
}

const EVIDENCE_CHIP_VISIBLE_LIMIT = 8;

export function FindingCard({
  finding,
  evidenceItems,
  onEvidenceChipActivate,
  reviewHistory = [],
  actions,
  className,
}: FindingCardProps) {
  const evidenceById = new Map(evidenceItems.map((item) => [item.id, item]));
  const [aiDetailsOpen, setAiDetailsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [allEvidenceShown, setAllEvidenceShown] = useState(false);

  const visibleEvidenceRefs =
    allEvidenceShown || finding.evidenceRefs.length <= EVIDENCE_CHIP_VISIBLE_LIMIT
      ? finding.evidenceRefs
      : finding.evidenceRefs.slice(0, EVIDENCE_CHIP_VISIBLE_LIMIT);
  const hiddenEvidenceCount = finding.evidenceRefs.length - visibleEvidenceRefs.length;

  return (
    <article
      className={cn(
        'bg-surface-raised shadow-raised flex flex-col gap-3 rounded-container p-5',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <AiSignalBadge variant="signal" />
        <span
          className={cn(
            'text-label font-medium transition-colors duration-panel ease-standard',
            STATE_CLASS_NAME[finding.state],
          )}
        >
          {STATE_LABEL[finding.state]}
          {finding.state === 'escalated' && finding.escalatedToRole !== null && (
            <> &mdash; {finding.escalatedToRole}</>
          )}
        </span>
      </div>

      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-caption text-text-tertiary tracking-wide uppercase">
            Finding Summary
          </p>
          <h3 className="text-heading-section text-text-primary">{finding.what}</h3>
        </div>
        <ConfidenceIndicator level={finding.confidence} className="shrink-0 pt-4" />
      </div>

      <div>
        <p className="text-caption text-text-tertiary tracking-wide uppercase">Analysis</p>
        <FindingNarrative why={finding.why} />
      </div>

      <div>
        <p className="text-caption text-text-tertiary mb-2 tracking-wide uppercase">
          Supporting Evidence
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {visibleEvidenceRefs.map((evidenceId) => {
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
          {hiddenEvidenceCount > 0 && (
            <button
              type="button"
              onClick={() => {
                setAllEvidenceShown(true);
              }}
              className="text-caption text-text-secondary hover:text-text-primary rounded-interactive outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
            >
              +{hiddenEvidenceCount} more
            </button>
          )}
        </div>
      </div>

      <div>
        <p className="text-caption text-text-tertiary tracking-wide uppercase">Business Impact</p>
        <p className="text-body text-text-primary">{deriveFindingImpact(finding)}</p>
        <p className="text-caption text-text-tertiary">
          Derived from confidence and evidence count — not a backend-assigned risk score.
        </p>
      </div>

      <div className="border-border-subtle border-t pt-3">
        <p className="text-caption text-text-tertiary tracking-wide uppercase">
          Policy Evaluation
        </p>
        <p className="text-body text-text-tertiary">
          {finding.policyVersion !== null
            ? `Evaluated under policy ${finding.policyVersion}`
            : 'Not yet evaluated against policy'}
        </p>
      </div>

      <div className="bg-surface-secondary rounded-container flex flex-col gap-2 p-3">
        <p className="text-caption text-text-tertiary tracking-wide uppercase">Recommendation</p>
        <p className="text-label text-text-primary">{finding.recommendedAction}</p>
        {actions !== undefined && (
          <div className="border-border-subtle mt-1 flex flex-col gap-2 border-t pt-2">
            <p className="text-caption text-text-tertiary tracking-wide uppercase">
              Reviewer Action
            </p>
            {actions}
          </div>
        )}
      </div>

      <div className="border-border-subtle flex flex-col gap-2 border-t pt-2">
        <button
          type="button"
          onClick={() => {
            setAiDetailsOpen((open) => !open);
          }}
          className="text-caption text-text-secondary hover:text-text-primary self-start outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
        >
          {aiDetailsOpen ? 'Hide AI details' : 'AI details'}
        </button>
        {aiDetailsOpen && (
          <dl className="text-caption text-text-secondary animate-panel-in grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <dt className="text-text-tertiary">Model version</dt>
            <dd>{finding.modelVersion}</dd>
            <dt className="text-text-tertiary">Prompt version</dt>
            <dd>{finding.promptVersion}</dd>
            <dt className="text-text-tertiary">Extraction version</dt>
            <dd>{finding.extractionVersion}</dd>
          </dl>
        )}

        <button
          type="button"
          onClick={() => {
            setHistoryOpen((open) => !open);
          }}
          className="text-caption text-text-secondary hover:text-text-primary self-start outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
        >
          {historyOpen ? 'Hide review history' : 'Review history'}
        </button>
        {historyOpen &&
          (reviewHistory.length > 0 ? (
            <ul className="text-caption text-text-secondary animate-panel-in flex flex-col gap-1">
              {reviewHistory.map((entry) => (
                <li key={entry.id}>{reviewHistoryLine(entry)}</li>
              ))}
            </ul>
          ) : (
            <p className="text-caption text-text-tertiary animate-panel-in">
              No review decisions recorded yet.
            </p>
          ))}

        <button
          type="button"
          onClick={() => {
            setCommentsOpen((open) => !open);
          }}
          className="text-caption text-text-secondary hover:text-text-primary self-start outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
        >
          {commentsOpen ? 'Hide comments' : 'Comments'}
        </button>
        {commentsOpen && (
          <div className="animate-panel-in">
            <CommentThread findingId={finding.id} />
          </div>
        )}
      </div>
    </article>
  );
}
