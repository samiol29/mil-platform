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
import type { Application, EvaluationStatus } from '@entities/application/types';
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
    documents.every(
      (doc) => doc.ingestionStatus === 'COMPLETED' || doc.ingestionStatus === 'FAILED',
    )
  );
}

/**
 * What a zero-findings application honestly means, for `FindingsRegion`/
 * `PolicyRegion`. Five real, distinguishable states from data already
 * fetched — never conflates "nothing to see" with "we don't know yet",
 * "AI evaluation never ran", or "something actually broke":
 *
 * - `'not-submitted'`: the application is still DRAFT — Finding Generation
 *   is only ever triggered by the DRAFT -> SUBMITTED transition (ADR-009),
 *   so there is nothing to find yet, no matter how much evidence exists.
 *   This is the exact "16 uploaded / 7 processed / 9 failed, no findings"
 *   symptom's real root cause (final product polish sprint) — previously
 *   indistinguishable from `'failures'` below.
 * - `'evaluation-failed'`: the application was submitted and evaluation
 *   genuinely ran, but its most recent FINDING_GENERATION run ended FAILED
 *   (e.g. an AI provider outage) — retryable via `useRetryEvaluation`.
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
export type ZeroFindingsOutcome =
  'not-submitted' | 'evaluation-failed' | 'pending' | 'failures' | 'clean';

export function zeroFindingsOutcome(
  documents: readonly Document[],
  applicationStatus: Application['status'],
  evaluationStatus: EvaluationStatus | undefined,
): ZeroFindingsOutcome {
  if (applicationStatus === 'DRAFT') return 'not-submitted';
  if (evaluationStatus?.status === 'FAILED') return 'evaluation-failed';
  if (!allDocumentsTerminal(documents)) return 'pending';
  return documents.some((doc) => doc.ingestionStatus === 'FAILED') ? 'failures' : 'clean';
}

/**
 * The application's real lifecycle ladder (final product polish sprint,
 * refinement R1). Every step is backed by a real, named field or
 * derivation — never a fabricated status:
 *
 * - `submitted`: `Application.status` — real backend field, DRAFT vs.
 *   everything else (SUBMITTED/IN_REVIEW/REVIEW_COMPLETE/WITHDRAWN).
 * - `findings`/`policy`: unchanged from before — derived from real
 *   `Finding.policyVersion`/count.
 * - `evaluation`: the real FINDING_GENERATION run outcome
 *   (`useEvaluationStatus`) — `failed` renders distinctly so a Gemini
 *   outage reads as "evaluation failed, retry available", never silently
 *   as "still processing".
 *
 * Two real backend gaps this ladder deliberately does NOT paper over
 * (disclosed, not fabricated): there is no application-level reviewer
 * verdict aggregation (only per-finding APPROVED/REJECTED/OVERRIDDEN/
 * ESCALATED exist — see `FindingsRegion`'s reviewer summary), and no
 * "push final decision to LOS" endpoint exists (only the manual readiness
 * push in `LOSSyncPanel`). Both are out of scope for this ladder.
 */
export function deriveApplicationStages(
  findings: readonly Finding[],
  applicationStatus: Application['status'],
  evaluationStatus: EvaluationStatus | undefined,
): readonly PipelineStep[] {
  const hasFindings = findings.length > 0;
  const allFindingsPolicyEvaluated = hasFindings && findings.every((f) => f.policyVersion !== null);
  const submitted = applicationStatus !== 'DRAFT';

  const evaluationStep: PipelineStep =
    evaluationStatus?.status === 'FAILED'
      ? {
          id: 'evaluation',
          label: 'Evaluation',
          status: 'failed',
          detail: evaluationStatus.errorMessage ?? 'The last evaluation attempt failed.',
        }
      : {
          id: 'evaluation',
          label: 'Evaluation',
          status:
            hasFindings || evaluationStatus?.status === 'COMPLETED'
              ? 'complete'
              : submitted
                ? 'active'
                : 'pending',
        };

  return [
    {
      id: 'submitted',
      label: 'Submitted',
      status: submitted ? 'complete' : 'active',
    },
    evaluationStep,
    {
      id: 'findings',
      label: 'Findings',
      status: hasFindings ? 'complete' : submitted ? 'active' : 'pending',
    },
    {
      id: 'policy',
      label: 'Policy',
      status: allFindingsPolicyEvaluated ? 'complete' : hasFindings ? 'active' : 'pending',
    },
  ];
}
