/**
 * Groups poison jobs by (step, error code) (final polish sprint). A single
 * upstream outage (e.g. Gemini's free-tier rate limit) can poison dozens of
 * jobs at once, each carrying the identical provider error message — the
 * Operational Dashboard was repeating that same full paragraph verbatim in
 * one card per job, which reads as noise rather than signal for an
 * operator trying to understand "what's actually wrong." Grouping loses no
 * information: every individual job (and its own retry countdown) is still
 * listed, just under one collapsed summary instead of N duplicated ones.
 */

import type { PoisonJob } from '@entities/operational/types';

export interface PoisonJobGroup {
  readonly key: string;
  readonly stepName: string;
  readonly errorCode: string | null;
  readonly errorMessage: string | null;
  readonly jobs: readonly PoisonJob[];
}

export function groupPoisonJobs(jobs: readonly PoisonJob[]): readonly PoisonJobGroup[] {
  const groups = new Map<string, PoisonJob[]>();
  for (const job of jobs) {
    const key = `${job.stepName}::${job.errorCode ?? ''}`;
    const existing = groups.get(key);
    if (existing) existing.push(job);
    else groups.set(key, [job]);
  }
  return Array.from(groups.entries()).map(([key, groupJobs]) => ({
    key,
    stepName: groupJobs[0].stepName,
    errorCode: groupJobs[0].errorCode,
    errorMessage: groupJobs[0].errorMessage,
    jobs: groupJobs,
  }));
}
