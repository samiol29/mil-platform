import { describe, expect, it } from 'vitest';

import { groupPoisonJobs } from './groupPoisonJobs';
import type { PoisonJob } from '@entities/operational/types';

function makeJob(overrides: Partial<PoisonJob> = {}): PoisonJob {
  return {
    id: 'job-1',
    workflowRunId: 'run-1',
    stepName: 'OCR',
    status: 'FAILED',
    retryCount: 3,
    maxRetries: 3,
    errorCode: 'PROVIDER_UNAVAILABLE',
    errorMessage: 'Gemini API returned HTTP 429',
    updatedAt: '2026-07-13T00:00:00Z',
    ...overrides,
  };
}

describe('groupPoisonJobs', () => {
  it('groups jobs sharing the same step and error code together', () => {
    const groups = groupPoisonJobs([
      makeJob({ id: 'a' }),
      makeJob({ id: 'b' }),
      makeJob({ id: 'c', stepName: 'EXTRACTION' }),
    ]);
    expect(groups).toHaveLength(2);
    expect(groups.find((g) => g.stepName === 'OCR')?.jobs).toHaveLength(2);
    expect(groups.find((g) => g.stepName === 'EXTRACTION')?.jobs).toHaveLength(1);
  });

  it('keeps distinct error codes for the same step in separate groups', () => {
    const groups = groupPoisonJobs([
      makeJob({ id: 'a', errorCode: 'PROVIDER_UNAVAILABLE' }),
      makeJob({ id: 'b', errorCode: 'TIMEOUT' }),
    ]);
    expect(groups).toHaveLength(2);
  });

  it('returns an empty array for no jobs', () => {
    expect(groupPoisonJobs([])).toEqual([]);
  });
});
