/**
 * Application-level pipeline summary (Product Experience phase, Phase 4).
 * The document-level equivalent of `deriveDocumentStages.ts` — a pure
 * function of already-fetched `Document`/`Finding` lists, agnostic to
 * whether that data arrived via polling or a future push subscription.
 *
 * Three stages — Findings, Policy, Ready for Review — distinct from the
 * four per-document stages (`deriveDocumentStages.ts`) because finding
 * generation runs once per application on submit, not per document
 * (`src/mil/api/deps.py`). "Ready for Review" is explicitly a **client-
 * computed heuristic**, never presented as backend-verified: no
 * application-readiness endpoint exists anywhere in the backend today (the
 * only `is_ready`/`missing_items` fields belong to an unimplemented,
 * unrelated LOS-integration interface). A `FAILED` document counts as
 * terminal/resolved for this heuristic, not a blocker — "ready to start
 * reviewing what did process" is a different question from "did every
 * document succeed," and the aggregate counts below answer that honestly
 * on their own.
 */

import type { PipelineStep } from '@design-system/components/ProcessingPipeline';
import type { Document } from '@entities/document/queries';
import type { Finding } from '@entities/finding/queries';

export interface DocumentAggregateCounts {
  readonly total: number;
  readonly ready: number;
  readonly processing: number;
  readonly failed: number;
}

export function summarizeDocuments(documents: readonly Document[]): DocumentAggregateCounts {
  return {
    total: documents.length,
    ready: documents.filter((doc) => doc.ingestionStatus === 'COMPLETED').length,
    processing: documents.filter(
      (doc) => doc.ingestionStatus === 'PENDING' || doc.ingestionStatus === 'IN_PROGRESS',
    ).length,
    failed: documents.filter((doc) => doc.ingestionStatus === 'FAILED').length,
  };
}

/**
 * Every document has reached a terminal ingestion state (`COMPLETED` or
 * `FAILED` — a `FAILED` document is resolved for this purpose, not still
 * pending). This is the right signal for "stop waiting, start reviewing
 * what did process" (the Ready-for-Review stage below) — but it is
 * deliberately *not* enough on its own to call a zero-findings application
 * "clean": a document can reach FAILED and still contribute zero findings,
 * which is a processing failure, not a clean pass. See
 * `zeroFindingsOutcome` for that distinction.
 */
export function allDocumentsTerminal(documents: readonly Document[]): boolean {
  return (
    documents.length > 0 &&
    documents.every((doc) => doc.ingestionStatus === 'COMPLETED' || doc.ingestionStatus === 'FAILED')
  );
}

/**
 * What a zero-findings application honestly means, for `FindingsRegion`/
 * `PolicyRegion` (Phase 12). Three real, distinguishable states from data
 * already fetched — never conflates "nothing to see" with "we don't know
 * yet" or "something actually broke":
 *
 * - `'pending'`: processing hasn't finished (some document still
 *   `PENDING`/`IN_PROGRESS`, or no documents at all yet) — too early to
 *   say anything.
 * - `'failures'`: every document reached a terminal state, but at least
 *   one `FAILED` — a genuinely clean read is not possible because some
 *   documents were never actually evaluated.
 * - `'clean'`: every document reached `COMPLETED` and none failed —
 *   the only case where "no material issues were detected" is an honest
 *   claim, not an assumption papering over a processing failure.
 */
export type ZeroFindingsOutcome = 'pending' | 'failures' | 'clean';

export function zeroFindingsOutcome(documents: readonly Document[]): ZeroFindingsOutcome {
  if (!allDocumentsTerminal(documents)) return 'pending';
  return documents.some((doc) => doc.ingestionStatus === 'FAILED') ? 'failures' : 'clean';
}

export function deriveApplicationStages(
  documents: readonly Document[],
  findings: readonly Finding[],
): readonly PipelineStep[] {
  const hasFindings = findings.length > 0;
  const allFindingsPolicyEvaluated = hasFindings && findings.every((f) => f.policyVersion !== null);
  const documentsTerminal = allDocumentsTerminal(documents);

  return [
    {
      id: 'findings',
      label: 'Findings',
      status: hasFindings ? 'complete' : 'pending',
    },
    {
      id: 'policy',
      label: 'Policy',
      status: allFindingsPolicyEvaluated ? 'complete' : hasFindings ? 'active' : 'pending',
    },
    {
      id: 'ready-for-review',
      label: 'Ready for Review (estimated)',
      status: documentsTerminal && hasFindings ? 'complete' : 'active',
      detail:
        'Estimated client-side from document and finding status — not a backend-verified readiness check.',
    },
  ];
}
