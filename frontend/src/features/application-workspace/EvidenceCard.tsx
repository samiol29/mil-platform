/**
 * EvidenceCard (Product Experience phase, Phase 5) — the investigation-
 * grade unit for a single piece of evidence. Mirrors `FindingCard.tsx`'s
 * *composition* (the same `AiSignalBadge`/`ConfidenceIndicator`/
 * `EvidenceChip` design-system primitives, none of which are coupled to
 * `Finding` specifically), not its shape — a `Finding`-shaped card cannot
 * represent an `EvidenceItem` as-is.
 *
 * Leads with provenance and confidence, not the raw value (Principle 1 of
 * the investigation-workspace refinement): `AiSignalBadge` → type + value →
 * `ConfidenceIndicator` → a provenance line built entirely from real fields
 * (`extractionMethod`, `extractionModelVersion`, `extractedAt`) → a "View in
 * document" action reusing the exact same `DocumentJumpTarget` mechanism
 * `FindingCard`'s evidence chips already use (not a parallel one) →, when
 * resolvable, a reverse link to the finding(s) that cite this item.
 *
 * `supersedesId` gets its first-ever UI treatment here: when non-null and
 * resolvable against the same already-fetched evidence list, a plain
 * "Supersedes an earlier extraction from {date}" line — real data, no
 * fabricated lineage graph. `pageNumber`/`fieldLocation` being `null` is
 * shown honestly ("Page —", no highlight) — this component never presents
 * the `?? 1` navigation fallback (`ApplicationWorkspace.tsx`'s jump-target
 * construction) as if it were real displayed data.
 *
 * This card's provenance section is the intended seam for future work
 * (an AI-explanation string, a fuller lineage chain, conflict detection)
 * to extend into — no such field exists on `EvidenceItem` today, so none
 * of that is built or faked here.
 */

import { FileText } from 'lucide-react';

import { AiSignalBadge } from '@design-system/components/AiSignalBadge';
import { ConfidenceIndicator } from '@design-system/components/ConfidenceIndicator';
import { EvidenceChip } from '@design-system/components/EvidenceChip';
import type { EvidenceItem } from '@entities/evidence/queries';

function formatEvidenceType(evidenceType: string): string {
  return evidenceType.replaceAll('_', ' ');
}

function formatValue(item: EvidenceItem): string {
  if (item.valueNumeric !== null) {
    return item.currency !== null ? `${item.currency} ${item.valueNumeric}` : item.valueNumeric;
  }
  return item.valueText ?? '—';
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export interface EvidenceCardProps {
  readonly item: EvidenceItem;
  /** Resolved client-side (same already-fetched evidence list) when `item.supersedesId` is set and matches a known item. */
  readonly supersededItem?: EvidenceItem;
  readonly relatedFindingsCount: number;
  readonly onViewInDocument: () => void;
  readonly onViewFindings?: () => void;
}

export function EvidenceCard({
  item,
  supersededItem,
  relatedFindingsCount,
  onViewInDocument,
  onViewFindings,
}: EvidenceCardProps) {
  return (
    <article className="bg-surface-raised shadow-raised flex flex-col gap-2 rounded-container p-3">
      <div className="flex items-center justify-between gap-3">
        <AiSignalBadge variant="signal" />
        <span className="text-caption text-text-tertiary">
          Page {item.pageNumber ?? '—'}
        </span>
      </div>

      <div>
        <p className="text-caption text-text-tertiary tracking-wide uppercase">
          {formatEvidenceType(item.evidenceType)}
        </p>
        <p className="text-heading-section text-text-primary">{formatValue(item)}</p>
      </div>

      <ConfidenceIndicator level={item.confidence} />

      <p className="text-caption text-text-tertiary">
        Extracted via {item.extractionMethod} · model {item.extractionModelVersion} ·{' '}
        {formatDate(item.extractedAt)}
      </p>

      {supersededItem !== undefined && (
        <p className="text-caption text-text-tertiary">
          Supersedes an earlier extraction from {formatDate(supersededItem.extractedAt)}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <EvidenceChip icon={FileText} label="View in document" onClick={onViewInDocument} />
        {relatedFindingsCount > 0 && onViewFindings !== undefined && (
          <EvidenceChip
            label={`Used in ${String(relatedFindingsCount)} finding${relatedFindingsCount === 1 ? '' : 's'} →`}
            onClick={onViewFindings}
          />
        )}
      </div>
    </article>
  );
}
