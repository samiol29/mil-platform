/**
 * Real-backend-reason extraction (Product Experience phase, Phase 3 —
 * "preserve trust… never replace real errors with generic 'Upload failed'").
 *
 * The API has two error response shapes in practice:
 * - Every `MILError` subclass (`mil/api/errors.py`) → `{ code, message,
 *   details }`, `message` already camelCased by the response interceptor.
 * - A handful of raw Starlette `HTTPException`s that bypass that handler
 *   (e.g. the upload size limit, `_read_upload_within_limit` in
 *   `mil/api/v1/documents.py`) → `{ detail: { code, message } }` or, for
 *   FastAPI's own built-ins, `{ detail: string }`.
 *
 * This tries each real shape in turn and only falls back to a generic
 * message if the response genuinely carries none (e.g. a network failure
 * with no response at all).
 */

import { isAxiosError } from 'axios';

export function extractErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) return fallback;

  const data: unknown = error.response?.data;
  if (data === null || typeof data !== 'object') return fallback;

  const record = data as Record<string, unknown>;

  if (typeof record.message === 'string' && record.message.length > 0) {
    return record.message;
  }

  const detail = record.detail;
  if (typeof detail === 'string' && detail.length > 0) {
    return detail;
  }
  if (detail !== null && typeof detail === 'object') {
    const detailMessage = (detail as Record<string, unknown>).message;
    if (typeof detailMessage === 'string' && detailMessage.length > 0) {
      return detailMessage;
    }
  }

  return fallback;
}

/**
 * True when the failure is a real 409 Conflict — the backend's own signal
 * that the record moved under the caller (e.g. someone else already
 * resolved this finding, or a retry target is no longer in a retryable
 * state), as distinct from a validation error, a permissions error, or a
 * network failure (final product polish sprint, D6). Before this, every
 * mutation's `onError` routed a 409 through the exact same generic-failure
 * toast as any other error — a real, undifferentiated case that specifically
 * benefits from a "someone else already acted on this — refresh and check"
 * framing rather than "try again," which implies retrying would help.
 */
export function isConflictError(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 409;
}
