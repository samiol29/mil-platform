# Phase 1 Data Model: Frontend Data & State Shapes

This is a conceptual model — field lists, relationships, and state transitions — not code. It mirrors the Key Entities already defined in the Underwriter Workspace specification (002) and the platform's canonical domain entities (Constitution, Domain Entities Reference), adding only the client-side caching/freshness tier each entity requires. No new business entity is introduced here; this document exists to fix vocabulary before implementation and to make each entity's caching behavior an explicit, reviewable decision rather than an ad hoc per-screen choice.

## Naming Rule

Every frontend type name matches its backend/domain name exactly (`Application`, `Document`, `EvidenceItem`, `Finding`, `Verification`, `Notification`) — per Constitution Principle VII (Domain-Driven Design) and 004's finding that naming drift between layers is a recurring source of confusion in the researched enterprise products. No frontend-only synonym (e.g., "Loan," "Case," "Record") is introduced for an entity that already has a platform-canonical name.

**One documented exception**: `AuditTrailEntry` is spec 002's own deliberately-chosen, product-facing Key Entity name (see spec.md's Key Entities section) for what the backend implements as `AuditEvent` (`src/mil/audit/models.py`). This is a 1:1 mapping, not a synonym invented at the frontend layer — the frontend type is named to match spec 002's own vocabulary, which a reviewer reads directly, rather than the backend's internal class name, which they never see. Every other entity in this document matches its backend class name exactly; this is the sole, explicitly-recorded exception, kept to one to avoid the naming drift this rule exists to prevent.

---

## Application (view model)

| Field | Notes |
|---|---|
| `id` | Internal identifier; never rendered as a primary label (002 FR-006) |
| `borrowerName`, `loanNumber`, `losReference` | The three permitted search/display identifiers (002 FR-009) |
| `status` | Lifecycle state; drives which actions are available (002 FR-030) |
| `assignedReviewer` | Nullable |
| `documentCount`, `evidenceCount`, `flaggedFindingCount` | Queue-row summary fields (002 FR-018) |
| `lastActivityAt`, `createdAt` | Drive default newest-first ordering (002 FR-016) |
| `slaState` | Derived: on-track / at-risk / overdue (002 FR-021; Design System Status color family) |

**Caching tier**: Queue-row-level fields are "informational" (tolerant of brief staleness, background-refreshed) per 002's State Management & Data Strategy. The specific Application record open in the Application Workspace is "audit-critical" once any finding on it is being acted upon — its staleness must be checked (FR-036) before a verification/override write is submitted, never silently assumed fresh.

---

## Document (view model)

| Field | Notes |
|---|---|
| `id`, `applicationId`, `filename`, `documentType` | |
| `pageCount` | Populated once ingestion completes |
| `ingestionStatus` | pending / in_progress / completed / failed |
| `ingestionError` | Present only when `ingestionStatus === "failed"` (002 Edge Cases) |
| `evidenceCount` | Evidence items derived from this document |

**Caching tier**: Informational while `ingestionStatus` is not yet `completed` (short `staleTime`, active polling/SSE-driven invalidation so the user sees progress); long-lived/effectively immutable once `completed` or `failed` (002 Caching Strategy: "reference or rarely changing data... may be cached aggressively").

---

## EvidenceItem

| Field | Notes |
|---|---|
| `id`, `applicationId`, `documentId` | |
| `value`, `fieldType` | e.g., income, identity, property, employment (002 FR-046) |
| `page`, `fieldLocation` | Provenance for Document Viewer highlighting (Constitution Principle II) |
| `extractionConfidence` | Mapped to the Design System's fixed confidence-band scale (003 FR-061), never a raw numeric score presented directly |
| `extractionMethod`, `extractionVersion`, `extractedAt` | Full provenance per Constitution Principle II |
| `verificationStatus` | unverified / verified / overridden |
| `conflictsWith` | Zero or more other `EvidenceItem` ids representing the same underlying fact with a different value (002 FR-047) |

