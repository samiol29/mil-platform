/**
 * Policy Engine entities (spec 005-enterprise-platform §3/§4).
 *
 * `evaluatedRuleKeys`/`passedRuleKeys` are additive/nullable on the backend
 * (`PolicyResult.evaluated_rule_keys`) — `null` means this evaluation ran
 * before that column existed and genuinely has no recorded rule catalogue,
 * never an empty array standing in for "none passed."
 */

import { z } from 'zod';

export const policyResultSchema = z.object({
  id: z.uuid(),
  findingId: z.uuid(),
  applicationId: z.uuid(),
  policyPackId: z.uuid(),
  policyVersion: z.string(),
  outcome: z.string(),
  triggeredRuleKeys: z.array(z.string()),
  evaluatedRuleKeys: z.array(z.string()).nullable(),
  passedRuleKeys: z.array(z.string()).nullable(),
  evaluatedAt: z.iso.datetime(),
  createdAt: z.iso.datetime(),
});

export type PolicyResult = z.infer<typeof policyResultSchema>;

export const policyRuleSchema = z.object({
  id: z.uuid(),
  policyPackId: z.uuid(),
  ruleKey: z.string(),
  name: z.string(),
  description: z.string(),
  severity: z.string(),
  createdAt: z.iso.datetime(),
});

export type PolicyRule = z.infer<typeof policyRuleSchema>;

export const policyPackSchema = z.object({
  id: z.uuid(),
  tenantId: z.uuid(),
  version: z.string(),
  name: z.string(),
  jurisdiction: z.string().nullable(),
  isActive: z.boolean(),
  activatedAt: z.iso.datetime().nullable(),
  deactivatedAt: z.iso.datetime().nullable(),
  createdAt: z.iso.datetime(),
});

export type PolicyPack = z.infer<typeof policyPackSchema>;

export const policyPackApprovalSchema = z.object({
  id: z.uuid(),
  policyPackId: z.uuid(),
  requestedByUserId: z.uuid(),
  decidedByUserId: z.uuid().nullable(),
  decision: z.enum(['PENDING', 'APPROVED', 'REJECTED']),
  reason: z.string().nullable(),
  decidedAt: z.iso.datetime().nullable(),
  createdAt: z.iso.datetime(),
});

export type PolicyPackApproval = z.infer<typeof policyPackApprovalSchema>;
