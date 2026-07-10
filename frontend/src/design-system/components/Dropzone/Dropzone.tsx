/**
 * Dropzone (Product Experience phase, Phase 3) — the entry point for a
 * borrower's entire document package, not a single-file picker. Leads with
 * folder intake (drag-and-drop of a folder is walked recursively via
 * `folderWalk.ts`; a "Choose folder" button uses the native
 * `webkitdirectory` picker) while still supporting plain multi-file and
 * single-file selection — Principle 1 of the upload workflow ("borrower
 * package first").
 *
 * The outer drag region is a plain (non-interactive-role) container, not a
 * `role="button"` — the two real `<button>`s inside it ("Choose files"/
 * "Choose folder") are the accessible, keyboard-operable equivalents of
 * drag-and-drop (which has no meaningful keyboard equivalent of its own).
 * Wrapping them in an outer interactive role would nest interactive
 * controls, a WCAG violation caught by this component's own Storybook
 * a11y check.
 */

import { FolderUp, Upload } from 'lucide-react';
import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';

import { cn } from '@design-system/lib/cn';

import { readAllFilesFromDataTransfer } from './folderWalk';

export interface DropzoneProps {
  readonly onFilesSelected: (files: File[]) => void;
  readonly disabled?: boolean;
  readonly className?: string;
}

export function Dropzone({ onFilesSelected, disabled = false, className }: DropzoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length > 0) onFilesSelected(files);
    event.target.value = '';
  }

  async function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragActive(false);
    if (disabled) return;
    const files = await readAllFilesFromDataTransfer(event.dataTransfer);
    if (files.length > 0) onFilesSelected(files);
  }

  return (
    // Drag-and-drop has no corresponding ARIA role/keyboard equivalent of its
    // own — the "Choose files"/"Choose folder" buttons below are the real
    // accessible, keyboard-operable equivalents of this drop target.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      aria-disabled={disabled}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragActive(true);
      }}
      onDragLeave={() => {
        setIsDragActive(false);
      }}
      onDrop={(event) => {
        void handleDrop(event);
      }}
      className={cn(
        'rounded-container flex flex-col items-center gap-3 border-2 border-dashed p-8 text-center',
        'transition-colors duration-micro ease-standard',
        disabled
          ? 'border-border-subtle bg-surface-disabled cursor-not-allowed'
          : isDragActive
            ? 'border-interactive-primary-default bg-surface-secondary'
            : 'border-border-default',
        className,
      )}
    >
      <FolderUp className="text-text-tertiary size-8" aria-hidden="true" />
      <div>
        <p className="text-body-emphasis text-text-primary">
          Drop the borrower's folder here, or drop individual files
        </p>
        <p className="text-caption text-text-secondary mt-1">
          Native PDFs, scanned PDFs, JPEG, PNG, TIFF, or ZIP bundles
        </p>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={(event) => {
            event.stopPropagation();
            fileInputRef.current?.click();
          }}
          className={cn(
            'text-label border-border-default text-text-secondary hover:bg-surface-secondary rounded-interactive border px-3 py-1.5 font-medium',
            'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50',
          )}
        >
          <Upload className="mr-1.5 inline size-3.5" aria-hidden="true" />
          Choose files
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={(event) => {
            event.stopPropagation();
            folderInputRef.current?.click();
          }}
          className={cn(
            'text-label border-border-default text-text-secondary hover:bg-surface-secondary rounded-interactive border px-3 py-1.5 font-medium',
            'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50',
          )}
        >
          <FolderUp className="mr-1.5 inline size-3.5" aria-hidden="true" />
          Choose folder
        </button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        hidden
        onChange={handleFileInputChange}
        aria-label="Choose files to upload"
      />
      <input
        ref={(node) => {
          folderInputRef.current = node;
          // `webkitdirectory` is a de facto standard (Chromium/WebKit/Firefox)
          // with no corresponding React prop/JSX attribute type — set imperatively.
          node?.setAttribute('webkitdirectory', '');
        }}
        type="file"
        multiple
        hidden
        onChange={handleFileInputChange}
        aria-label="Choose a folder to upload"
      />
    </div>
  );
}
