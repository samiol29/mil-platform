/**
 * Borrower Identity Resolution entities (spec 005-enterprise-platform §5,
 * Wave 3). Matches `src/mil/api/v1/schemas.py`'s `IdentityMatchCandidateResponse`/
 * `BorrowerIdentityResponse`/`BorrowerIdentityMemberResponse` exactly.
 */

import { z } from 'zod';

export const identityMatchCandidateSchema = z.object({
  id: z.uuid(),
  tenantId: z.uuid(),
  partyId: z.uuid(),
  candidatePartyId: z.uuid(),
  matchScore: z.number(),
  matchBasis: z.record(z.string(), z.unknown()),
  status: z.enum(['PENDING', 'CONFIRMED', 'REJECTED']),
  reviewedByUserId: z.uuid().nullable(),
  reason: z.string().nullable(),
  reviewedAt: z.iso.datetime().nullable(),
  createdAt: z.iso.datetime(),
});

export type IdentityMatchCandidate = z.infer<typeof identityMatchCandidateSchema>;

export const borrowerIdentitySchema = z.object({
  id: z.uuid(),
  tenantId: z.uuid(),
  primaryDisplayName: z.string(),
  createdAt: z.iso.datetime(),
});

export type BorrowerIdentity = z.infer<typeof borrowerIdentitySchema>;

export const borrowerIdentityMemberSchema = z.object({
  id: z.uuid(),
  borrowerIdentityId: z.uuid(),
  partyId: z.uuid(),
  applicationId: z.uuid(),
  linkedByUserId: z.uuid(),
  linkedAt: z.iso.datetime(),
  unlinkedAt: z.iso.datetime().nullable(),
  unlinkedByUserId: z.uuid().nullable(),
});

export type BorrowerIdentityMember = z.infer<typeof borrowerIdentityMemberSchema>;

/**
 * Cross-Application Intelligence observation (spec 005 §6, Wave 3). Matches
 * `CrossApplicationObservationResponse` exactly. Never a decision — an
 * observation, always citing its supporting evidence ids.
 */
export const crossApplicationObservationSchema = z.object({
  kind: z.string(),
  description: z.string(),
  applicationIds: z.array(z.uuid()),
  documentIds: z.array(z.uuid()),
  findingIds: z.array(z.uuid()),
});

export type CrossApplicationObservation = z.infer<typeof crossApplicationObservationSchema>;
