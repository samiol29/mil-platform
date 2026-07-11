/**
 * Customer Portal checklist + status (spec 005-enterprise-platform §12,
 * Wave 4). A borrower's entire portal surface: plain-language status, and
 * a checklist of requested documents with an upload action per item.
 *
 * Never renders AI reasoning, Findings, Evidence, Policy results, internal
 * comments, or Timeline/Audit detail — the backend API this calls
 * (`/v1/portal/*`) structurally cannot return any of that (a minimal,
 * purpose-built read surface, not the internal API filtered client-side).
 */

import { useRef, useState } from 'react';

import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Skeleton } from '@design-system/components/LoadingState';
import type { ChecklistItem } from '@entities/portal/types';
import { usePortalChecklist, usePortalStatus, useUploadForChecklistItem } from '@entities/portal/queries';

const ITEM_STATUS_COPY: Record<ChecklistItem['status'], string> = {
  REQUESTED: 'Please upload this when ready',
  RECEIVED: "We've received this",
  WAIVED: 'No longer needed',
};

export function PortalChecklistPage() {
  const statusQuery = usePortalStatus();
  const checklistQuery = usePortalChecklist();

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-1 text-center">
        <h1 className="text-display">Your Application</h1>
        {statusQuery.isPending ? (
          <Skeleton className="mx-auto h-6 w-48" />
        ) : statusQuery.isError ? (
          <p className="text-body text-text-tertiary">Status unavailable right now.</p>
        ) : (
          <p className="text-heading text-interactive-primary-default">
            {statusQuery.data.statusLabel}
          </p>
        )}
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-heading">What we need from you</h2>
        {checklistQuery.isPending ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : checklistQuery.isError ? (
          <ErrorState
            title="We couldn't load your checklist"
            description="Please try again in a moment."
            onRetry={() => void checklistQuery.refetch()}
          />
        ) : checklistQuery.data.length === 0 ? (
          <EmptyState
            title="Nothing needed right now"
            description="We'll let you know here if we need anything else from you."
          />
        ) : (
          <ul className="flex flex-col gap-3" aria-label="Document checklist">
            {checklistQuery.data.map((item) => (
              <ChecklistItemCard key={item.id} item={item} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ChecklistItemCard({ item }: { item: ChecklistItem }) {
  const uploadMutation = useUploadForChecklistItem();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  return (
    <li className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-2 p-4">
      <div className="flex items-center justify-between">
        <span className="text-body font-medium">{item.label}</span>
        <span className="text-caption text-text-tertiary">{ITEM_STATUS_COPY[item.status]}</span>
      </div>
      {item.status === 'REQUESTED' && (
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            aria-label={`Upload file for ${item.label}`}
            onChange={(e) => {
              setSelectedFile(e.target.files?.[0] ?? null);
            }}
          />
          <Button
            variant="secondary"
            disabled={selectedFile === null}
            loading={uploadMutation.isPending}
            onClick={() => {
              if (selectedFile === null) return;
              uploadMutation.mutate({
                itemId: item.id,
                file: selectedFile,
                documentType: item.documentType,
              });
            }}
          >
            Upload
          </Button>
        </div>
      )}
      {uploadMutation.isError && (
        <p className="text-caption text-feedback-error-fg">
          Upload failed — please try again.
        </p>
      )}
    </li>
  );
}
