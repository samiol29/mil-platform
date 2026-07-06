export type WorkspaceRegion = 'overview' | 'findings' | 'evidence' | 'documents';

export const WORKSPACE_REGIONS: readonly WorkspaceRegion[] = [
  'overview',
  'findings',
  'evidence',
  'documents',
];

export const REGION_LABEL: Record<WorkspaceRegion, string> = {
  overview: 'Overview',
  findings: 'Findings',
  evidence: 'Evidence',
  documents: 'Documents',
};
