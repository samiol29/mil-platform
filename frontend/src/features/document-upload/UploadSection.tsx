/**
 * Upload section (Product Experience phase, Phase 3) — the orchestrator:
 * stages files (validation, duplicate-hash check, type detection), runs a
 * concurrency-limited upload batch, and lets each row's status flow
 * seamlessly into the real polled `ingestionStatus` once uploaded
 * (Principle 6 — see `UploadFileRow.tsx`).
 *
 * Mounted inline in the Documents region (`ApplicationWorkspace.tsx`), not
 * a Drawer — a Drawer would break the "one continuous screen" feel this
 * phase is built around. Expanded by default when the application has zero
 * documents (wired from `DocumentViewer.tsx`'s empty-state action);
 * collapsed to an "Add more documents" affordance once documents exist.
 */

import { ChevronDown, ChevronRight, Upload } from 'lucide-react';
import { useState } from 'react';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { Dropzone } from '@design-system/components/Dropzone';
import { Select } from '@design-system/components/Select';
import { COLLAPSIBLE_GROUP_HEADER_CLASS } from '@design-system/lib/collapsibleGroupHeader';
import { cn } from '@design-system/lib/cn';
import { useDocumentsForApplication, useUploadDocument } from '@entities/document/queries';
import { usePartiesForApplication } from '@entities/party/queries';
import { PARTY_TYPE_LABEL } from '@entities/party/types';
import { extractErrorMessage } from '@shared/api/extractErrorMessage';

import {
  DOCUMENT_TYPE_LABEL,
  detectDocumentType,
  hasUnrecognizedExtension,
  type DocumentType,
} from './documentTypeDetection';
import { sha256Hex } from './fileHash';
import type { UploadRow } from './types';
import { UploadFileRow } from './UploadFileRow';

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024; // Mirrors the real backend default, `mil_max_upload_bytes` (see plan) — if it ever drifts, the server's own 413 is surfaced verbatim.
const MAX_UPLOAD_MB = 25;
const MAX_CONCURRENT_UPLOADS = 3;

async function runWithConcurrencyLimit<T, R>(
  items: readonly T[],
  limit: number,
  worker: (item: T) => Promise<R>,
): Promise<readonly R[]> {
  const results: R[] = [];
  let index = 0;
  async function next(): Promise<void> {
    const current = index;
    index += 1;
    if (current >= items.length) return;
    results[current] = await worker(items[current]);
    await next();
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => next()));
  return results;
}

export interface UploadSectionProps {
  readonly applicationId: string;
  readonly expanded: boolean;
  readonly onExpandedChange: (expanded: boolean) => void;
}

