/**
 * AI Case Copilot panel (spec 005-enterprise-platform §8).
 *
 * The backend for this module (`src/mil/copilot/*`, `src/mil/api/v1/
 * copilot.py`) was already fully built, tested, RBAC-enforced, and mounted
 * before this wave — this component is the first frontend surface that
 * consumes it. A collapsible panel inside the Overview region (research.md
 * R3), not a new route or region: keeps the application always in view,
 * since asking a question is fundamentally "about the thing already open."
 *
 * Every citation is mandatory grounding, per the backend's own contract
 * (`CopilotService`/ADR-011: no answer without a resolvable citation, or a
 * safe "insufficient grounding" response instead of a fabrication). DOCUMENT
 * citations reuse the exact same `DocumentJumpTarget` mechanism Evidence/
 * Findings/Policy already use — no second navigation channel.
 */

import { useState } from 'react';
import { MessageCircleQuestion } from 'lucide-react';

import { Button } from '@design-system/components/Button';
import { ErrorState } from '@design-system/components/ErrorState';
import { LoadingState } from '@design-system/components/LoadingState';
import { Textarea } from '@design-system/components/Textarea';
import {
  useCopilotHistory,
  useLatestCopilotSession,
  useSubmitCopilotQuery,
} from '@entities/copilot/queries';
import type { Citation } from '@entities/copilot/types';
import type { DocumentJumpTarget } from '@features/document-viewer/DocumentViewer';

/**
 * Human-readable label per real citation kind (final design excellence
 * sprint) — falls back to the raw kind string for forward-compatibility
 * with a kind this frontend doesn't know about yet, never hiding one.
 */
const CITATION_KIND_LABEL: Record<string, string> = {
  APPLICATION: 'Application',
  DOCUMENT: 'Document',
  DOCUMENT_TEXT: 'Document text',
  EVIDENCE: 'Evidence',
  FINDING: 'Finding',
  POLICY_RESULT: 'Policy result',
  REVIEW_ACTION: 'Review action',
};

/** Truncated the same way every other internal id shown to a reviewer already is (e.g. `resolvePolicyPackName`'s fallback) — a full 36-character UUID is debug output, not a citation a reviewer can act on. */
function truncatedRef(ref: string): string {
  return ref.length > 8 ? `${ref.slice(0, 8)}…` : ref;
}

function CitationChip({
  citation,
  onEvidenceChipActivate,
}: {
  citation: Citation;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
}) {
  const kindLabel = CITATION_KIND_LABEL[citation.kind] ?? citation.kind;
  const label = `${kindLabel}: ${truncatedRef(citation.ref)}${citation.locator !== null ? ` (${citation.locator})` : ''}`;

  if (citation.kind !== 'DOCUMENT') {
    return (
      <span className="bg-surface-secondary text-text-secondary rounded-chip text-caption px-2 py-0.5">
        {label}
      </span>
    );
  }

  const pageNumber =
    citation.locator !== null && /^\d+$/.test(citation.locator) ? Number(citation.locator) : 1;

  return (
    <button
      type="button"
      onClick={() => {
        onEvidenceChipActivate({
          documentId: citation.ref,
          pageNumber,
          boundingBox: null,
          label: 'Copilot citation',
        });
      }}
      className="bg-surface-secondary text-text-primary hover:bg-surface-disabled rounded-chip text-caption px-2 py-0.5 outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
    >
      {label} →
    </button>
  );
}

export function CopilotPanel({
  applicationId,
  onEvidenceChipActivate,
}: {
  applicationId: string;
  onEvidenceChipActivate: (jump: DocumentJumpTarget) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [question, setQuestion] = useState('');
  const sessionQuery = useLatestCopilotSession(applicationId);
  const sessionId = sessionQuery.data?.id ?? null;
  const historyQuery = useCopilotHistory(sessionId);
  const submitQuery = useSubmitCopilotQuery();

  const handleAsk = () => {
    if (question.trim().length === 0) return;
    submitQuery.mutate(
      { applicationId, question, ...(sessionId !== null ? { sessionId } : {}) },
      {
        onSuccess: () => {
          setQuestion('');
        },
      },
    );
  };

  return (
    <div className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-3 p-4">
      <button
        type="button"
        onClick={() => {
          setExpanded((v) => !v);
        }}
        className="flex items-center gap-2 text-left outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
      >
        <MessageCircleQuestion size={18} />
        <span className="text-label text-text-primary font-medium">
          Ask Copilot about this application
        </span>
      </button>

      {expanded && (
        <div className="flex flex-col gap-3">
          {sessionQuery.isPending ? (
            <LoadingState label="Loading conversation…" />
          ) : historyQuery.isError ? (
            <ErrorState
              title="Could not load Copilot history"
              onRetry={() => void historyQuery.refetch()}
            />
          ) : (
            <ul className="flex max-h-80 flex-col gap-3 overflow-y-auto">
              {(historyQuery.data?.items ?? []).length === 0 ? (
                <li className="text-caption text-text-tertiary">
                  No questions asked yet on this application.
                </li>
              ) : (
                (historyQuery.data?.items ?? []).map((item) => (
                  <li key={item.queryId} className="flex flex-col gap-1.5">
                    <p className="text-body text-text-primary font-medium">{item.question}</p>
                    {item.response !== null ? (
                      <>
                        <p className="text-body text-text-secondary">{item.response.answer}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {item.response.citations.map((citation, index) => (
                            <CitationChip
                              key={`${citation.kind}-${citation.ref}-${String(index)}`}
                              citation={citation}
                              onEvidenceChipActivate={onEvidenceChipActivate}
                            />
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="text-caption text-text-tertiary">Awaiting response…</p>
                    )}
                  </li>
                ))
              )}
            </ul>
          )}

          <div className="flex flex-col gap-2">
            <Textarea
              aria-label="Ask a question about this application"
              value={question}
              onChange={(e) => {
                setQuestion(e.target.value);
              }}
              placeholder="What evidence supports the income finding?"
              rows={2}
            />
            <div className="flex items-center justify-between gap-2">
              {submitQuery.isError && (
                <p className="text-caption text-feedback-error-fg">
                  {submitQuery.error instanceof Error
                    ? submitQuery.error.message
                    : 'Failed to ask Copilot'}
                </p>
              )}
              <Button
                variant="primary"
                size="sm"
                disabled={question.trim().length === 0}
                loading={submitQuery.isPending}
                onClick={handleAsk}
                className="ml-auto"
              >
                Ask
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
