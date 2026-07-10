/**
 * Local (pre-persistence) staged-upload state (Product Experience phase,
 * Phase 3). Deliberately never stored in `uiStore` (its docstring forbids
 * it from ever holding server-derived data) and never in TanStack Query
 * (there is nothing to fetch yet — it's a draft, exactly like the intake
 * wizard's form state) — plain local component state in `UploadSection`.
 */

import type { DetectionSource, DocumentType } from './documentTypeDetection';

export type UploadRowStatus = 'staged' | 'uploading' | 'uploaded' | 'error';

export interface UploadRow {
  readonly id: string;
  readonly file: File;
  readonly documentType: DocumentType;
  readonly detectionSource: DetectionSource;
  /** Filled in asynchronously once the file has been hashed (`fileHash.ts`); duplicate checks wait for this. */
  readonly contentHash: string | null;
  readonly isDuplicate: boolean;
  readonly duplicateAcknowledged: boolean;
  readonly unrecognizedExtension: boolean;
  /** Blocking — set for a genuinely-invalid file (empty, over the size limit). Upload is disabled while set. */
  readonly validationError: string | null;
  readonly status: UploadRowStatus;
  readonly uploadProgress: number;
  /** The real backend error message (`extractErrorMessage`), never a generic string. */
  readonly uploadError: string | null;
  /** Set once the server confirms the upload — the id used to find this file's live row in `useDocumentsForApplication`. */
  readonly documentId: string | null;
}
