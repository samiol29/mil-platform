/**
 * Per-document pipeline stage derivation (Product Experience phase, Phase
 * 4). Pure function of already-fetched data — no fetching, no polling
 * concerns — so it's agnostic to whether `Document` arrived via polling or
 * (later) a push subscription (see `entities/document/queries.ts`'s
 * WebSocket/SSE seam note).
 *
 * Four stages, not the seven an idealized pipeline narrative might suggest:
 * `Document.ingestionStatus` (`PENDING/IN_PROGRESS/COMPLETED/FAILED`) is the
 * *only* per-document status the backend API exposes today. A real OCR-vs-
 * Extraction split exists in the database (`WorkflowStep.step_name` —
 * `OCR`/`EXTRACTION`, one `WorkflowRun` per document, `src/workers/
 * document_pipeline.py`) but has zero REST surface — no route reads it.
 * Rendering OCR and Extraction as two independently-tracked steps today
 * would fabricate granularity the frontend cannot actually observe; this
 * function deliberately collapses them into one "Processing" stage. If a
 * future backend change exposes `WorkflowStep`, this is the one place that
 * splits it into two.
 */

import type { Document } from '@entities/document/queries';

import type {
  PipelineStep,
  PipelineStepStatus,
} from '@design-system/components/ProcessingPipeline';

export function deriveDocumentStages(document: Document): readonly PipelineStep[] {
  const { ingestionStatus, evidenceItemCount, ingestionError } = document;

  const processingStatus: PipelineStepStatus =
    ingestionStatus === 'PENDING'
      ? 'pending'
      : ingestionStatus === 'IN_PROGRESS'
        ? 'active'
        : ingestionStatus === 'FAILED'
          ? 'failed'
          : 'complete';

  const evidenceStatus: PipelineStepStatus =
    processingStatus === 'failed'
      ? 'skipped'
      : processingStatus !== 'complete'
        ? 'pending'
        : evidenceItemCount > 0
          ? 'complete'
          : 'pending';

  const readyStatus: PipelineStepStatus =
    processingStatus === 'failed'
      ? 'skipped'
      : ingestionStatus === 'COMPLETED'
        ? 'complete'
        : 'pending';

  return [
    { id: 'upload', label: 'Upload', status: 'complete' },
    {
      id: 'processing',
      label: 'Processing',
      status: processingStatus,
      ...(processingStatus === 'failed' && ingestionError !== null
        ? { detail: ingestionError }
        : {}),
    },
    { id: 'evidence', label: 'Evidence', status: evidenceStatus },
    { id: 'ready', label: 'Ready', status: readyStatus },
  ];
}
