import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { extractErrorMessage, isConflictError } from './extractErrorMessage';

function makeAxiosError(status: number, data: unknown): AxiosError {
  const error = new AxiosError('Request failed', String(status));
  error.response = {
    status,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data,
  };
  return error;
}

describe('extractErrorMessage', () => {
  it('returns the fallback for a non-axios error', () => {
    expect(extractErrorMessage(new Error('boom'), 'fallback')).toBe('fallback');
  });

  it('returns a MILError-shaped `message` field', () => {
    const error = makeAxiosError(409, { code: 'CONFLICT', message: 'Already resolved' });
    expect(extractErrorMessage(error, 'fallback')).toBe('Already resolved');
  });

  it('returns a raw HTTPException `detail` string', () => {
    const error = makeAxiosError(413, { detail: 'Payload too large' });
    expect(extractErrorMessage(error, 'fallback')).toBe('Payload too large');
  });

  it('returns a nested `detail.message`', () => {
    const error = makeAxiosError(413, { detail: { code: 'PAYLOAD_TOO_LARGE', message: 'Too big' } });
    expect(extractErrorMessage(error, 'fallback')).toBe('Too big');
  });

  it('falls back when the response body carries none of the known shapes', () => {
    const error = makeAxiosError(500, {});
    expect(extractErrorMessage(error, 'fallback')).toBe('fallback');
  });
});

describe('isConflictError (final product polish sprint, D6)', () => {
  it('is true for a real 409 response', () => {
    expect(isConflictError(makeAxiosError(409, { code: 'CONFLICT', message: 'x' }))).toBe(true);
  });

  it('is false for a 500', () => {
    expect(isConflictError(makeAxiosError(500, { code: 'SERVER_ERROR', message: 'x' }))).toBe(
      false,
    );
  });

  it('is false for a 422 validation error', () => {
    expect(isConflictError(makeAxiosError(422, { code: 'VALIDATION_ERROR', message: 'x' }))).toBe(
      false,
    );
  });

  it('is false for a non-axios error', () => {
    expect(isConflictError(new Error('network down'))).toBe(false);
  });
});
