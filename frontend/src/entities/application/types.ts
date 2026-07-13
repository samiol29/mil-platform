/**
 * Application entity (spec 002 tasks.md T052; data-model.md).
 *
 * This Zod schema matches the ACTUAL current `GET /v1/applications/{id}`
 * response shape (`src/mil/api/v1/schemas.py::ApplicationResponse`) — not
 * every field `data-model.md` eventually anticipates for the Application
 * Queue row (`documentCount`, `evidenceCount`, `flaggedFindingCount`,
 * `lastActivityAt`, `slaState`). Those are queue-row aggregate fields the
 * backend does not compute yet; they arrive with the search/queue endpoint
 * enhancement (tasks.md T073, User Story 2), not this single-application
 * read used by the Application Workspace (User Story 1). Adding them here
 * now would parse fields the API never sends, defeating the entity layer's
 * "a contract change fails loudly" guarantee (plan.md).
 *
 * `borrowerName` is deliberately NOT a field on this type: the backend has
 * no such column on `MortgageApplication` — a borrower's display name is a
 * `Party` (see `entities/party` if/when one is introduced), sourced from
 * `GET /v1/applications/{id}/parties`. The Application Workspace composes
 * both, per plan.md's Design System/Entity layering rule.
 */

import { z } from 'zod';

export const applicationSchema = z.object({
  id: z.uuid(),
  losReference: z.string().nullable(),
  loanNumber: z.string().nullable(),
  status: z.enum(['DRAFT', 'SUBMITTED', 'IN_REVIEW', 'REVIEW_COMPLETE', 'WITHDRAWN']),
  activePolicyPackId: z.uuid().nullable(),
  partyCount: z.number().int().nonnegative(),
  createdAt: z.iso.datetime(),
  updatedAt: z.iso.datetime().nullable(),
});

export type Application = z.infer<typeof applicationSchema>;
export type ApplicationStatus = Application['status'];

/**
 * Real status of an application's FINDING_GENERATION evaluation run
 * (`GET /v1/applications/{id}/evaluation` — final product polish sprint).
 * `NOT_TRIGGERED` means evaluation was never started (most commonly: the
 * application has never been submitted) — never inferred from document
 * processing status, which is a separate pipeline. `retryable` is only
 * `true` when `status === 'FAILED'`.
 */
export const evaluationStatusSchema = z.object({
  status: z.enum(['NOT_TRIGGERED', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED']),
  errorMessage: z.string().nullable(),
  retryable: z.boolean(),
  startedAt: z.iso.datetime().nullable(),
  completedAt: z.iso.datetime().nullable(),
});

export type EvaluationStatus = z.infer<typeof evaluationStatusSchema>;
