/**
 * Document type detection (Product Experience phase, Phase 3) — a
 * client-side filename-keyword heuristic only. `document_type` is a free
 * string on the backend (no closed enum — `specs/001-mil-platform-spec/
 * contracts/documents.yaml`), so `DOCUMENT_TYPES` below is a curated list
 * for the UI's `Select`, not a server-enforced constraint; `OTHER` plus the
 * always-editable `Select` cover anything the heuristic misses.
 *
 * `DetectionSource` exists specifically so a future real backend classifier
 * has an obvious, additive place to plug in (`'backend'`) without changing
 * this shape — not because one exists today.
 */

export const DOCUMENT_TYPES = [
  'BANK_STATEMENT',
  'PAYSLIP',
  'W2',
  'TAX_RETURN',
  'IDENTITY_DOCUMENT',
  'VALUATION_REPORT',
  'CREDIT_REPORT',
  'INSURANCE_DOCUMENT',
  'OTHER',
] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number];

export const DOCUMENT_TYPE_LABEL: Record<DocumentType, string> = {
  BANK_STATEMENT: 'Bank Statement',
  PAYSLIP: 'Pay Stub',
  W2: 'W-2',
  TAX_RETURN: 'Tax Return',
  IDENTITY_DOCUMENT: 'Identity Document',
  VALUATION_REPORT: 'Valuation Report',
  CREDIT_REPORT: 'Credit Report',
  INSURANCE_DOCUMENT: 'Insurance Document',
  OTHER: 'Other',
};

export type DetectionSource = 'heuristic' | 'manual' | 'backend';

const KEYWORD_RULES: readonly { readonly pattern: RegExp; readonly type: DocumentType }[] = [
  { pattern: /pay ?stub|payslip/i, type: 'PAYSLIP' },
  { pattern: /w-?2/i, type: 'W2' },
  { pattern: /tax/i, type: 'TAX_RETURN' },
  { pattern: /bank/i, type: 'BANK_STATEMENT' },
  { pattern: /passport|license|licence|\bid\b/i, type: 'IDENTITY_DOCUMENT' },
  { pattern: /appraisal|valuation/i, type: 'VALUATION_REPORT' },
  { pattern: /credit/i, type: 'CREDIT_REPORT' },
  { pattern: /insurance/i, type: 'INSURANCE_DOCUMENT' },
];

/** Filename-keyword guess only — always overridable, never authoritative. */
export function detectDocumentType(filename: string): DocumentType {
  const match = KEYWORD_RULES.find((rule) => rule.pattern.test(filename));
  return match?.type ?? 'OTHER';
}

const SUPPORTED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'tif', 'tiff', 'zip'];

/** Soft signal only — the backend does not reject by extension at upload time (see plan). */
export function hasUnrecognizedExtension(filename: string): boolean {
  const extension = filename.split('.').pop()?.toLowerCase();
  return extension === undefined || !SUPPORTED_EXTENSIONS.includes(extension);
}
