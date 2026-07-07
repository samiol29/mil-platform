/**
 * Client-side SHA-256 (Product Experience phase, Phase 3's duplicate
 * detection) — Web Crypto `SubtleCrypto.digest`, no new dependency. Matches
 * the backend's own hash algorithm for `Document.content_hash` (`mil/api/v1/
 * documents.py`: "A SHA-256 integrity hash is computed from the raw
 * bytes"), so a staged file's hash is directly comparable to
 * already-uploaded documents' `contentHash`.
 */

export async function sha256Hex(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}
