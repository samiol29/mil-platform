/**
 * Document download (Product Experience phase, Phase 4.5 — "every
 * uploaded document should become accessible… download the original
 * file"). A plain async helper, not a query/mutation: downloading is a
 * one-off side effect with no cached state to hold, unlike the rest of
 * this module.
 *
 * Fetches the exact same content endpoint `PdfRenderer.tsx` already uses
 * (`GET /applications/{id}/documents/{id}/content`, confirmed to serve raw
 * bytes independent of `ingestionStatus`) via the shared `httpClient` so
 * the bearer-token interceptor applies. The endpoint has no
 * `Content-Disposition` header, so the saved filename comes from the
 * `download` attribute on a synthesized anchor using the real `filename`
 * already returned on `Document` — no backend change needed for this.
 */

import { httpClient } from '@app/auth/httpClient';

export async function downloadDocument(
  applicationId: string,
  documentId: string,
  filename: string,
): Promise<void> {
  const response = await httpClient.get<Blob>(
    `/applications/${applicationId}/documents/${documentId}/content`,
    { responseType: 'blob' },
  );

  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