**Caching tier**: Audit-critical once a Finding referencing it is being verified/overridden — must be confirmed-fresh at the moment of that action (mirrors Application's tiering rule above).

---

## Finding

| Field | Notes |
|---|---|
| `id`, `applicationId` | |
| `what`, `why`, `recommendedAction` | The three narrative explainability fields (Constitution Principle III) |
| `evidenceRefs` | One or more `EvidenceItem` ids — a Finding with zero resolvable evidence refs must never render (002 FR-031) |
| `confidence` | Same fixed band scale as `EvidenceItem.extractionConfidence` |
| `state` | unreviewed / verified / overridden / escalated (002 FR-053) |
| `modelVersion`, `promptVersion`, `policyVersion` | Constitution Principle XII attribution, always carried, never dropped by a cache transform |

**Caching tier**: Audit-critical — a Finding is never rendered from a cache that cannot supply all five explainability fields; a partial cache hit is treated as a cache miss for this entity specifically.

---

## Verification / Override Record

| Field | Notes |
|---|---|
| `id`, `findingId`, `reviewerId` | |
| `previousValue`, `newValue` | |
| `reason` | Required, non-empty for an override (002 FR-052, FR-076) |
| `createdAt` | |

**State transition rule**: this record is created exactly once, by exactly one confirmed (never optimistic) mutation, and is never subsequently updated or deleted by any client operation — the frontend data layer must not expose an update or delete affordance for this type at all, at the type-system level, not merely by omitting a button (mirrors Constitution Principle VIII's immutability requirement as a compile-time, not just UX, guarantee).

---

## Copilot Session / Message / Citation

| Field | Notes |
|---|---|
| `sessionId`, `applicationId` | A session belongs to exactly one application; the client must never construct a request carrying evidence from a different `applicationId` (Constitution Principle V enforced at the request-construction layer, not just the UI) |
| `messages[]` | `{ question, answer, citations[], modelVersion, promptVersion, createdAt }` |
| `citations[]` | Each resolves to either an `EvidenceItem` id or a `Document` location; an answer with zero citations must carry an explicit `insufficientEvidence: true` flag rather than being indistinguishable from a cited answer with an empty array |

**Caching tier**: Append-only per session; a session's prior messages are immutable once written (never re-fetched/overwritten), matching 002 FR-063 (full history must remain reviewable later).

---

## Saved View / Filter

| Field | Notes |
|---|---|
| `id`, `ownerId`, `name` | |
| `criteria` | Structured filter conditions (field, operator, value)[] |
| `sort` | Column + direction |
| `visibility` | private / shared-with-team |

**Caching tier**: Low-risk/preference — optimistic create/update/delete is explicitly permitted here (002 Assumptions; 004 Design Decision on selective optimistic UI).

---

## Notification

| Field | Notes |
|---|---|
| `id`, `type`, `applicationId` (nullable), `findingId` (nullable) | |
| `readAt` | Nullable |
| `createdAt` | |
| `groupKey` | Used client-side to group repeated notifications of the same type/subject (002 FR-086) |

**Caching tier**: Delivered via SSE/polling (see research.md); `readAt` mutation is optimistic (low-risk, trivially reversible).

---

## Audit Trail Entry

| Field | Notes |
|---|---|
| `id`, `applicationId`, `eventType`, `actor`, `timestamp`, `payload` | Read-only projection of the backend's existing audit-event record |

**Caching tier**: Read-only, append-only, long-lived cache (an audit trail entry never changes once written) — the frontend must not expose any mutation affordance for this type at all.

---

## Cross-Cutting State Machines

**Document ingestion**: `pending → in_progress → completed | failed` (drives Document Viewer and queue-row rendering; see 002 Edge Cases).

**Finding lifecycle**: `unreviewed → verified | overridden | escalated` (drives which action controls the Application Workspace renders; 002 FR-053).

**Application lifecycle**: driven entirely by backend-owned status values; the frontend never computes or infers a status transition locally — it only requests one (via a confirmed mutation) and renders whatever the backend subsequently returns.
