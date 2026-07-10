/**
 * AuditTrailEntry entity (spec 002 tasks.md T060; data-model.md).
 *
 * `AuditTrailEntry` is data-model.md's own deliberately-chosen,
 * product-facing name for what the backend implements as `AuditEvent`
 * (`src/mil/audit/models.py`) — the one documented naming exception in
 * data-model.md's Naming Rule.
 *
 * Matches `src/mil/api/v1/schemas.py::AuditEventResponse` — field names
 * mirror the real backend response (`occurredAt`, `eventData`), not
 * data-model.md's pre-implementation sketch (`timestamp`, `payload`),
 * consistent with how `entities/evidence` and `entities/application`
 * resolved the same kind of naming gap (Principle VII: match the real
 * backend name, not a guess made before the endpoint existed).
 *
 * `actor` (a resolved human-readable name, per data-model.md's field list)
 * is not available: the backend records only `actorId` (a UUID) and
 * `actorType` (`"SYSTEM"` / `"USER"`) — resolving `actorId` to a display
 * name requires joining to `core.users`, which no endpoint does yet.
 *
 * No mutation affordance exists on this type, at the type level — this
 * schema has no corresponding write hook anywhere in the entity layer, per
 * data-model.md's explicit requirement ("the frontend must not expose any
 * mutation affordance for this type at all").
 */

import { z } from 'zod';

export const auditTrailEntrySchema = z.object({
  id: z.uuid(),
  applicationId: z.uuid().nullable(),
  eventType: z.string(),
  entityType: z.string(),
  entityId: z.uuid(),
  actorId: z.uuid().nullable(),
  actorType: z.enum(['SYSTEM', 'USER']),
  eventData: z.record(z.string(), z.unknown()),
  occurredAt: z.iso.datetime(),
  sequenceNumber: z.number().int().nullable(),
});

export type AuditTrailEntry = z.infer<typeof auditTrailEntrySchema>;
