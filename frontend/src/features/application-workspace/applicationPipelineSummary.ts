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

export function deriveApplicationStages(
  documents: readonly Document[],
  findings: readonly Finding[],
): readonly PipelineStep[] {
  const hasFindings = findings.length > 0;
  const allFindingsPolicyEvaluated = hasFindings && findings.every((f) => f.policyVersion !== null);
  const allDocumentsTerminal =
    documents.length > 0 &&
    documents.every((doc) => doc.ingestionStatus === 'COMPLETED' || doc.ingestionStatus === 'FAILED');

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
      status: allDocumentsTerminal && hasFindings ? 'complete' : 'active',
      detail:
        'Estimated client-side from document and finding status — not a backend-verified readiness check.',
    },
  ];
}
