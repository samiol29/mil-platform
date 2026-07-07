export type WorkspaceRegion =
  | 'overview'
  | 'findings'
  | 'evidence'
  | 'documents'
  | 'policy'
  | 'timeline';

/**
 * Tab order matches the product's own investigation chain (Product
 * Experience phase, Phase 10 — confirmed by audit that every consumer
 * validates `region` by string value, never array position, so this order
 * is purely presentational and safe to change): Document → Evidence →
 * Finding → Policy, with Timeline last as the case-history view over all
 * of it.
 */
export const WORKSPACE_REGIONS: readonly WorkspaceRegion[] = [
  'overview',
  'documents',
  'evidence',
  'findings',
  'policy',
  'timeline',
];

export const REGION_LABEL: Record<WorkspaceRegion, string> = {
  overview: 'Overview',
  findings: 'Findings',
  evidence: 'Evidence',
  documents: 'Documents',
  policy: 'Policy',
  timeline: 'Timeline',
};
