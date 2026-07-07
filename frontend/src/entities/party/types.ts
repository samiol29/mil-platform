/**
 * Party entity (Product Experience phase, Phase 2) — matches
 * `specs/001-mil-platform-spec/contracts/applications.yaml`'s `Party` schema
 * and `src/mil/application/models.py::Party`. A Party is a person or legal
 * entity registered against an application (borrower/co-borrower/guarantor/
 * corporate entity) — non-PII `displayName` only, per the backend's own
 * "full personal details live in the LOS" invariant.
 */

import { z } from 'zod';

export const PARTY_TYPES = ['APPLICANT', 'CO_APPLICANT', 'GUARANTOR', 'CORPORATE_ENTITY'] as const;

export const partySchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid(),
  partyType: z.enum(PARTY_TYPES),
  displayName: z.string(),
  createdAt: z.iso.datetime(),
});

export type Party = z.infer<typeof partySchema>;
export type PartyType = Party['partyType'];

/** Shared display label for a party type — used by the intake wizard's Borrowers step and the Workspace Overview alike. */
export const PARTY_TYPE_LABEL: Record<PartyType, string> = {
  APPLICANT: 'Applicant',
  CO_APPLICANT: 'Co-Applicant',
  GUARANTOR: 'Guarantor',
  CORPORATE_ENTITY: 'Corporate Entity',
};
