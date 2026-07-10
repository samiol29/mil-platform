/**
 * Findings grouped by policy version (Product Experience phase, Phase 7 —
 * "which lending or compliance rules were evaluated?"). `Finding.
 * policyVersion` is the only real "which policy evaluation" signal that
 * reaches the frontend — a bare, independently-set-per-finding string (or
 * `null` when not yet evaluated). This reuses the exact same
 * `policyVersion !== null` signal `deriveApplicationStages`
 * (`applicationPipelineSummary.ts`) already uses for the Overview
 * pipeline's "Policy" stage — one source of truth, two presentations.
 *
 * There is no rule-level pass/fail data anywhere in the backend: a policy
 * check that's satisfied produces no `Finding` at all, so "awaiting
 * judgment" vs. "resolved" (derived from the real `Finding.state`) is the
 * most granular real breakdown this can honestly offer — not a per-rule
 * pass/fail trace.
 */

import type { Finding } from '@entities/finding/queries';

export interface PolicyVersionGroup {
  /** `null` renders as "Not yet evaluated" — a finding with no policy attribution yet. */
  readonly policyVersion: string | null;
  readonly findings: readonly Finding[];
  readonly awaitingJudgmentCount: number;
  readonly resolvedCount: number;
}

function isAwaitingJudgment(finding: Finding): boolean {
  return finding.state === 'unreviewed' || finding.state === 'escalated';
}

export function groupFindingsByPolicyVersion(
  findings: readonly Finding[],
): readonly PolicyVersionGroup[] {
  const byVersion = new Map<string | null, Finding[]>();
  for (const finding of findings) {
    const existing = byVersion.get(finding.policyVersion);
    if (existing) existing.push(finding);
    else byVersion.set(finding.policyVersion, [finding]);
  }

  const groups: PolicyVersionGroup[] = [];
  for (const [policyVersion, groupFindings] of byVersion) {
    groups.push({
      policyVersion,
      findings: groupFindings,
      awaitingJudgmentCount: groupFindings.filter(isAwaitingJudgment).length,
      resolvedCount: groupFindings.filter((f) => !isAwaitingJudgment(f)).length,
    });
  }

  // Real policy versions first (alphabetical, deterministic), the "not yet
  // evaluated" (`null`) bucket always last — it's a pending state, not a
  // version to compare against others.
  return groups.sort((a, b) => {
    if (a.policyVersion === null) return 1;
    if (b.policyVersion === null) return -1;
    return a.policyVersion.localeCompare(b.policyVersion);
  });
}
