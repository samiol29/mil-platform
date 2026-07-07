/**
 * Persistent duplicate detection (Product Experience phase, Phase 4.5) —
 * distinct from Phase 3's pre-upload duplicate check (`UploadSection.tsx`,
 * which compares *staged* files against already-uploaded ones before
 * upload). This is the after-the-fact view: grouping already-persisted
 * documents by their real `contentHash` (SHA-256, computed and stored by
 * the backend at upload time) to surface possible duplicates that made it
 * into the package.
 */

import type { Document } from '@entities/document/queries';

/** Maps `contentHash` to every document sharing it — only hashes with more than one document are real duplicates. */
export function findDuplicateGroups(documents: readonly Document[]): ReadonlyMap<string, readonly Document[]> {
  const byHash = new Map<string, Document[]>();
  for (const doc of documents) {
    const existing = byHash.get(doc.contentHash);
    if (existing) existing.push(doc);
    else byHash.set(doc.contentHash, [doc]);
  }

  const duplicateGroups = new Map<string, readonly Document[]>();
  for (const [hash, docs] of byHash) {
    if (docs.length > 1) duplicateGroups.set(hash, docs);
  }
  return duplicateGroups;
}

/** Convenience: the set of document ids that belong to any duplicate group. */
export function duplicateDocumentIds(documents: readonly Document[]): ReadonlySet<string> {
  const groups = findDuplicateGroups(documents);
  const ids = new Set<string>();
  for (const docs of groups.values()) {
    for (const doc of docs) ids.add(doc.id);
  }
  return ids;
}