export function UploadSection({ applicationId, expanded, onExpandedChange }: UploadSectionProps) {
  const [rows, setRows] = useState<readonly UploadRow[]>([]);
  const [partyId, setPartyId] = useState<string | undefined>(undefined);
  const [collapsedGroups, setCollapsedGroups] = useState<ReadonlySet<DocumentType>>(new Set());

  const documentsQuery = useDocumentsForApplication(applicationId);
  const partiesQuery = usePartiesForApplication(applicationId);
  const uploadDocument = useUploadDocument(applicationId);
  const addToast = useUiStore((state) => state.addToast);
  const existingDocuments = documentsQuery.data ?? [];

  function updateRow(id: string, patch: Partial<UploadRow>) {
    setRows((prev) => prev.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  function hashAndFlagDuplicate(rowId: string, file: File) {
    void sha256Hex(file).then((hash) => {
      setRows((prev) => {
        const existingHashes = new Set(existingDocuments.map((doc) => doc.contentHash));
        const isDuplicate =
          existingHashes.has(hash) ||
          prev.some((row) => row.id !== rowId && row.contentHash === hash);
        return prev.map((row) =>
          row.id === rowId ? { ...row, contentHash: hash, isDuplicate } : row,
        );
      });
    });
  }

  function handleFilesSelected(files: File[]) {
    const newRows: UploadRow[] = files.map((file) => ({
      id: crypto.randomUUID(),
      file,
      documentType: detectDocumentType(file.name),
      detectionSource: 'heuristic',
      contentHash: null,
      isDuplicate: false,
      duplicateAcknowledged: false,
      unrecognizedExtension: hasUnrecognizedExtension(file.name),
      validationError:
        file.size === 0
          ? 'This file is empty.'
          : file.size > MAX_UPLOAD_BYTES
            ? `File exceeds the ${String(MAX_UPLOAD_MB)}MB upload limit.`
            : null,
      status: 'staged',
      uploadProgress: 0,
      uploadError: null,
      documentId: null,
    }));
    setRows((prev) => [...prev, ...newRows]);
    for (const row of newRows) {
      hashAndFlagDuplicate(row.id, row.file);
    }
  }

  async function uploadOneRow(row: UploadRow): Promise<boolean> {
    updateRow(row.id, { status: 'uploading', uploadProgress: 0, uploadError: null });
    try {
      const document = await uploadDocument.mutateAsync({
        file: row.file,
        documentType: row.documentType,
        ...(partyId !== undefined ? { partyId } : {}),
        onUploadProgress: (event) => {
          const percent =
            event.total !== undefined && event.total > 0
              ? Math.round((event.loaded / event.total) * 100)
              : 0;
          updateRow(row.id, { uploadProgress: percent });
        },
      });
      updateRow(row.id, { status: 'uploaded', uploadProgress: 100, documentId: document.id });
      return true;
    } catch (error) {
      updateRow(row.id, {
        status: 'error',
        uploadError: extractErrorMessage(error, 'Upload failed — please try again.'),
      });
      return false;
    }
  }

  async function handleUploadAll() {
    const uploadable = rows.filter(
      (row) =>
        row.status === 'staged' &&
        row.validationError === null &&
        (!row.isDuplicate || row.duplicateAcknowledged),
    );
    const results = await runWithConcurrencyLimit(uploadable, MAX_CONCURRENT_UPLOADS, uploadOneRow);
    const succeededCount = results.filter(Boolean).length;
    const failedCount = results.length - succeededCount;

    if (failedCount === 0) {
      addToast({
        title: `${String(succeededCount)} document${succeededCount === 1 ? '' : 's'} uploaded`,
        variant: 'success',
      });
    } else {
      addToast({
        title: `${String(succeededCount)} of ${String(results.length)} documents uploaded`,
        description: `${String(failedCount)} failed — see the row${failedCount === 1 ? '' : 's'} below for details.`,
        variant: 'error',
      });
    }
  }

  const staged = rows.filter((row) => row.status === 'staged');
  const uploading = rows.filter((row) => row.status === 'uploading');
  const errored = rows.filter((row) => row.status === 'error');
  const duplicatesUnacknowledged = rows.filter(
    (row) => row.isDuplicate && !row.duplicateAcknowledged,
  );
  const readyToUploadCount = staged.filter(
    (row) => row.validationError === null && (!row.isDuplicate || row.duplicateAcknowledged),
  ).length;

  const groups = new Map<DocumentType, UploadRow[]>();
  for (const row of rows) {
    const existing = groups.get(row.documentType);
    if (existing) existing.push(row);
    else groups.set(row.documentType, [row]);
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => {
          onExpandedChange(true);
        }}
        className={cn(
          'text-label border-border-default text-text-secondary hover:bg-surface-secondary flex items-center gap-1.5 self-start rounded-interactive border px-3 py-1.5 font-medium',
          'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
        )}
      >
        <Upload className="size-3.5" aria-hidden="true" />
        Add more documents
      </button>
    );
  }

  return (
    <section
      aria-label="Upload documents"
      className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-4 p-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-heading-section text-text-primary">Upload documents</h3>
        {rows.length > 0 && (
          <button
            type="button"
            onClick={() => {
              onExpandedChange(false);
            }}
            className="text-caption text-text-tertiary hover:text-text-primary outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
          >
            Collapse
          </button>
        )}
      </div>

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2">
          <span className="text-label text-text-secondary">Applies to</span>
          <Select
            value={partyId ?? ''}
            onChange={(event) => {
              setPartyId(event.target.value.length > 0 ? event.target.value : undefined);
            }}
            className="w-56"
          >
            <option value="">Unassigned</option>
            {(partiesQuery.data ?? []).map((party) => (
              <option key={party.id} value={party.id}>
                {PARTY_TYPE_LABEL[party.partyType]} — {party.displayName}
              </option>
            ))}
          </Select>
        </label>
      </div>

      <Dropzone onFilesSelected={handleFilesSelected} disabled={uploading.length > 0} />

      {rows.length > 0 && (
        <>
          <div className="text-caption text-text-secondary flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>
              {rows.length} file{rows.length === 1 ? '' : 's'}
            </span>
            {staged.length > 0 && <span>· {staged.length} staged</span>}
            {uploading.length > 0 && <span>· {uploading.length} uploading</span>}
            {duplicatesUnacknowledged.length > 0 && (
              <span className="text-feedback-warning-fg">
                · {duplicatesUnacknowledged.length} duplicate
                {duplicatesUnacknowledged.length === 1 ? '' : 's'} flagged
              </span>
            )}
            {errored.length > 0 && (
              <span className="text-feedback-error-fg">
                · {errored.length} error{errored.length === 1 ? '' : 's'}
              </span>
            )}
          </div>

          <div className="bg-surface-sunken max-h-[28rem] overflow-y-auto rounded-container">
            {Array.from(groups.entries()).map(([type, groupRows]) => {
              const isCollapsed = collapsedGroups.has(type);
              return (
                <div key={type} className="border-border-subtle border-b last:border-b-0">
                  <button
                    type="button"
                    onClick={() => {
                      setCollapsedGroups((prev) => {
                        const next = new Set(prev);
                        if (next.has(type)) next.delete(type);
                        else next.add(type);
                        return next;
                      });
                    }}
                    className={cn(COLLAPSIBLE_GROUP_HEADER_CLASS, 'py-1.5')}
                  >
                    {isCollapsed ? (
                      <ChevronRight className="size-3.5" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="size-3.5" aria-hidden="true" />
                    )}
                    {DOCUMENT_TYPE_LABEL[type]}
                    <span className="text-text-tertiary">({groupRows.length})</span>
                  </button>
                  {!isCollapsed && (
                    <div>
                      {groupRows.map((row) => (
                        <UploadFileRow
                          key={row.id}
                          row={row}
                          polledDocument={existingDocuments.find(
                            (doc) => doc.id === row.documentId,
                          )}
                          onDocumentTypeChange={(type_) => {
                            updateRow(row.id, { documentType: type_, detectionSource: 'manual' });
                          }}
                          onAcknowledgeDuplicate={() => {
                            updateRow(row.id, { duplicateAcknowledged: true });
                          }}
                          onRemove={() => {
                            setRows((prev) => prev.filter((r) => r.id !== row.id));
                          }}
                          onRetry={() => {
                            void uploadOneRow(row);
                          }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <Button
            variant="primary"
            disabled={readyToUploadCount === 0}
            loading={uploading.length > 0}
            onClick={() => {
              void handleUploadAll();
            }}
          >
            Upload {readyToUploadCount} file{readyToUploadCount === 1 ? '' : 's'}
          </Button>
        </>
      )}
    </section>
  );
}
