/**
 * A single upload row (Product Experience phase, Phase 3, Principle 2 —
 * "the row is the unit of trust"). The same row renders through every
 * stage: staged → uploading → uploaded → then driven by the real polled
 * `Document.ingestionStatus` (`entities/document/queries.ts`) once it
 * exists — never a screen swap (Principle 6).
 */

import { AlertTriangle, CheckCircle2, Copy, Loader2, RotateCw, X } from 'lucide-react';

import { Select } from '@design-system/components/Select';
import { cn } from '@design-system/lib/cn';
import type { Document } from '@entities/document/queries';

import { DOCUMENT_TYPES, DOCUMENT_TYPE_LABEL, type DocumentType } from './documentTypeDetection';
import type { UploadRow } from './types';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${String(bytes)} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ingestionStatusLabel(status: Document['ingestionStatus']): string {
  switch (status) {
    case 'PENDING':
      return 'Queued for processing';
    case 'IN_PROGRESS':
      return 'Processing…';
    case 'COMPLETED':
      return 'Ready';
    case 'FAILED':
      return 'Processing failed';
  }
}

export interface UploadFileRowProps {
  readonly row: UploadRow;
  /** The live document once uploaded — drives the post-upload status via real polling, not local state. */
  readonly polledDocument: Document | undefined;
  readonly onDocumentTypeChange: (type: DocumentType) => void;
  readonly onAcknowledgeDuplicate: () => void;
  readonly onRemove: () => void;
  readonly onRetry: () => void;
}

export function UploadFileRow({
  row,
  polledDocument,
  onDocumentTypeChange,
  onAcknowledgeDuplicate,
  onRemove,
  onRetry,
}: UploadFileRowProps) {
  const canEditType = row.status === 'staged' || row.status === 'error';
  const canRemove = row.status === 'staged' || row.status === 'error';

  return (
    <div className="border-border-subtle flex flex-col gap-2 border-b px-3 py-2.5 last:border-b-0">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-body-emphasis text-text-primary truncate" title={row.file.name}>
            {row.file.name}
          </p>
          <p className="text-caption text-text-tertiary">{formatBytes(row.file.size)}</p>
        </div>

        <div className="w-44 shrink-0">
          <Select
            value={row.documentType}
            disabled={!canEditType}
            onChange={(event) => {
              onDocumentTypeChange(event.target.value as DocumentType);
            }}
            aria-label={`Document type for ${row.file.name}`}
          >
            {DOCUMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {DOCUMENT_TYPE_LABEL[type]}
              </option>
            ))}
          </Select>
        </div>

        <div className="w-40 shrink-0 text-right">
          <RowStatus row={row} polledDocument={polledDocument} />
        </div>

        {canRemove && (
          <button
            type="button"
            aria-label={`Remove ${row.file.name}`}
            onClick={onRemove}
            className={cn(
              'rounded-interactive text-text-tertiary shrink-0 p-1.5',
              'hover:bg-surface-disabled hover:text-text-critical',
              'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
            )}
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
        {row.status === 'error' && (
          <button
            type="button"
            aria-label={`Retry ${row.file.name}`}
            onClick={onRetry}
            className={cn(
              'rounded-interactive text-text-secondary shrink-0 p-1.5',
              'hover:bg-surface-disabled hover:text-text-primary',
              'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
            )}
          >
            <RotateCw className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>

      {row.status === 'uploading' && (
        <div className="bg-surface-disabled h-1 w-full overflow-hidden rounded-full">
          <div
            className="bg-interactive-primary-default h-full rounded-full transition-all"
            style={{ width: `${String(row.uploadProgress)}%` }}
          />
        </div>
      )}

      {row.validationError !== null && (
        <p className="text-caption text-feedback-error-fg flex items-center gap-1.5">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          {row.validationError}
        </p>
      )}

      {row.status === 'error' && row.uploadError !== null && (
        <p className="text-caption text-feedback-error-fg flex items-center gap-1.5">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          {row.uploadError}
        </p>
      )}

      {row.unrecognizedExtension && row.validationError === null && (
        <p className="text-caption text-feedback-warning-fg flex items-center gap-1.5">
          <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
          Unrecognized file type — may not process correctly.
        </p>
      )}

      {row.isDuplicate && row.status === 'staged' && (
        <div className="text-caption text-feedback-warning-fg flex items-center gap-2">
          <Copy className="size-3.5 shrink-0" aria-hidden="true" />
          <span>This looks like a duplicate of a document already on this application.</span>
          {!row.duplicateAcknowledged && (
            <button
              type="button"
              onClick={onAcknowledgeDuplicate}
              className="text-feedback-warning-fg font-medium underline underline-offset-2 outline-none focus-visible:outline-2 focus-visible:outline-focus-ring"
            >
              Upload anyway
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function RowStatus({
  row,
  polledDocument,
}: {
  readonly row: UploadRow;
  readonly polledDocument: Document | undefined;
}) {
  if (row.status === 'staged') {
    return <span className="text-caption text-text-tertiary">Ready to upload</span>;
  }
  if (row.status === 'uploading') {
    return <span className="text-caption text-text-secondary">{row.uploadProgress}%</span>;
  }
  if (row.status === 'error') {
    return (
      <span className="text-caption text-feedback-error-fg inline-flex items-center gap-1">
        <AlertTriangle className="size-3.5" aria-hidden="true" />
        Upload failed
      </span>
    );
  }

  // status === 'uploaded' — from here on, the real polled document drives the label (Principle 6).
  if (polledDocument === undefined) {
    return (
      <span className="text-caption text-text-secondary inline-flex items-center gap-1">
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        Uploaded
      </span>
    );
  }

  if (polledDocument.ingestionStatus === 'COMPLETED') {
    return (
      <span className="text-caption text-feedback-success-fg inline-flex items-center gap-1">
        <CheckCircle2 className="size-3.5" aria-hidden="true" />
        Ready
      </span>
    );
  }
  if (polledDocument.ingestionStatus === 'FAILED') {
    return (
      <span
        className="text-caption text-feedback-error-fg inline-flex items-center gap-1"
        title={polledDocument.ingestionError ?? undefined}
      >
        <AlertTriangle className="size-3.5" aria-hidden="true" />
        {polledDocument.ingestionError ?? 'Processing failed'}
      </span>
    );
  }
  return (
    <span className="text-caption text-text-secondary inline-flex items-center gap-1">
      <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
      {ingestionStatusLabel(polledDocument.ingestionStatus)}
    </span>
  );
}
