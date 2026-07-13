# Feature Specification: Mortgage Intelligence Layer — Enterprise Platform

**Feature Branch**: `005-enterprise-platform`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "The MIL MVP is complete and frozen (tagged). We are no longer
building an MVP — we are now completing the full enterprise Mortgage Intelligence Layer platform.
This is the complete product vision, not a V2/V3 increment. Extend the existing architecture with:
Relationship Manager/Banker Workspace, LOS Integration Layer, Policy Engine, Policy Administration,
Borrower Identity Resolution, Cross-Application Intelligence, Universal Search, AI Case Copilot,
Collaboration, Operational Dashboard, Business Analytics, Customer Portal, Notification System,
Production Infrastructure, Enterprise Administration, Security and Compliance, Deployment
Architecture. Produce business objectives, functional requirements, non-functional requirements,
user stories, domain model additions, database schema changes, API contracts, RBAC changes, AI
considerations, integration requirements, UX considerations, acceptance criteria, risks, and future
extensibility for every module. Do not implement. Preserve MVP principles: AI assists but never
decides, human-in-the-loop, explainability, traceability, auditability, enterprise-first
architecture, honest UX, extensibility."

---

## 0. How to read this document

This is a **master specification**, not a single feature spec. It governs 17 modules that together
complete the Mortgage Intelligence Layer. Each module gets its own numbered section (§1–§17) with
the same 13 subsections, in the same order, so implementation can proceed systematically without
revisiting product architecture. Sections are ordered by dependency, not by build priority —
Product/Engineering may sequence delivery differently; this document is the target state, not the
roadmap. A separate `plan.md` will be produced per module (or per related module cluster) once this
spec is reviewed, following normal `/speckit-plan` → `/speckit-tasks` → `/speckit-implement` flow.

**Foundational and NOT redesigned by this spec** (per explicit instruction): Underwriter Workspace,
the AI extraction/finding pipeline (`src/workers/document_pipeline.py`, `finding_pipeline.py`,
`policy_pipeline.py`), Evidence, Findings, the existing Policy evaluation model (`src/mil/policy/`),
Timeline, Audit, and Human Review (Verify/Override/Escalate). These are treated as stable
dependencies that new modules integrate with, never rebuild. Where a module below needs to change
one of these (e.g. a new event type, a new read-only query), that is called out explicitly as an
**additive** change — no existing contract, table, or UI is altered destructively.

**Ground-truth discipline** (carried over from the MVP build, and non-negotiable in this spec):
every domain-model addition, schema change, and API contract below is checked against what
*already exists* in `src/mil/**`, `specs/001-mil-platform-spec/`, and the frontend `entities/**`
before being proposed as new. Three bounded contexts already have real, working scaffolding this
spec extends rather than invents:

| Bounded context | Existing state | Which module below extends it |
|---|---|---|
| `src/mil/policy/` | `PolicyPack`, `PolicyRule`, `PolicyResult` ORM models + `PolicyService` + repository — no HTTP route exists yet | §3 Policy Engine, §4 Policy Administration |
| `src/mil/identity/` | `User`, `Role`, `RoleAssignment` ORM models + `rbac.py` + `abac.py` (tenant isolation, cross-application denial) + `dev_seed.py` — no HTTP route exists yet | §15 Enterprise Administration, §16 Security & Compliance |
| `src/mil/copilot/` | **Fully wired already**: `CopilotSession`/`CopilotQuery`/`CopilotResponse` models, a full grounding/citation service (`service.py`, `citations.py`, `ports.py`, `adapters.py`, `classifier.py`, `prompts.py`), a real API layer (`src/mil/api/v1/copilot.py` — `POST /v1/copilot/query`, `GET /v1/copilot/sessions/{id}`, `GET /v1/copilot/sessions/{id}/history`, `GET /v1/applications/{id}/copilot`), an OpenAPI contract (`specs/001-mil-platform-spec/contracts/copilot.yaml`), and mounted in `src/main.py` (`copilot_router`/`application_copilot_router` both registered). **Corrected from an earlier draft of this table, which understated this — verified directly against `src/main.py`'s router registration before this correction.** Zero frontend consumes it. | §8 AI Case Copilot (frontend-only gap) |
| `src/mil/review/` | `ReviewComment` model + `add_comment()` service method exist — confirmed no `comment` route anywhere in `src/mil/api/v1/*.py` and no dedicated route module — no HTTP route exists yet | §9 Collaboration |
| `src/mil/integration/` | Package stub only (`__init__.py`) — genuinely greenfield | §2 LOS Integration Layer |
| `src/mil/operational/` | Package stub only (`__init__.py`) — genuinely greenfield | §10 Operational Dashboard, §11 Business Analytics |

Also re-confirmed at this pass: `src/mil/policy/` and `src/mil/identity/` still have **no** route module under `src/mil/api/v1/` (no `policy.py`, no `identity.py`/`admin.py`/`users.py`) and neither is registered in `src/main.py` — the original assessment for those two stands unchanged.

This table is the single most important piece of scoping information in this document: for four of
seventeen modules, the primary work is **wiring an HTTP API and a frontend onto a domain layer that
already exists and already passes its own unit tests** — not inventing new business logic. Treat
proposals in §3, §4, §8, §9 accordingly (lighter backend lift, same UX/API-contract rigor).

**Constitution compliance**: every module below is checked against all twelve principles in
`.specify/memory/constitution.md` (v1.1.0). None of the twelve principles are amended, relaxed, or
reinterpreted by this spec — this document extends the domain, it does not touch governance.
A per-module Constitution Check is included in each module's Acceptance Criteria.

---

## 1. Relationship Manager / Banker Workspace

### 1.1 Business objectives
- Give the loan-originating side of the bank (Relationship Managers / Bankers) a first-class
  workspace, distinct from the Underwriter Workspace, so origination and underwriting are no
  longer two disconnected worlds sharing one screen design.
- Reduce back-and-forth between RM and Underwriter by giving the RM visibility into where "their"
  applications stand in the AI pipeline and review process, without granting underwriting authority.
- Close the roadmap gap explicitly deferred during the MVP UI build ("Assignment Management" —
  see prior plan's Non-goals) — this is where it lands.

### 1.2 Functional requirements
- **FR-RM-001**: System MUST provide a Banker Workspace landing view scoped to applications where
  the authenticated user is the originating RM or an assigned collaborator (see FR-RM-004).
- **FR-RM-002**: RM MUST be able to originate a new application and borrower/party intake using the
  existing intake flow (`POST /v1/applications`, `POST /v1/applications/{id}/parties` — unchanged
  contracts) from within the Banker Workspace, not only from the Underwriter Workspace.
- **FR-RM-003**: RM MUST be able to view application status, processing pipeline state, and a
  read-only summary of Findings (`what`/`state`, not full explainability detail) for their own
  applications — RM has no Verify/Override/Escalate capability (enforced by RBAC, §1.6).
- **FR-RM-004**: System MUST support explicit **assignment** of an application to one RM (owner)
  and, optionally, one Underwriter (reviewer) — this is the "Assignment Management" capability the
  MVP UI plan deferred as backend-dependent. Assignment is now in scope because this spec adds the
  backend field.
- **FR-RM-005**: RM MUST be able to message the assigned Underwriter about a specific application
  through the Collaboration module (§9) — not a separate messaging system.
- **FR-RM-006**: RM Workspace MUST show a portfolio view: applications grouped by stage, with a
  count of "awaiting borrower documents" (derived from Document Checklist status introduced by the
  Customer Portal module, §12) and "awaiting underwriter action."
- **FR-RM-007**: RM MUST NOT be able to view another RM's applications unless granted a
  supervisory role (Regional Manager) — enforced via ABAC (`abac.py`'s existing pattern), not just
  UI filtering.

### 1.3 Non-functional requirements
- Workspace list/portfolio queries MUST meet the same p95 < 300ms target already set for reviewer
  endpoints in `specs/001-mil-platform-spec/plan.md`.
- RM-facing pipeline/status views MUST reuse the exact status vocabulary already established
  (`ApplicationStatus` enum, `APPLICATION_STATUS_CHIP_CLASS_NAME` map from the Phase 11 UI pass) —
  no second status taxonomy.
- Assignment changes MUST be audited (Principle VIII) with the same rigor as Verify/Override.

### 1.4 User stories
- **US-RM-1 (P1)**: As an RM, I originate a new application, add the borrower, and hand it to
  Documents/Upload — identical journey to what the Underwriter Workspace already does, just entered
  from my own workspace. *Independent test*: create an application as an RM-only user and confirm
  it appears correctly in both the RM portfolio view and (once assigned) the Underwriter queue.
- **US-RM-2 (P1)**: As an RM, I check my portfolio each morning and see which applications are
  stalled waiting on the borrower vs. waiting on the underwriter, so I know who to follow up with.
  *Independent test*: seed applications in each state; confirm portfolio counts match.
- **US-RM-3 (P2)**: As an RM, I assign an application to a specific underwriter and see that
  reflected in their queue immediately. *Independent test*: assignment write → underwriter queue
  read, within one request cycle, no polling delay beyond existing query invalidation.
- **US-RM-4 (P3)**: As a Regional Manager, I view all RMs' portfolios in my region in one combined
  view. *Independent test*: a Regional Manager role sees N RMs' applications; an RM role does not.

### 1.5 Domain model additions
- **`Assignment`** (new entity) — `id`, `applicationId` (FK, unique — one active assignment record
  per application, historized via `AssignmentHistory`, not overwritten), `ownerUserId` (RM),
  `reviewerUserId` (Underwriter, nullable until assigned), `assignedByUserId`, `assignedAt`,
  `previousAssignmentId` (nullable, for reassignment chains).
- **`AssignmentHistory`** (new entity, append-only) — same shape as `Assignment`, one row per
  assignment/reassignment event, never updated — mirrors the Evidence/Audit immutability pattern
  already established (Principle VIII).
- No change to `MortgageApplication`, `Party`, `Document`, `Evidence`, or `Finding` aggregates.

### 1.6 Database schema changes
```sql
-- New table, `core` schema (co-located with application/party per existing convention)
CREATE TABLE core.assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES core.applications(id),
    owner_user_id UUID NOT NULL REFERENCES identity.users(id),
    reviewer_user_id UUID REFERENCES identity.users(id),
    assigned_by_user_id UUID NOT NULL REFERENCES identity.users(id),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    previous_assignment_id UUID REFERENCES core.assignment_history(id),
    UNIQUE (application_id)
);

CREATE TABLE core.assignment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES core.applications(id),
    owner_user_id UUID NOT NULL REFERENCES identity.users(id),
    reviewer_user_id UUID REFERENCES identity.users(id),
    assigned_by_user_id UUID NOT NULL REFERENCES identity.users(id),
    assigned_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_assignments_owner ON core.assignments(owner_user_id);
CREATE INDEX idx_assignments_reviewer ON core.assignments(reviewer_user_id);
```
Depends on `identity.users` existing as a real table — currently true in the ORM model
(`src/mil/identity/models.py`) but **not yet migrated/routed** (see the ground-truth table above);
this migration must run after §15's identity migration, not before.

### 1.7 API contracts (additive; existing `applications.yaml` untouched except as noted)
- `PUT /v1/applications/{id}/assignment` — body `{ownerUserId, reviewerUserId?}` → `Assignment`.
  Requires `Permission.WRITE_APPLICATION` **and** a new `Permission.MANAGE_ASSIGNMENT`.
- `GET /v1/applications/{id}/assignment` → `Assignment | null`.
- `GET /v1/applications/{id}/assignment-history` → `AssignmentHistory[]`.
- `GET /v1/applications?ownerUserId={me}` — additive query param on the existing list endpoint
  (same pattern as the already-proposed `search` param from the MVP's Phase 1), not a new endpoint.
- `GET /v1/rm/portfolio` — RM-scoped aggregate view: counts by status + "awaiting documents" +
  "awaiting underwriter," computed server-side (avoids the N+1 risk already flagged in the MVP
  plan's field-availability audit for per-application aggregates).

### 1.8 RBAC changes
- New permission: `Permission.MANAGE_ASSIGNMENT` (`manage:assignment`).
- `Role.RELATIONSHIP_MANAGER` (already exists in `src/mil/kernel/security.py`) gains
  `READ_APPLICATION`, `WRITE_APPLICATION` (already held), `MANAGE_ASSIGNMENT` (own applications
  only, enforced via ABAC ownership check, not a blanket grant).
- New role: `Role.REGIONAL_MANAGER` — superset of `RELATIONSHIP_MANAGER` permissions, scoped via
  ABAC to a `regionId` attribute on `User` (new column, §15) rather than a new permission.
- Underwriter/Compliance/Audit roles are unaffected — this module adds no new restriction on them.

### 1.9 AI considerations
- No new AI capability in this module. The RM Workspace surfaces **existing** AI outputs
  (processing pipeline stage, finding counts) at reduced detail — it never re-runs or re-interprets
  a Finding. Per Principle I, RM cannot verify/override/escalate; the workspace is read-plus-assign,
  not a second review surface.

### 1.10 Integration requirements
- None beyond the existing internal APIs. This module has no LOS dependency of its own — origination
  data still flows through the same `POST /v1/applications` contract §2 will eventually also feed
  from an LOS push.

### 1.11 UX considerations
- Reuses the Phase 11 design language (borderless elevated panels, stat-row pattern from the
  Underwriter Home Dashboard) rather than inventing a new visual system for a second workspace.
- Assignment is a lightweight inline action (assignee picker), not a modal wizard — it's a
  one-field, low-friction operation performed frequently.
- RM Workspace explicitly does **not** expose the Findings explainability detail, Evidence, Policy,
  or Timeline regions — only a status/count summary — so the UI itself enforces the "read-plus-
  assign, not review" boundary the RBAC layer also enforces, defense in depth applied to UX.

### 1.12 Acceptance criteria
- Given an RM-only user, when they open the Banker Workspace, then they see only applications they
  own or are assigned to, never another RM's applications, without a supervisory role.
- Given an application with `reviewerUserId` set, when the assigned Underwriter opens their queue,
  then that application appears immediately (query invalidation on assignment write).
- Given an RM attempts a `POST /v1/applications/{id}/findings/{findingId}/verify` call directly,
  then the request is rejected with 403 (RBAC enforced server-side, not just hidden client-side).
- **Constitution check**: Principle I (RM cannot decide) ✅; Principle VIII (assignment changes
  audited) ✅; Principle VII (new entities named `Assignment`/`AssignmentHistory`, not generic
  `Task`/`Ownership`) ✅.

### 1.13 Risks
- **Reassignment races**: two supervisors reassigning the same application concurrently — mitigated
  by the `UNIQUE(application_id)` constraint on the live `assignments` row plus an optimistic
  version check on `PUT`.
- **Scope creep into full CRM**: this module must stay a workspace onto MIL's own data, not become
  a parallel pipeline/CRM system — non-goal, stated explicitly in §1.14-equivalent risk framing.
- **RBAC ABAC complexity growth**: adding region-scoped ABAC (`REGIONAL_MANAGER`) is the first
  attribute-scoped role beyond tenant/application scope — must be implemented as a generalizable
  attribute policy (extending `abac.py`), not a one-off special case, or §15/§16 will each invent
  their own variant.

### 1.14 Future extensibility
- Assignment model is deliberately generic enough to support future auto-assignment/load-balancing
  rules (not built here) without a schema change — `assignedByUserId` distinguishes system-assigned
  from human-assigned once that capability exists.
- `AssignmentHistory` is the substrate for a future "reassignment reasons" analytics view (§11).

---

## 2. LOS Integration Layer

### 2.1 Business objectives
- Fulfil Constitution Principle VI (API-First Integration) in practice: MIL must integrate with
  existing LOS platforms (Encompass, Wipro NetOxygen, Temenos, Finastra, nCino, etc.) without
  requiring those systems to change, and without MIL ever writing loan-decision state back
  autonomously (Integration Model: read → enrich → return).
- Remove the current manual-only origination path as the sole entry point — applications should be
  able to arrive from an LOS push/sync, not just manual intake.

### 2.2 Functional requirements
- **FR-LOS-001**: System MUST support registering one or more **LOS Connections** per tenant, each
  with a vendor adapter type, credentials (stored via the secrets manager, §14, never in the DB),
  and a sync mode (`WEBHOOK` push or `POLL` pull).
- **FR-LOS-002**: System MUST provide an adapter interface (`LOSAdapter` Protocol) with a bounded
  method set: `fetch_application(los_reference) -> LOSApplicationPayload`,
  `list_updated_since(timestamp) -> Iterable[LOSApplicationPayload]`, and
  `push_status(application_id, status, note) -> LOSPushResult` — the last one is the *only* write
  path, and it is always a human-initiated action proxied through MIL, never autonomous (Principle
  VI, Integration Model).
- **FR-LOS-003**: An inbound LOS payload MUST be mapped through a per-connection **Field Mapping**
  (configurable, not hardcoded per vendor) into MIL's `CreateApplicationRequest`/`AddPartyRequest`
  shapes — reusing the existing contracts unchanged.
- **FR-LOS-004**: System MUST record every inbound sync and outbound push as an immutable
  **Integration Event** (Principle VIII) capturing the raw payload (redacted per §16's data
  minimisation rule), the mapped result, and success/failure.
- **FR-LOS-005**: A failed sync MUST NOT silently drop data — it lands in a **Sync Failure Queue**
  visible to Operations (§10) with the real adapter error message, never a generic failure banner
  (the same "never a generic error, always the real message" discipline established for document
  ingestion in the MVP build).
- **FR-LOS-006**: System MUST de-duplicate inbound applications by `(tenantId, losReference)` —
  a repeat sync of the same LOS record updates the existing MIL application, it does not create a
  duplicate.
- **FR-LOS-007**: `push_status` MUST require an explicit human action (a reviewer or RM clicking
  "Sync status to LOS") — never triggered automatically by a Finding or Policy result changing.

### 2.3 Non-functional requirements
- Adapter implementations MUST be pluggable at deployment time (Principle VI: vendor-agnostic core)
  — the core `mil.integration` package has zero import of any vendor SDK; vendor adapters are a
  separate, optionally-installed package.
- Sync latency target: an LOS-pushed application MUST be visible in MIL within 60 seconds of
  webhook receipt (matches the existing 60-second document-ingestion target order of magnitude).
- The integration layer MUST be resilient to LOS downtime: poll-mode connections back off
  exponentially and resume without manual intervention; webhook receivers return 2xx immediately
  and process asynchronously via the existing `JobQueue` (Principle IX: reuse existing
  infrastructure, don't invent a second queue).

### 2.4 User stories
- **US-LOS-1 (P1)**: As an Operations engineer, I register a new LOS connection with credentials
  and a field mapping, and confirm a test sync succeeds, without any code deployment.
  *Independent test*: connection CRUD + a dry-run sync against a mock adapter.
- **US-LOS-2 (P1)**: As the platform, when the LOS pushes a new loan record, I create a MIL
  application and parties automatically, visible in the RM/Underwriter workspaces within the
  latency target. *Independent test*: webhook → application exists, fields correctly mapped.
- **US-LOS-3 (P2)**: As a reviewer, I click "Sync status to LOS" after a decision and see the real
  LOS response (success or the vendor's actual error) reflected in MIL. *Independent test*: mock
  adapter returns a failure string; MIL displays it verbatim, doesn't mask it as generic.
- **US-LOS-4 (P3)**: As Operations, I see a queue of failed syncs with real error detail and can
  manually retry one. *Independent test*: seeded failure → retry → success transitions the record
  out of the failure queue.

### 2.5 Domain model additions
- **`LOSConnection`** — `id`, `tenantId`, `vendorType` (enum, open-ended string per the existing
  "free string, not closed enum" convention used for `Document.documentType`), `syncMode`,
  `credentialRef` (opaque pointer into the secrets manager, never a raw credential column),
  `fieldMappingId`, `status` (`ACTIVE`/`PAUSED`/`FAILED`), `lastSyncedAt`.
- **`LOSFieldMapping`** — `id`, `connectionId`, `mappingDefinition` (JSON: source-field → MIL-field
  transform rules), `version` (versioned like Policy Packs, so a mapping change is traceable).
- **`LOSSyncEvent`** — append-only, `id`, `connectionId`, `direction` (`INBOUND`/`OUTBOUND`),
  `losReference`, `applicationId` (nullable until mapped), `payloadRedacted`, `outcome`
  (`SUCCESS`/`FAILURE`), `errorMessage`, `occurredAt`. This is the Integration Event of FR-LOS-004.
- **`LOSPushRequest`** — `id`, `applicationId`, `initiatedByUserId`, `requestedStatus`, `note`,
  `result` (`PENDING`/`SUCCESS`/`FAILURE`), `respondedAt`.

### 2.6 Database schema changes
```sql
CREATE SCHEMA IF NOT EXISTS integration;

CREATE TABLE integration.los_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    vendor_type TEXT NOT NULL,
    sync_mode TEXT NOT NULL CHECK (sync_mode IN ('WEBHOOK', 'POLL')),
    credential_ref TEXT NOT NULL,
    field_mapping_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE integration.los_field_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES integration.los_connections(id),
    mapping_definition JSONB NOT NULL,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE integration.los_sync_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id UUID NOT NULL REFERENCES integration.los_connections(id),
    direction TEXT NOT NULL CHECK (direction IN ('INBOUND', 'OUTBOUND')),
    los_reference TEXT,
    application_id UUID REFERENCES core.applications(id),
    payload_redacted JSONB,
    outcome TEXT NOT NULL CHECK (outcome IN ('SUCCESS', 'FAILURE')),
    error_message TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_los_sync_events_connection ON integration.los_sync_events(connection_id);
CREATE UNIQUE INDEX idx_los_dedup ON core.applications(tenant_id, los_reference)
    WHERE los_reference IS NOT NULL;

CREATE TABLE integration.los_push_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES core.applications(id),
    initiated_by_user_id UUID NOT NULL REFERENCES identity.users(id),
    requested_status TEXT NOT NULL,
    note TEXT,
    result TEXT NOT NULL DEFAULT 'PENDING',
    responded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.7 API contracts
- `POST /v1/integrations/los/connections` / `GET .../connections` / `PATCH .../connections/{id}`
  (admin-only; credentials write-only, never returned in a `GET`).
- `POST /v1/integrations/los/connections/{id}/test` — dry-run sync, no persistence.
- `POST /v1/integrations/los/webhooks/{connectionId}` — vendor webhook receiver (auth via a
  per-connection signing secret, not session auth).
- `GET /v1/integrations/los/sync-events?outcome=FAILURE` — the Sync Failure Queue.
- `POST /v1/integrations/los/sync-events/{id}/retry`.
- `POST /v1/applications/{id}/los-push` — body `{status, note}` → `LOSPushRequest`.
- OpenAPI file: new `integrations-los.yaml`, additive to the existing contracts directory.

### 2.8 RBAC changes
- New permission: `Permission.MANAGE_INTEGRATION` (**already exists** as a constant in
  `security.py` but is currently unused by any route — this module is its first real consumer).
- New permission: `Permission.PUSH_LOS_STATUS` — granted to `UNDERWRITER`, `RELATIONSHIP_MANAGER`;
  connection management (`MANAGE_INTEGRATION`) stays `ADMIN`-only.
- Webhook receiver authenticates via signing-secret verification, not a user role — service-to-
  service, logged as `SERVICE_ACCOUNT` actor in the audit trail.

### 2.9 AI considerations
- None. This module is deliberately non-AI — it is a deterministic mapping and transport layer.
  Explicitly note (Principle XII, Deterministic Intelligence): field-mapping transforms MUST be
  pure/deterministic functions of the mapping definition, never an AI-inferred mapping, so a sync
  is always reproducible from the same inputs.

### 2.10 Integration requirements
- This module *is* the integration requirement for the rest of the platform. Vendor-specific
  adapters (Encompass, NetOxygen, etc.) are out of scope for this spec — only the adapter
  *interface* and one reference/mock adapter (used for contract testing) are specified here.
  Building a real vendor adapter is a follow-on, adapter-by-adapter effort.

### 2.11 UX considerations
- Connection management is an Enterprise Administration screen (§15), not a reviewer-facing one.
- The Sync Failure Queue reuses the Operational Dashboard's (§10) existing queue/table visual
  language — it is one more operational queue, not a bespoke screen.
- `push_status` is a single confirm-dialog action from the Application Workspace header, following
  the same non-optimistic, mandatory-confirm pattern already used for Verify/Override/Escalate.

### 2.12 Acceptance criteria
- Given a registered `POLL`-mode connection, when a mock LOS returns two updated records, then two
  MIL applications are created/updated correctly-mapped, with a `LOSSyncEvent` per record.
- Given a sync failure, when Operations views the Sync Failure Queue, then the real adapter error
  string is shown verbatim.
- Given a duplicate LOS reference on the same tenant, when synced twice, then no duplicate
  application is created — the existing one is updated.
- Given a non-Admin user attempts to create a connection, then 403.
- **Constitution check**: Principle VI (vendor-agnostic core, adapters pluggable) ✅; Integration
  Model (no autonomous write — `push_status` always human-initiated) ✅; Principle VIII (every
  sync/push is an audited event) ✅.

### 2.13 Risks
- **Credential handling**: LOS credentials are highly sensitive — must go through §14/§16's secrets
  management from day one; this module MUST NOT store raw credentials in `los_connections` even
  temporarily (mitigated by `credentialRef` being an opaque pointer, never the secret itself).
- **Vendor heterogeneity**: field-mapping flexibility (JSON `mappingDefinition`) risks becoming an
  under-specified escape hatch — mitigated by a strict mapping-definition schema validated at
  connection-save time, not left as an arbitrary blob.
- **Webhook replay/security**: signature verification and idempotency (via `LOSSyncEvent`
  dedup on `(connectionId, losReference, payload hash)`) are mandatory, not optional hardening.

### 2.14 Future extensibility
- The adapter Protocol is intentionally minimal (3 methods) so new vendors are additive packages,
  never core changes. A future bidirectional document sync (pulling LOS-stored documents into MIL)
  is a natural extension of `fetch_application`'s payload shape, not a new interface.

---

## 3. Policy Engine

### 3.1 Business objectives
- Give the **existing** policy evaluation domain layer (`src/mil/policy/`: `PolicyPack`,
  `PolicyRule`, `PolicyResult`, `PolicyService`) a real HTTP surface and a real activation
  mechanism — today, per the MVP build's own research (Phase 7 of the prior UI plan), **no code
  path anywhere creates or activates a `PolicyPack` in production**, which is why every finding in
  the demo dataset has `policyVersion: null`. This module closes that gap.
- Make policy evaluation results genuinely queryable per-rule (today `PolicyResult` exists as a
  domain concept but the MVP UI research confirmed no endpoint exposes rule-level pass/fail) —
  this is the "which rules passed" gap the MVP's Phase 7 explicitly and honestly disclosed as
  unbuildable *at the time*; this module is what makes it buildable.

### 3.2 Functional requirements
- **FR-POL-001**: System MUST expose `PolicyPack`/`PolicyRule` through a real API (read for all
  reviewer roles; write for `MANAGE_POLICY_PACKS` only, see §4 for the authoring workflow).
- **FR-POL-002**: System MUST record a `PolicyResult` row **per rule, per finding-generation run**
  — not only for rules that fail. This is the single largest functional change in this module: the
  existing `PolicyResult` model must be populated for *every* evaluated rule (pass or fail), so
  "which rules passed" becomes a real, queryable fact for the first time.
- **FR-POL-003**: `finding_pipeline.py`/`policy_pipeline.py` (existing, unmodified business logic)
  MUST be extended — additively, same function signatures wrapped, not rewritten — to write the
  full per-rule `PolicyResult` set as part of the existing evaluation run, using the existing
  `PolicyService`.
- **FR-POL-004**: An application MUST be evaluated under exactly one **active** `PolicyPack` per
  jurisdiction at any given time; policy activation is atomic (only one `ACTIVE` pack per
  jurisdiction) and versioned (activating pack v2 does not retroactively change v1's already-
  recorded results — Principle XII).
- **FR-POL-005**: `GET .../policy-results` MUST support filtering by outcome, rule, and finding —
  the read side of FR-POL-002.

### 3.3 Non-functional requirements
- Writing N per-rule results instead of only failing ones increases write volume roughly by the
  average rule count per pack (expect single-digit-to-low-double-digit rules per pack at initial
  scale) — must not push policy evaluation past the existing pipeline's processing budget; batched
  insert, not N round trips.
- Policy evaluation MUST remain deterministic (Principle XII) — identical evidence + identical
  active policy version MUST produce identical `PolicyResult` rows if re-run.

### 3.4 User stories
- **US-POL-1 (P1)**: As a Policy Administrator, I activate PolicyPack v3 for the US jurisdiction and
  confirm new applications are evaluated against it while historical findings retain their original
  `policyVersion`. *Independent test*: activate → new evaluation run → check `policyVersion`
  matches; historical finding unchanged.
- **US-POL-2 (P1)**: As a Compliance Officer, I query "which rules were checked and passed" for a
  given application — for the first time, a real answer instead of "no such data exists" (the MVP's
  Phase 7 disclosure). *Independent test*: seed a pack with 5 rules, 2 trigger findings, 3 don't;
  confirm all 5 appear in `PolicyResult` with correct outcomes.
- **US-POL-3 (P2)**: As an Underwriter, I see a rule-level breakdown in the Policy region (extends
  the existing `groupFindingsByPolicyVersion` region from the MVP build) instead of only a
  finding-count summary.

### 3.5 Domain model additions
- No new entities — `PolicyPack`, `PolicyRule`, `PolicyResult` already exist
  (`src/mil/policy/models.py`). Additions are **behavioral** (write path populates all rows, not
  only failures) and one new field:
- **`PolicyRule.appliesTo`** (new column, nullable JSON predicate) — lets a rule scope itself to a
  document/party type, needed once per-rule evaluation is exhaustive (today only triggered rules
  existed, so scoping was implicit in "did it fire").

### 3.6 Database schema changes
```sql
-- Additive column only; PolicyPack/PolicyRule/PolicyResult tables already exist.
ALTER TABLE policy.policy_rules ADD COLUMN applies_to JSONB;

-- New partial index supporting FR-POL-005's outcome filter at scale
CREATE INDEX idx_policy_results_outcome ON policy.policy_results(outcome);
CREATE INDEX idx_policy_results_finding ON policy.policy_results(finding_id);
```

### 3.7 API contracts
- `GET /v1/policy-packs` / `GET /v1/policy-packs/{id}` — read, all authenticated reviewer roles.
- `GET /v1/applications/{id}/policy-results?outcome=PASSED|FAILED&ruleId=` — the FR-POL-005 read
  endpoint (additive; sits alongside the existing `applications.yaml`).
- Write endpoints (`create pack`, `add rule`, `activate pack`) are specified in §4 (Policy
  Administration owns the authoring workflow; this section owns the evaluation/read contract).
- New OpenAPI file: `policy.yaml`.

### 3.8 RBAC changes
- `Permission.MANAGE_POLICY_PACKS` **already exists** in `security.py`, currently unused by any
  route — this module (jointly with §4) is its first consumer.
- New permission: `Permission.READ_POLICY_RESULTS` — granted to all existing reviewer roles that
  already hold `READ_FINDINGS` (`UNDERWRITER`, `CREDIT_ANALYST`, `RISK_ANALYST`,
  `COMPLIANCE_OFFICER`, `AUDIT_TEAM`).

### 3.9 AI considerations
- Policy evaluation itself is explicitly **not** AI (Principle IV/XII) — it is deterministic rule
  evaluation against AI-produced Evidence/Findings. This module must not blur that line: a
  `PolicyRule`'s condition logic is declarative/deterministic, never an LLM call. AI produces the
  Evidence and Findings that policy rules evaluate; policy itself stays rule-based.

### 3.10 Integration requirements
- None new. Consumes existing Evidence/Finding data internally within the modular monolith
  (Principle: modules communicate via defined service interfaces, not direct model access —
  `PolicyService` already respects this).

### 3.11 UX considerations
- Extends (does not replace) the Policy region built in the MVP's Phase 7 — the honest "cannot show
  rules that passed silently" disclosure banner is **removed** once FR-POL-002 ships (it becomes
  false), replaced with the real per-rule breakdown it was withholding.
- Rule-level rows reuse the existing `STATE_LABEL`/badge vocabulary — passed/failed/not-evaluated,
  not a new color system.

### 3.12 Acceptance criteria
- Given an active PolicyPack with 5 rules and one finding-generation run, when evaluation completes,
  then exactly 5 `PolicyResult` rows exist for that run (not just the triggering rule's row).
- Given two PolicyPack versions, when v2 is activated, then applications evaluated before
  activation retain `policyVersion` referencing v1.
- Given a non-privileged role queries `policy-results`, then 403 unless they hold
  `READ_POLICY_RESULTS`.
- **Constitution check**: Principle XII (deterministic, versioned, reproducible) ✅; Principle IV
  (policy is not automation of the lending decision — it informs, doesn't decide) ✅.

### 3.13 Risks
- **Retroactive volume**: exhaustive per-rule writes on a large policy pack could become a real
  storage/perf concern at high application volume — mitigated by requiring FR-POL-002's write to be
  a single batched insert per run, revisited in a future performance pass, not solved by NFR
  hand-waving here.
- **Rule condition expressiveness**: `appliesTo` JSON predicates risk becoming a bespoke DSL with no
  governance — this module defines the schema; §4 owns validation/authoring UX so the DSL doesn't
  sprawl uncontrolled.

### 3.14 Future extensibility
- `PolicyRule.appliesTo` is the seam for jurisdiction/product-type-scoped rules without a schema
  change. `PolicyResult`'s exhaustive per-rule recording is what makes a future "policy coverage"
  analytics view (§11) possible without inventing new data.

---

## 4. Policy Administration

### 4.1 Business objectives
- Give Compliance/Policy Administrators a real authoring and approval workflow for `PolicyPack`s —
  today the *only* way a pack could exist is a direct DB write or test fixture (confirmed during
  the MVP build). This module is the human-facing front door onto §3's engine.
- Enforce a **maker-checker** approval step before a policy pack goes live, matching regulated-
  industry norms for changing the rules that govern lending-adjacent decisions.

### 4.2 Functional requirements
- **FR-PADM-001**: A Policy Administrator MUST be able to draft a new `PolicyPack` (name,
  jurisdiction, rule set) without it becoming `ACTIVE` — a `DRAFT` state, distinct from `ACTIVE`/
  `RETIRED` (extends `PolicyPack`'s existing status concept, does not replace it).
- **FR-PADM-002**: Activating a pack MUST require a second, different authenticated user's approval
  (maker-checker) — the drafter cannot self-approve.
- **FR-PADM-003**: Every rule addition/edit/removal within a draft MUST be tracked with a diff
  against the previous version, so an approver reviews *what changed*, not the whole pack blind.
- **FR-PADM-004**: Activation MUST be atomic per jurisdiction (only one `ACTIVE` pack at a time,
  enforced at the DB layer via a partial unique index, not just application logic).
- **FR-PADM-005**: A retired pack's historical findings/results MUST remain queryable exactly as
  recorded (Principle XII) — retirement never rewrites history.

### 4.3 Non-functional requirements
- Activation is a rare, deliberate, low-throughput operation — no special performance target beyond
  standard API latency; correctness and auditability dominate over speed here.
- Draft editing MUST NOT be visible to any role other than the drafter and designated approvers
  until submitted for approval (confidentiality of in-progress policy changes).

### 4.4 User stories
- **US-PADM-1 (P1)**: As a Policy Administrator, I draft a new pack with 6 rules, submit it for
  approval, and it does not affect any live evaluation until approved and activated.
  *Independent test*: draft exists, `GET /v1/policy-packs?status=ACTIVE` unaffected.
- **US-PADM-2 (P1)**: As a Compliance Officer (approver), I review a diff of what changed in a
  submitted pack and approve or reject it with a mandatory reason (mirrors the existing
  Override/Escalate "mandatory reason" pattern). *Independent test*: reject with reason → pack
  stays in `REJECTED`, drafter notified (§13).
- **US-PADM-3 (P2)**: As the drafter of a pack, I cannot approve my own submission.
  *Independent test*: self-approval attempt → 403.

### 4.5 Domain model additions
- **`PolicyPack.status`** extended enum: `DRAFT | PENDING_APPROVAL | ACTIVE | REJECTED | RETIRED`
  (extends the existing status field, does not rename it).
- **`PolicyPackApproval`** (new entity, append-only) — `id`, `policyPackId`, `requestedByUserId`,
  `decidedByUserId` (nullable until decided), `decision` (`PENDING`/`APPROVED`/`REJECTED`),
  `reason` (mandatory on rejection, optional on approval), `decidedAt`.
- **`PolicyRuleChange`** (new entity, append-only) — `id`, `policyPackId`, `ruleId`, `changeType`
  (`ADDED`/`MODIFIED`/`REMOVED`), `previousDefinition`, `newDefinition`, `changedAt` — the diff
  substrate for FR-PADM-003.

### 4.6 Database schema changes
```sql
ALTER TABLE policy.policy_packs
    ADD CONSTRAINT chk_policy_pack_status
    CHECK (status IN ('DRAFT','PENDING_APPROVAL','ACTIVE','REJECTED','RETIRED'));

CREATE UNIQUE INDEX idx_one_active_pack_per_jurisdiction
    ON policy.policy_packs(jurisdiction) WHERE status = 'ACTIVE';

CREATE TABLE policy.policy_pack_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_pack_id UUID NOT NULL REFERENCES policy.policy_packs(id),
    requested_by_user_id UUID NOT NULL REFERENCES identity.users(id),
    decided_by_user_id UUID REFERENCES identity.users(id),
    decision TEXT NOT NULL DEFAULT 'PENDING' CHECK (decision IN ('PENDING','APPROVED','REJECTED')),
    reason TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (requested_by_user_id != decided_by_user_id)
);

CREATE TABLE policy.policy_rule_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_pack_id UUID NOT NULL REFERENCES policy.policy_packs(id),
    rule_id UUID,
    change_type TEXT NOT NULL CHECK (change_type IN ('ADDED','MODIFIED','REMOVED')),
    previous_definition JSONB,
    new_definition JSONB,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.7 API contracts
- `POST /v1/policy-packs` (creates `DRAFT`), `PATCH /v1/policy-packs/{id}/rules` (draft-only edits,
  writes a `PolicyRuleChange` per edit), `POST /v1/policy-packs/{id}/submit-for-approval`,
  `POST /v1/policy-packs/{id}/approve`, `POST /v1/policy-packs/{id}/reject` (`{reason}`),
  `POST /v1/policy-packs/{id}/activate` (only from an `APPROVED`-adjacent state — approval and
  activation are separate steps so an approved-but-not-yet-live pack can be scheduled).
- `GET /v1/policy-packs/{id}/diff` → `PolicyRuleChange[]` for the current draft cycle.
- New OpenAPI file: `policy-administration.yaml`.

### 4.8 RBAC changes
- New permission: `Permission.DRAFT_POLICY_PACK` — narrower than the existing
  `MANAGE_POLICY_PACKS`, which becomes the approval/activation permission.
- New role: `Role.POLICY_ADMINISTRATOR` — holds `DRAFT_POLICY_PACK`, `READ_POLICY_RESULTS`.
- `Role.COMPLIANCE_OFFICER` (existing) gains `MANAGE_POLICY_PACKS` (approval authority) — consistent
  with its existing audit/compliance-oversight positioning.

### 4.9 AI considerations
- None — authoring and approval are explicitly human, deterministic workflow steps. No AI
  drafts or recommends rule content in this spec (a future "AI-suggested policy rule from
  historical override patterns" idea is noted only in §4.14, not built).

### 4.10 Integration requirements
- None beyond §13 (Notification System) for approval-request/decision notifications.

### 4.11 UX considerations
- A dedicated Policy Administration screen (distinct from the reviewer-facing Policy region) —
  diff view styled like a code-review diff (added/removed/modified rule rows), not a raw JSON dump.
- Maker-checker is enforced in the UI by disabling the approve action entirely (not just erroring)
  when `requestedByUserId === currentUser.id`.

### 4.12 Acceptance criteria
- Given a drafted pack, when submitted and approved by a different user, then it can be activated
  and immediately governs new evaluations.
- Given the same user who drafted a pack, when they attempt to approve it, then rejected with 403.
- Given a pack is rejected with a reason, then the drafter can see that reason and revise the draft.
- **Constitution check**: Principle VIII (approval decisions immutably audited with mandatory
  reason on rejection, mirroring Override) ✅; Principle IX (additive status values on the existing
  `PolicyPack`, not a rewritten model) ✅.

### 4.13 Risks
- **Workflow bypass**: a direct DB or admin-tool edit to `policy_packs.status` would bypass
  maker-checker entirely — mitigated by the DB constraint (§4.6) covering the *state machine*, but
  the approval *identity* check only exists in service logic; documented as a defense-in-depth gap
  to close with a DB trigger if this becomes a real threat model concern.
- **Draft/active drift**: a long-lived draft could go stale relative to the evidence/schema it will
  be evaluated against — mitigated by requiring re-validation of rule `appliesTo` predicates
  (§3.5) at activation time, not only at draft time.

### 4.14 Future extensibility
- The `PolicyRuleChange` diff log is the substrate for a future "policy change impact simulation"
  (replay historical findings against a draft pack before activating it) — explicitly not built
  here, noted as the natural next step once this workflow is live and trusted.

---

## 5. Borrower Identity Resolution

> **Wave 3 implementation correction (2026-07-12)**: this section originally specified
> probabilistic matching on "name, DOB, address, phone, email." Direct inspection of
> `mil.application.models.Party` at implementation time confirmed MIL stores **only**
> `displayName` — no DOB/address/phone/email column exists anywhere in the schema, consistent
> with Principle V (least-data: "full personal details live in the LOS and are never stored in
> MIL"). Implementing the original wording would have required either fabricating fields MIL
> deliberately never collects, or violating Principle V. The constitution is objectively correct
> here — it is the load-bearing security principle, not the spec's example list — so this section
> is corrected as follows and implemented against the corrected design, not the original wording:
> - **Deterministic matching** uses a new, additive, hashed identifier
>   (`Party.externalIdentifierHash` + `Party.identifierType`) — a SHA-256 hash of whatever real
>   external identifier the LOS supplied (customer ID, national ID, etc.), never the raw value,
>   mirroring the exact discipline already used by `identity.users.emailHash`. Score 0.98.
> - **Probabilistic matching** is restricted to normalized `displayName` similarity — the one
>   other real, already-stored signal. Score 0.65. No DOB/address/phone/email matching is
>   implemented, or ever will be under this section's current schema, without a separate,
>   explicit architectural decision to begin storing that PII in MIL.
> - The domain model is also renamed from the originally-specified `BorrowerMasterRecord`/
>   `BorrowerMasterRecordMember` to `BorrowerIdentity`/`BorrowerIdentityMember` (schema
>   `borrower_identity`, not `identity_resolution` — `identity_resolution` was reserved terminology
>   that never matched any other module's naming; `borrower_identity` matches the Python package
>   name `mil.borrower_identity` 1:1, avoiding a name/package mismatch). Sections 5.5–5.8 below
>   reflect the implemented design; 5.1–5.4 and 5.9–5.14's intent are unchanged.

### 5.1 Business objectives
- Recognize when the same real-world borrower appears across multiple applications (repeat
  customer, joint applications, previously-declined-now-reapplying) — today MIL treats every
  `Party` as fully independent, with no cross-application identity concept at all.
- Reduce duplicate document collection burden and give underwriters visibility into a borrower's
  history across applications, without creating a shadow credit-bureau-style profile beyond what
  MIL itself has legitimately collected.

### 5.2 Functional requirements
- **FR-BIR-001**: System MUST compute **match candidates** between a new `Party` and existing
  `Party` records using only data MIL already legitimately holds (`displayName`, and — once
  captured — normalized identity attributes explicitly entered during intake, never inferred from
  documents without evidence backing, per Principle II).
- **FR-BIR-002**: A match candidate MUST always be **advisory** — the system MUST NOT auto-merge
  identities. A human (Underwriter or Compliance) reviews and confirms or rejects a match
  (Principle I: AI assists, never decides — this applies to identity resolution exactly as it
  applies to findings).
- **FR-BIR-003**: A confirmed match creates a **Borrower Master Record** linking the matched
  `Party` rows; an application's own `Party` row is never deleted or rewritten — the master record
  is an additive linking layer (Principle IX: additive, non-destructive).
- **FR-BIR-004**: Underwriters MUST be able to see, from a Borrower Master Record, every
  application the borrower has been party to, with read access gated by the same ABAC rules as any
  cross-application query (extends `abac.py`'s existing `CrossApplicationDenialPolicy` — this
  module is the first legitimate, explicit exception to that policy, and must be implemented as an
  explicit allow-list capability, not a bypass).
- **FR-BIR-005**: A rejected match candidate MUST be recorded (not silently discarded) so the same
  low-quality match isn't repeatedly re-surfaced.

### 5.3 Non-functional requirements
- Match-candidate computation MUST run asynchronously (existing `JobQueue`), never inline on the
  intake request path — it's an enrichment, not a blocking step (Integration Model: enrich, don't
  block).
- False-positive matches are a real risk (wrongly linking two different people) — match scoring
  MUST be conservative, and every candidate MUST show its scoring basis to the human reviewer
  (Principle III: explainability applies to identity matches exactly as to findings — what, why,
  what evidence, how confident, what action).

### 5.4 User stories
- **US-BIR-1 (P1)**: As an Underwriter, when a new application's borrower closely matches an
  existing borrower, I see a match candidate with a clear confidence and basis, and I confirm or
  reject it. *Independent test*: two parties with identical normalized name + overlapping other
  attributes produce a candidate; dissimilar names do not.
- **US-BIR-2 (P2)**: As an Underwriter reviewing a confirmed-match borrower, I see their other
  applications' status (not full detail) to inform my review. *Independent test*: confirmed master
  record → cross-application summary visible; unconfirmed candidate → not visible.
- **US-BIR-3 (P3)**: As a Compliance Officer, I audit every identity-match decision (confirm/reject)
  with reviewer identity and reasoning, same rigor as a Finding override.

### 5.5 Domain model additions (as implemented — `mil.borrower_identity`)
- **`Party`** (existing, additively extended): `externalIdentifierHash` (nullable, SHA-256 of a
  real LOS-supplied identifier — never the raw value) and `identifierType` (nullable, free-string
  label, e.g. `"CUSTOMER_ID"`).
- **`IdentityMatchCandidate`** — `id`, `tenantId`, `partyId`, `candidatePartyId`, `matchScore`
  (`NUMERIC(4,3)`, real 0.98/0.65 per §5's implementation correction above), `matchBasis` (JSON,
  e.g. `{"exactIdentifierMatch": true, "identifierType": "CUSTOMER_ID"}` or
  `{"nameSimilarity": "exactNormalizedMatch"}`), `status` (`PENDING`/`CONFIRMED`/`REJECTED`),
  `reviewedByUserId`, `reason`, `reviewedAt`, `createdAt`.
- **`BorrowerIdentity`** — `id`, `tenantId`, `primaryDisplayName`, `createdAt`. Created the first
  time a candidate involving a party is confirmed.
- **`BorrowerIdentityMember`** — `id`, `borrowerIdentityId`, `partyId`, `applicationId`,
  `linkedByUserId`, `linkedAt`, `unlinkedAt` (nullable), `unlinkedByUserId` (nullable) — append-only;
  a correction unlinks by setting `unlinkedAt`, never by deleting the row (Principle IX).

### 5.6 Database schema changes (as implemented — migration `0019_borrower_identity.py`)
```sql
ALTER TABLE core.parties ADD COLUMN external_identifier_hash VARCHAR(128);
ALTER TABLE core.parties ADD COLUMN identifier_type VARCHAR(50);
CREATE INDEX ix_core_parties_external_identifier_hash ON core.parties (external_identifier_hash);

CREATE SCHEMA IF NOT EXISTS borrower_identity;

CREATE TABLE borrower_identity.identity_match_candidates (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    party_id UUID NOT NULL REFERENCES core.parties(id),
    candidate_party_id UUID NOT NULL REFERENCES core.parties(id),
    match_score NUMERIC(4,3) NOT NULL,
    match_basis JSON NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    reviewed_by_user_id UUID REFERENCES core.users(id),
    reason TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE borrower_identity.borrower_identities (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    primary_display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE borrower_identity.borrower_identity_members (
    id UUID PRIMARY KEY,
    borrower_identity_id UUID NOT NULL REFERENCES borrower_identity.borrower_identities(id),
    party_id UUID NOT NULL REFERENCES core.parties(id),
    application_id UUID NOT NULL REFERENCES core.applications(id),
    linked_by_user_id UUID NOT NULL REFERENCES core.users(id),
    linked_at TIMESTAMPTZ NOT NULL,
    unlinked_at TIMESTAMPTZ,
    unlinked_by_user_id UUID REFERENCES core.users(id)
);
```

### 5.7 API contracts (as implemented — `mil.api.v1.borrower_identity`)
- `POST /v1/parties/{party_id}/compute-match-candidates` → computes + persists `IdentityMatchCandidate[]`
  against every other party in the tenant (skips same-application pairs and existing PENDING pairs).
- `GET /v1/parties/{party_id}/match-candidates` → `IdentityMatchCandidate[]` suggested for a party.
- `GET /v1/parties/{party_id}/borrower-identity` → the party's resolved `BorrowerIdentity`, or `null`.
- `POST /v1/match-candidates/{id}/confirm` → creates/extends a `BorrowerIdentity`, links both
  parties' `BorrowerIdentityMember` rows.
- `POST /v1/match-candidates/{id}/reject` → `{reason?}`.
- `GET /v1/borrower-identities/{id}` → the resolved identity.
- `GET /v1/borrower-identities/{id}/members` → active party/application links.
- Schemas live in the existing `mil.api.v1.schemas` module alongside every other Wave 2/3 addition
  (no separate `identity-resolution.yaml` — this project's OpenAPI is generated from one FastAPI
  app, not hand-authored per-module files; every prior Wave 2 module followed the same convention).

### 5.8 RBAC changes (as implemented)
- New permission: `Permission.READ_CROSS_APPLICATION_IDENTITY` — the explicit, audited exception to
  the default cross-application denial; granted to `RELATIONSHIP_MANAGER` (read-only — RM sees the
  Borrower Profile but does not confirm merges), `UNDERWRITER`, `COMPLIANCE_OFFICER`, `RISK_ANALYST`.
- New permission: `Permission.CONFIRM_IDENTITY_MATCH` — granted to `UNDERWRITER`,
  `COMPLIANCE_OFFICER`, `RISK_ANALYST` (not `RELATIONSHIP_MANAGER` — confirming authority stays with
  the roles that already own review/compliance decisions elsewhere in the platform).

### 5.9 AI considerations
- Match scoring MAY use a deterministic similarity algorithm (e.g. normalized string distance) or a
  model-assisted scorer — either way, Principle XII applies: the scoring method and version MUST
  be attributed on `IdentityMatchCandidate` exactly as `modelVersion`/`promptVersion` are attributed
  on `Finding`. This module MUST NOT silently upgrade its matching algorithm without versioning the
  change.
- This is explicitly an **advisory AI/heuristic** capability — Principle I applies without
  exception: no automatic merge, ever.

### 5.10 Integration requirements
- None beyond internal cross-module queries — no external identity-verification service is
  integrated in this spec (a future KYC/identity-verification vendor integration is noted in
  §5.14, not built).

### 5.11 UX considerations
- Match candidates surface as a dismissible, non-blocking banner in the Overview region (reusing
  the `AiSignalBadge` vocabulary already established for AI-originated signals) — never a modal
  that blocks the review workflow.
- Confirmed cross-application history renders as a compact list (loan #, status, age) — deliberately
  terse, matching the "reference material, not decision" framing used for identifiers in the Phase
  11 UI redesign.

### 5.12 Acceptance criteria
- Given two parties with strongly matching normalized attributes, when intake completes, then a
  match candidate is generated asynchronously (not blocking intake) with a visible basis.
- Given a confirmed match, when an Underwriter views the master record, then they see both
  applications' status-level summary, gated by `READ_CROSS_APPLICATION_IDENTITY`.
- Given a rejected candidate, then it never resurfaces for the same party pair.
- **Constitution check**: Principle I (advisory only, human confirms) ✅; Principle II (matching
  basis is evidence-like: attributable, not opaque) ✅; Principle V (ABAC cross-application denial
  is extended via an explicit, audited allow-list, not bypassed) ✅.

### 5.13 Risks
- **False-positive identity linking** is the dominant risk of this entire module — two different
  people sharing a common name could be wrongly suggested as a match. Mitigation: conservative
  scoring thresholds, mandatory human confirmation, full basis transparency, and a reject path that
  suppresses re-suggestion.
- **Privacy/regulatory sensitivity**: cross-application identity linkage is exactly the kind of
  capability fair-lending and privacy regulators scrutinize — this module's audit trail (§5.5's
  `reviewedByUserId`/`reviewedAt`, always populated) is not optional hardening, it is the
  compliance requirement itself.

### 5.14 Future extensibility
- `matchBasis`'s open JSON shape allows adding new signal types (e.g. a future KYC-vendor-verified
  identity attribute) without a schema change. `BorrowerMasterRecord.status` already anticipates a
  future "split" correction workflow (an incorrectly merged record being un-merged) even though
  that workflow's UI is not built in this spec.

---

## 6. Cross-Application Intelligence

> **Wave 3 implementation correction (2026-07-12)**: this section originally specified a
> persisted, tenant-wide `CrossApplicationSignal` table computed by an async batch job across
> *all* applications' documents (duplicate-document detection scoped to the whole tenant corpus),
> with `confidence`/`recommendedAction` fields modeled after `Finding`. As implemented, this module
> is scoped to **one resolved `BorrowerIdentity`'s own linked applications** (§5's bounded set,
> typically a handful of applications per borrower) and computed **on demand**, not persisted or
> batch-scheduled — a real, defensible scope reduction, not a shortcut taken silently: a true
> tenant-wide duplicate-document index across every application's entire document corpus is a
> separate, larger undertaking (a dedicated indexed batch pipeline) that was not built in this
> wave and is not fabricated here. `confidence`/`recommendedAction` fields are dropped rather than
> populated with an invented value — a hash match either is or isn't a match (no probabilistic
> confidence exists to report), and "recommended action" would be inventing a directive this
> observation-only capability deliberately does not make (Principle I). What is implemented,
> honestly, per FR-XAI-001/002/003 (unchanged in intent): reused-document detection (real
> `Document.contentHash` collisions across the borrower's own applications), repeated
> `Finding.findingType` patterns, and a review-outcome summary — every observation cites its
> supporting application/document/finding ids (Principle III), computed by pure functions in
> `mil.cross_application_intelligence.service` and composed in `mil.api.deps`'s
> `CrossApplicationIntelligenceWorkspace`, gated by the existing `READ_CROSS_APPLICATION_IDENTITY`
> permission per FR-XAI-004 (unchanged — no new permission introduced). Sections 6.5–6.8 below
> reflect the implemented design.

### 6.1 Business objectives
- Surface patterns that are only visible *across* applications — e.g. the same document
  fingerprint (content hash) appearing on two unrelated applications, or a borrower's confirmed
  master record (§5) carrying a Finding pattern relevant to a new application — without ever
  turning this into an automated cross-application decision (Principle I applies at the portfolio
  level exactly as it does at the single-application level).
- Give Risk/Compliance a portfolio-level signal surface that today doesn't exist at all (the MVP
  scope was deliberately single-application; this module is the first genuinely cross-application
  capability, building on §5's identity resolution as its prerequisite).

### 6.2 Functional requirements
- **FR-XAI-001**: System MUST detect duplicate documents (identical `contentHash`) across
  *different* applications, not just within one application (the MVP's Phase 4.5 duplicate
  detection was explicitly single-application-scoped) — surfaced as a **Cross-Application Signal**,
  advisory only.
- **FR-XAI-002**: System MUST surface, for a confirmed Borrower Master Record (§5), a summary of
  Finding patterns across that borrower's applications (e.g. "2 of 3 applications had an income-
  verification finding") — derived, read-only, never a new finding type invented client-side.
- **FR-XAI-003**: Every Cross-Application Signal MUST be explainable per Principle III (what, why,
  evidence, confidence, recommended action) exactly like a Finding — this module does not get a
  lighter explainability bar just because it's cross-application.
- **FR-XAI-004**: Cross-Application Signals MUST respect the same ABAC allow-list introduced in §5
  — no signal computation may leak data to a user who lacks `READ_CROSS_APPLICATION_IDENTITY`.

### 6.3 Non-functional requirements
- Signal computation MUST be a background/batch process (existing `JobQueue`), triggered on new
  evidence/finding creation, never a synchronous cross-application join on the request path.
- MUST scale sub-linearly with portfolio size for the duplicate-document check — a hash-indexed
  lookup (`contentHash` index across `core.documents`, tenant-scoped), not a full cross-join.

### 6.4 User stories
- **US-XAI-1 (P1)**: As a Risk Analyst, I see a flag that a document on this application is
  byte-identical to a document on a different, unrelated application — a real, explainable
  duplicate-fraud signal. *Independent test*: two applications, same file hash → signal generated;
  different hashes → no signal.
- **US-XAI-2 (P2)**: As an Underwriter reviewing a confirmed-repeat borrower, I see "this borrower
  had 2 income-verification findings on a prior application" as context, not as a pre-judgment.
  *Independent test*: master record with prior findings → summary populated; new borrower → empty,
  honest "no prior history" state, never a fabricated placeholder.

### 6.5 Domain model additions (as implemented — `mil.cross_application_intelligence`)
- **`CrossApplicationObservation`** — a plain, non-persisted dataclass (not an ORM model — this
  module has no database table): `kind` (`REUSED_DOCUMENT` | `REPEATED_FINDING_TYPE` |
  `REVIEW_OUTCOME_SUMMARY`, an open string, not a closed DB enum), `description` (plain-language
  explanation of why the observation exists), `applicationIds`, `documentIds`, `findingIds` — the
  exact evidence a reviewer can click through, computed fresh on every request from real
  `Document.contentHash`/`Finding.findingType`/`Finding.lifecycleState` data.

### 6.6 Database schema changes (as implemented)
None. This module introduces no new table and no new column — it is a pure, read-only composition
over data `mil.document` and `mil.finding` already persist, scoped to one `BorrowerIdentity`'s
already-linked applications (§5). `idx_core_parties_external_identifier_hash` (added in §5's
migration) is the only index this wave introduces anywhere in this area of the schema.

### 6.7 API contracts (as implemented)
- `GET /v1/borrower-identities/{identity_id}/cross-application-signals` →
  `CrossApplicationObservation[]`, gated by `READ_CROSS_APPLICATION_IDENTITY`. Scoped to a resolved
  `BorrowerIdentity` (§5's bounded set of linked applications), not a single application — the
  correction above explains why this is keyed by identity rather than by application.
- Schema lives in the existing `mil.api.v1.schemas` module (no separate
  `cross-application-intelligence.yaml` — same convention as every other Wave 2/3 module, §5.7).

### 6.8 RBAC changes
- Reuses `Permission.READ_CROSS_APPLICATION_IDENTITY` from §5 — no new permission introduced,
  deliberately, since this module's access boundary is identical to identity resolution's.

### 6.9 AI considerations
- Duplicate-document detection is deterministic (hash comparison) — no AI/ML involved, explicitly
  noted so this module isn't mistaken for a model-based capability where none exists.
- Finding-pattern summarization (FR-XAI-002) is a simple aggregation (count/group), not an
  LLM-generated narrative — kept honest and reproducible per Principle XII; a future
  Copilot-generated narrative summary of cross-application patterns is a natural extension (§6.14),
  not built here.

### 6.10 Integration requirements
- None beyond internal modules (§5 Identity Resolution is a hard prerequisite for FR-XAI-002; §14's
  job queue for async computation).

### 6.11 UX considerations
- Signals render in the Overview region as a distinct, clearly-labeled "Cross-application signal"
  card — visually related to but distinguishable from single-application Findings, so a reviewer
  never confuses portfolio-level context with this application's own evidence.

### 6.12 Acceptance criteria
- Given identical document hashes across two applications, when the async job runs, then a
  `DUPLICATE_DOCUMENT` signal is created for both applications, each pointing at the other.
- Given a user without cross-application read permission, then signals are not returned (403 or
  filtered, not merely hidden client-side).
- **Constitution check**: Principle III (five explainability fields enforced structurally) ✅;
  Principle I (advisory signal, recommended action, never an automatic flag/block/decision) ✅.

### 6.13 Risks
- **Portfolio-scale compute growth**: naive pairwise comparison for finding-pattern signals doesn't
  scale — must be implemented as an indexed/aggregated query per borrower master record, not an
  all-pairs scan; explicitly called out so a naive implementation isn't shipped by mistake.
- **Signal fatigue**: if duplicate-document detection is too permissive (e.g. flags common
  boilerplate pages), reviewers will learn to ignore signals — mitigated by scoping detection to
  meaningfully-sized, borrower-submitted document types, not template pages.

### 6.14 Future extensibility
- `CrossApplicationSignal.signalType` is an open enum by design (string, not a closed DB enum) —
  future signal types (e.g. velocity/fraud-ring detection) are additive rows, not schema changes.
  A future Copilot-narrated cross-application summary would consume this table as its grounding
  source, consistent with how Copilot already grounds against Evidence/Findings (§8).

---

## 7. Universal Search

### 7.1 Business objectives
- Provide one search experience across applications, documents, and (later) borrowers/findings —
  extending, not replacing, the `search` query param already implemented server-side in the MVP
  (`ApplicationRepository.get_for_tenant`'s `ILIKE`/`or_()` clause across `los_reference`,
  `loan_number`, application `id`, and party `display_name`) and already wired into the Command
  Palette and Application Queue.
- Extend search beyond applications to documents (by filename/type) and, where §5/§6 apply, to
  borrower master records — while respecting the MVP's own explicit, correct constraint that MIL
  never stores full PII (email/phone/SSN) and therefore can never search on it (confirmed during
  the MVP's Phase 12 audit — this spec does not attempt to reopen that boundary).

### 7.2 Functional requirements
- **FR-SRCH-001**: System MUST extend the existing `search` param's scope to also match document
  `filename`/`documentType` for the authenticated user's accessible applications.
- **FR-SRCH-002**: System MUST provide a unified `GET /v1/search?q=` endpoint returning typed
  results (`application`, `document`, `borrower` result kinds) rather than three separate endpoints
  the frontend has to fan out to — one query, one latency budget.
- **FR-SRCH-003**: Search results MUST be scoped by the requesting user's RBAC/ABAC exactly as list
  endpoints already are — a search index MUST NOT become a side channel that leaks data a direct
  query would have blocked.
- **FR-SRCH-004**: A search query and its result count MUST be logged (not full results, to avoid
  duplicating sensitive data into a log store) for the operational visibility this module's own
  usage needs (§10/§11).

### 7.3 Non-functional requirements
- p95 latency target: < 300ms, matching every other interactive endpoint — search must not become
  the platform's slow path.
- At current/anticipated scale (§ per `specs/001-mil-platform-spec/plan.md`'s 500–50,000
  applications/month target), PostgreSQL full-text search (`tsvector`/`GIN` index) is sufficient —
  this module explicitly does NOT introduce a dedicated search engine (Elasticsearch/OpenSearch) at
  this scale; that is named as a future extensibility path (§7.14), not built now, per Principle IX
  (prefer incremental evolution over infrastructure additions not yet justified by scale).

### 7.4 User stories
- **US-SRCH-1 (P1)**: As any reviewer, I search "bank-statement" and see matching documents across
  my accessible applications, not just application-level matches. *Independent test*: filename
  match surfaces the owning application as a result.
- **US-SRCH-2 (P2)**: As an Underwriter, I search a borrower's name and, where a confirmed master
  record exists (§5), see them as one grouped result rather than N separate application hits.

### 7.5 Domain model additions
- No new persisted entities. A `SearchQueryLog` (new, lightweight, for §7.2's FR-SRCH-004) is the
  only addition:
- **`SearchQueryLog`** — `id`, `userId`, `queryText` (the search string itself — not sensitive
  beyond what a URL query param already exposes in access logs), `resultCount`, `searchedAt`.

### 7.6 Database schema changes
```sql
CREATE TABLE core.search_query_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES identity.users(id),
    query_text TEXT NOT NULL,
    result_count INT NOT NULL,
    searched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Full-text search support, additive indexes only
ALTER TABLE core.documents ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(filename,'') || ' ' || coalesce(document_type,''))) STORED;
CREATE INDEX idx_documents_search ON core.documents USING GIN (search_vector);
```

### 7.7 API contracts
- `GET /v1/search?q=&kinds=application,document,borrower&page=&pageSize=` →
  `{results: SearchResult[], total}` where `SearchResult` is a discriminated union
  `{kind: 'application', application: ApplicationListItem} | {kind: 'document', document: ...,
  applicationId} | {kind: 'borrower', masterRecord: ...}`.
- Additive `documentSearch` support folded into the existing `applications.yaml`'s `search` param
  semantics is insufficient for cross-entity results — hence the new unified endpoint, not a third
  bolt-on param.
- New OpenAPI file: `search.yaml`.

### 7.8 RBAC changes
- None new — `GET /v1/search` enforces the same per-result-kind permission checks as the underlying
  resource's own list endpoint (`READ_APPLICATION`, `READ_DOCUMENT`,
  `READ_CROSS_APPLICATION_IDENTITY` for borrower-kind results).

### 7.9 AI considerations
- None — this is deliberately classical full-text search, not semantic/vector search, at this
  scale and this data sensitivity level. A semantic-search upgrade is explicitly deferred (§7.14).

### 7.10 Integration requirements
- None external.

### 7.11 UX considerations
- One search entry point (Command Palette `⌘K`, already built) now returns grouped, typed results
  instead of application-only results — extends the existing UI, no new search surface introduced.

### 7.12 Acceptance criteria
- Given a document filename match, when searched, then the result includes the owning
  application's context (so a click lands the user in the right place, not a dangling document id).
- Given a user without document read access to a given application, then that application's
  documents never appear in their search results regardless of filename match.
- **Constitution check**: Principle V (search never bypasses RBAC/ABAC) ✅; Principle IX
  (PostgreSQL FTS chosen over new infrastructure until scale demands otherwise) ✅.

### 7.13 Risks
- **Search-as-a-leak-vector**: the single largest risk category for any search feature — mitigated
  structurally by requiring every result kind to re-use its underlying resource's existing
  permission check, not a separate, potentially-drifting search-specific ACL.
- **Result relevance at low data volume**: with a small per-tenant document corpus, naive `ILIKE`/
  `tsvector` ranking may feel imprecise — acceptable at this module's target scale; revisit only if
  real usage data shows a problem (Principle IX: don't over-engineer for problems not yet observed).

### 7.14 Future extensibility
- Explicitly deferred, not built: a dedicated search engine (Elasticsearch/OpenSearch) for
  relevance ranking and scale beyond PostgreSQL FTS's comfortable range; semantic/embedding-based
  search (would need its own AI-considerations review, distinct from this module's deliberately
  non-AI scope); search across Findings/Evidence content (deferred pending a data-sensitivity
  review — Finding `why`/`what` text may be more sensitive to index broadly than a filename).

---

## 8. AI Case Copilot

### 8.1 Business objectives
- **Corrected ground truth** (verified directly against `src/main.py` during Wave 1 planning, see
  §0's updated table): the backend for this module is **already fully built and live** — models,
  grounding service, adapters, citation system, prompt scaffolding, a real API
  (`src/mil/api/v1/copilot.py`), an OpenAPI contract, and router registration in `src/main.py` all
  exist today. This module's entire remaining scope is the **frontend** — there is no reviewer-
  facing UI anywhere in `frontend/src` that calls it. Nothing below in §8.2/§8.5/§8.6/§8.7 requires
  new backend work; it is retained as a description of the existing contract this module's frontend
  consumes, not a build list.
- Give reviewers a grounded, citation-backed Q&A surface over a single application's own data
  (evidence, findings, policy results, review history) — never a general-purpose chatbot, never a
  cross-application or open-web-connected assistant (Principle V: AI context isolation).

### 8.2 Functional requirements
- **FR-COP-001**: System MUST expose the existing `CopilotService` via `POST
  /v1/applications/{id}/copilot/query` accepting a natural-language question and returning a
  grounded `CopilotResponse` with citations resolved through the existing `citations.py` machinery.
- **FR-COP-002**: Every Copilot answer MUST cite its sources using the existing `Citation` model —
  an answer with no resolvable citation MUST be refused or explicitly caveated, never presented as
  an unsupported assertion (this is the existing grounding discipline in `service.py`; this module
  does not relax it to ship faster).
- **FR-COP-003**: Copilot's context MUST be scoped to exactly one application (the existing
  `ApplicationReaderAdapter`/`DocumentReaderAdapter`/etc. are already application-scoped) — this
  module MUST NOT widen that scope to satisfy §6's cross-application use case; a cross-application
  Copilot is explicitly out of scope (§8.14).
- **FR-COP-004**: A `CopilotSession` MUST persist query/response history per application
  (`CopilotSession`/`CopilotQuery`/`CopilotResponse` already model this) so a reviewer's prior
  questions remain visible on return to the application.
- **FR-COP-005**: Copilot MUST NOT be able to trigger any mutation (Verify/Override/Escalate,
  policy activation, assignment change) — read/query only, enforced by the adapter set having no
  writer adapters at all (already true of `ports.py`'s Protocol definitions — this module must not
  add one).

### 8.3 Non-functional requirements
- Query latency: acceptable to be slower than CRUD endpoints (LLM round-trip), but MUST show a
  loading/streaming state, never a silent multi-second hang (reuses `LoadingState`/`SkeletonState`
  design-system components already built).
- MUST log every query for auditability (Principle VIII: AI recommendations reproducible and
  logged) — `CopilotQuery`/`CopilotResponse` already provide the persistence; this module ensures
  the API layer doesn't bypass it (e.g. no fire-and-forget query path that skips persistence).

### 8.4 User stories
- **US-COP-1 (P1)**: As an Underwriter, I ask "what evidence supports the income finding?" and
  receive an answer citing the specific Evidence items and their source documents/pages.
  *Independent test*: a query about a known finding returns citations resolving to real evidence
  ids on that application.
- **US-COP-2 (P2)**: As an Underwriter, I ask a question with no supporting data in this
  application, and Copilot honestly says it cannot find grounding, rather than fabricating an
  answer. *Independent test*: query against an evidence-free application → refusal/caveat response,
  not a hallucinated citation.
- **US-COP-3 (P3)**: As an Underwriter, I return to an application days later and see my previous
  Copilot conversation still there.

### 8.5 Domain model additions
- None — `CopilotSession`, `CopilotQuery`, `CopilotResponse` already exist
  (`src/mil/copilot/models.py`). This module is API/frontend work over an existing, tested domain
  layer.

### 8.6 Database schema changes
- None required — the existing `copilot` schema/tables are assumed already migrated as part of the
  MVP build (verify at implementation time; if the migration was never actually run in production,
  that is a one-line gap to close, not a schema design task).

### 8.7 API contracts
- `POST /v1/applications/{id}/copilot/query` → `{question}` → `CopilotResponse` (with citations).
- `GET /v1/applications/{id}/copilot/sessions` → `CopilotSession[]` (history).
- New OpenAPI file: `copilot.yaml`, built directly from the existing `CopilotService`/`ports.py`
  types rather than invented independently — the contract should mirror the domain layer that
  already exists, not diverge from it.

### 8.8 RBAC changes
- `Permission.QUERY_COPILOT` **already exists** in `security.py`, currently unused by any route —
  this module is its first real consumer. No new permission required.

### 8.9 AI considerations
- This module *is* the AI consideration — every principle applies directly: Principle I (Copilot
  answers questions, never recommends a lending decision — the existing prompt scaffolding in
  `prompts.py` must be audited at implementation time to confirm this framing is enforced in the
  actual prompt text, not just the surrounding code); Principle II/III (citations = evidence-first,
  explainability); Principle XII (model/prompt version attribution on every `CopilotResponse`,
  mirroring `Finding`'s attribution fields — confirm `CopilotResponse`'s existing schema already
  carries this, extend additively if it doesn't).

### 8.10 Integration requirements
- Uses the same LLM provider integration already established for Evidence/Finding generation
  (`src/mil/providers/inference/gemini_inference.py`) — no new AI vendor integration.

### 8.11 UX considerations
- A persistent, collapsible Copilot panel inside the Application Workspace (natural extension of
  the `DocumentInspector` split-panel pattern established in the MVP's Phase 8) — not a separate
  route, so context (which application) is never ambiguous.
- Citations render as clickable chips reusing the existing `EvidenceChip`/`DocumentJumpTarget`
  mechanism — a Copilot citation click lands exactly where a Finding's evidence chip click does,
  same navigation primitive, not a second one.

### 8.12 Acceptance criteria
- Given a question with real grounding data, when queried, then the response includes at least one
  citation resolving to a real Evidence/Finding/Document/PolicyResult/Review/Audit record on that
  application.
- Given a question outside the application's data, then the response honestly states it cannot
  answer, never fabricates.
- Given a user without `QUERY_COPILOT`, then 403.
- **Constitution check**: Principle I (advisory Q&A only, no mutation capability) ✅; Principle II/
  III (mandatory citation, explainable) ✅; Principle V (single-application context isolation,
  reusing existing scoped adapters) ✅.

### 8.13 Risks
- **Prompt-scaffolding drift from constitution intent**: since `prompts.py` already exists but has
  never been exercised through a real UI, its actual behavior under real reviewer phrasing is
  unverified — this module's rollout MUST include a real-usage QA pass (not just unit tests)
  before general availability, mirroring the MVP's own "verify against the real backend/Gemini, not
  just mocks" discipline from its RC1 stabilization pass.
- **Latency/cost at scale**: every query is a real LLM call — needs rate-limiting per user/
  application to prevent runaway cost, not specified in the existing backend layer; add at the API
  layer this module introduces.

### 8.14 Future extensibility
- Cross-application Copilot (querying across a borrower's full history, once §5/§6 exist) is
  explicitly named as a future capability, not built here — the existing single-application scoping
  is a deliberate, principled boundary (Principle V), not an oversight to "just extend later"
  casually; widening it requires its own security/AI-considerations review.

---

## 9. Collaboration

**Correction found during Wave 1 implementation** (verified directly against `src/mil/review/
models.py`/migration 0008 before writing any code): `ReviewComment.review_session_id` FKs to
`review.review_sessions`, and a `ReviewSession` is unique per **Finding** (`finding_id` is unique —
one session per Finding, created once when policy evaluation completes). There is no
`application_id` column on `ReviewComment` and no code path that would let one exist independently
of a Finding's own review. This means real Collaboration is **scoped to one Finding's review**, not
a general application-wide thread as originally drafted below (FR-COLLAB-001/003 assumed a
`POST /v1/applications/{id}/comments` application-level thread). This is judged the objectively
correct scope, not merely the path of least resistance: every decision action in this platform
(Verify/Override/Escalate) already operates at Finding granularity, and Findings — not the
application as an undifferentiated whole — are the platform's actual unit of review. Implemented as
`POST /v1/findings/{id}/comments` instead; a comment can only be posted once a Review Session exists
for that Finding (a real 404 otherwise, not a silently-created one), matching the Finding's actual
lifecycle. FR-COLLAB-002 (mentions)/004 (edit window)/005 (delete) are implemented as designed,
scoped to this corrected unit.

### 9.1 Business objectives
- Give reviewers, RMs, and Compliance a way to discuss a specific application/finding without
  leaving MIL for email/chat — using the domain layer that **already exists**
  (`src/mil/review/`'s `ReviewComment` model and `add_comment()` service method, confirmed to have
  zero API route today, per §0's ground-truth table).
- Distinguish this from Timeline/Audit (Principle VIII's immutable system-of-record) exactly as the
  MVP's Phase 9 already framed the Timeline-vs-Audit distinction: comments are human discussion,
  not a compliance record substitute — comments MAY reference a Finding/Evidence/Document but never
  replace the mandatory Override/Escalate reason fields, which remain in the Review domain
  untouched.

### 9.2 Functional requirements
- **FR-COLLAB-001**: System MUST expose the existing `add_comment()` capability via
  `POST /v1/applications/{id}/comments` — comment body, optional reference to a Finding/Document/
  Evidence id (for a scoped, contextual comment).
- **FR-COLLAB-002**: Comments MUST support **@mentions** of other users with access to the
  application, triggering a Notification (§13) — mentions are resolved against real users with
  real access, never an arbitrary free-text name.
- **FR-COLLAB-003**: A comment thread MUST be visible to everyone with read access to the
  application (not a private DM system) — Collaboration is about shared case discussion, not
  general messaging (general messaging is explicitly out of scope, §9.14).
- **FR-COLLAB-004**: Comments MUST be editable by their author within a short window (e.g. 5
  minutes) and then immutable — edits after the window require a visible "edited" marker, comments
  are never silently rewritten (Principle VIII's spirit — informal discussion doesn't need full
  audit-event rigor, but honesty about edits still applies).
- **FR-COLLAB-005**: A comment MUST NOT be deletable by its author once another user has replied to
  or reacted to it — soft-delete only (`deletedAt`), preserving thread continuity.

### 9.3 Non-functional requirements
- Comment read/write endpoints meet the same p95 < 300ms target as other interactive endpoints.
- Mention resolution MUST perform a real permission check (can this mentioned user actually see
  this application) before creating a Notification — never notify a user about an application they
  can't access, which would itself be a data leak.

### 9.4 User stories
- **US-COLLAB-1 (P1)**: As an Underwriter, I leave a comment on a specific Finding asking a
  Compliance colleague to weigh in, @mentioning them. *Independent test*: comment created, mention
  resolved to a real user, notification queued.
- **US-COLLAB-2 (P2)**: As an RM, I see the Underwriter's comment thread on an application I
  originated and reply with context about the borrower. *Independent test*: RM with `READ_
  APPLICATION` can read and post; a user without application access cannot.
- **US-COLLAB-3 (P3)**: As a comment author, I fix a typo within 2 minutes of posting; after 10
  minutes I can no longer edit, only see my own comment as posted.

### 9.5 Domain model additions
- None new — `ReviewComment` already exists (`src/mil/review/models.py`, confirmed during the MVP's
  Phase 6/8 research). Additions are additive columns:
- **`ReviewComment.mentionedUserIds`** (new column, array of UUID) — if not already present.
- **`ReviewComment.editedAt`** (new column, nullable) — FR-COLLAB-004's "edited" marker.
- **`ReviewComment.deletedAt`** (new column, nullable) — FR-COLLAB-005's soft delete.

### 9.6 Database schema changes
```sql
ALTER TABLE review.review_comments
    ADD COLUMN IF NOT EXISTS mentioned_user_ids UUID[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
CREATE INDEX idx_review_comments_application ON review.review_comments(application_id);
```
(Exact base-table shape to be confirmed against the existing `review/models.py` at implementation
time — this spec assumes an `application_id`-scoped table already exists per the ground-truth
table in §0; if the existing model differs, these are the additive deltas required, not a
replacement schema.)

### 9.7 API contracts
- `POST /v1/applications/{id}/comments` → `{body, referenceType?, referenceId?, mentionedUserIds?}`.
- `GET /v1/applications/{id}/comments` → `ReviewComment[]`.
- `PATCH /v1/comments/{id}` → author-only, within edit window.
- `DELETE /v1/comments/{id}` → soft delete, blocked if replies/reactions exist.
- New OpenAPI file: `collaboration.yaml`.

### 9.8 RBAC changes
- New permission: `Permission.COMMENT_ON_APPLICATION` — granted to every role that already holds
  `READ_APPLICATION` (comments are as broadly readable/writable as the application itself, per
  FR-COLLAB-003) except `SERVICE_ACCOUNT`.

### 9.9 AI considerations
- None in this module directly. Explicitly note the natural adjacency to §8 (Copilot could
  summarize a long comment thread) — not built here, named in §9.14.

### 9.10 Integration requirements
- Depends on §13 (Notification System) for mention delivery — this module creates the notification
  event; §13 owns delivery channels.

### 9.11 UX considerations
- Comment thread renders inside the Application Workspace as a collapsible panel (same pattern
  family as Evidence/Document disclosures) — scoped comments (attached to a specific Finding)
  render inline near that Finding, reusing the disclosure pattern from the MVP's Phase 6
  Review-history disclosure, not a new UI primitive.
- @mention autocomplete is scoped to users with real access to the application — never a global
  user-directory search, both for correctness (can't mention someone who can't see the thread) and
  for privacy (doesn't expose the full user directory to every reviewer).

### 9.12 Acceptance criteria
- Given a comment mentioning a user without application access, then mention resolution rejects
  that mention (or the whole request, per implementation choice) rather than silently notifying
  someone who then can't open the link.
- Given a comment with a reply, when the author attempts to delete it, then deletion is blocked.
- **Constitution check**: Principle VIII (comments are discussion, not a substitute for the
  mandatory Override/Escalate audit fields, which are unchanged) ✅; Principle V (mention
  resolution is permission-checked, not an open directory) ✅.

### 9.13 Risks
- **Scope creep into a full chat product**: this module must stay "comments on a case," not grow
  into DMs/channels/presence — explicitly out of scope (§9.14).
- **Notification storm**: heavy @mention use on a busy application could flood a user with
  notifications — §13 owns batching/digest behavior; this module just emits the event honestly.

### 9.14 Future extensibility
- Out of scope, explicitly: private messaging, emoji reactions, rich-text/attachments in comments
  (plain text + mentions only, for now), AI-summarized comment threads (a natural Copilot extension
  once §8 ships).

---

## 10. Operational Dashboard

> **Wave 3 implementation correction (2026-07-12)**: this section originally specified a
> persistent `operational.metric_snapshots` time-series table plus a scheduled-refresh
> `operational.application_funnel` materialized view. As implemented, both the queue-depth and
> funnel views are computed **on demand** by aggregated SQL queries
> (`WorkflowRepository.count_by_type_and_status`, `ApplicationRepository.get_status_funnel`) —
> real, indexed, cheap aggregates at this platform's actual data volumes, not a fabricated
> shortcut: a scheduled materialized-view refresh job is real additional infrastructure (a cron/
> worker, staleness tracking, a `last_refreshed_at` signal) that was not built this wave. No
> `metric_snapshots` time-series table is introduced either — nothing here invents a history that
> doesn't exist; the existing in-process `GET /v1/metrics` (`mil.api.v1.ops`, unchanged) remains
> the platform's only metrics surface beyond this module's two new aggregates. "Poison jobs"
> (FR-OPS-002) are implemented as a real, honest proxy — `WorkflowStep` rows with
> `status == FAILED and retry_count >= max_retries` — not the fuller redelivery/visibility-timeout
> mechanism the RC1 checklist separately documented as unbuilt; a step abandoned mid-flight by a
> crashed worker (stuck `IN_PROGRESS` forever) is **not** detected by this query, which is an
> honest limitation, not a fabricated capability. Sections 10.5–10.7 below reflect the implemented
> design.

### 10.1 Business objectives
- Fulfil Constitution Principle X (Operational Excellence) — the platform must provide bottleneck
  identification and workload visibility, not just per-case tooling. Today `src/mil/operational/`
  is an empty package stub; this module is genuinely greenfield.
- Give Operations Managers real-time visibility into queue depth, processing pipeline health
  (including the two known, documented gaps from the MVP's RC1 pass: the job queue's poison-job
  risk and lack of redelivery on worker crash), and LOS sync health (§2).

### 10.2 Functional requirements
- **FR-OPS-001**: System MUST provide a live view of job queue depth per job type (Document
  ingestion, Finding generation, Policy evaluation — the existing `WorkflowRun`/`WorkflowStep`
  step names) and per-status (pending/in-progress/failed), sourced from the existing job queue
  infrastructure, not a new tracking mechanism duplicating it.
- **FR-OPS-002**: System MUST surface the LOS Sync Failure Queue (§2.7) as one operational widget
  among others, not a separate screen.
  Report unrecoverable/poison jobs (the MVP's RC1-documented risk) as a distinct, alertable
  category — this module is where that known gap becomes *visible* operationally, even before a
  future phase fixes the underlying redelivery mechanism.
- **FR-OPS-003**: System MUST show application-lifecycle funnel metrics (count per
  `ApplicationStatus`, average time-in-status) computed from existing data, no new tracking table
  required for the funnel itself.
- **FR-OPS-004**: Dashboard data freshness MUST be at most 5 minutes stale (matches the target
  already set in `specs/001-mil-platform-spec/plan.md`'s Technical Context).

### 10.3 Non-functional requirements
- Dashboard queries MUST run against read-optimized aggregates (materialized views or a
  scheduled-refresh summary table), never ad hoc heavy aggregation on every dashboard load — this
  is the same N+1/aggregate-cost discipline the MVP's own field-availability audit already
  established for the Application Queue.
- Must not add write load to the hot path (ingestion/finding/policy pipelines) — metrics are read
  from existing tables via a separate, scheduled aggregation job.

### 10.4 User stories
- **US-OPS-1 (P1)**: As an Operations Manager, I see current queue depth per job type and identify
  that Policy evaluation jobs are backing up. *Independent test*: seeded queue depth reflected
  correctly, refreshed within the freshness target.
- **US-OPS-2 (P1)**: As an Operations Manager, I see a poison-job alert distinct from a normal
  transient failure, so I know to investigate rather than wait for an automatic retry that will
  never come (per the documented gap). *Independent test*: a job exceeding the retry ceiling is
  classified and surfaced distinctly from a normally-retrying job.
- **US-OPS-3 (P2)**: As Operations, I see the application funnel (how many in each status, average
  dwell time) to spot where applications are getting stuck.

### 10.5 Domain model additions (as implemented)
None persisted — this module introduces no new ORM model or table. `QueueDepthRow`/
`ApplicationFunnelRow` (`mil.api.deps`) are plain, non-persisted dataclasses shaping the output of
the two aggregate repository queries; "poison jobs" are the existing `WorkflowStep` rows, filtered,
not a new entity.

### 10.6 Database schema changes (as implemented)
None. No new schema, table, index, or materialized view. Both aggregates run directly against the
existing `orchestrator.workflow_runs`/`orchestrator.workflow_steps` and `core.applications` tables.

### 10.7 API contracts (as implemented)
- `GET /v1/operational/queue-depth` → per-workflow-type/status counts
  (`WorkflowRepository.count_by_type_and_status`).
- `GET /v1/operational/poison-jobs` → `WorkflowStep` rows exceeding their retry ceiling
  (`WorkflowRepository.get_poison_steps`).
- `GET /v1/operational/funnel` → per-status count + average seconds since last update
  (`ApplicationRepository.get_status_funnel`).
- Schemas live in the existing `mil.api.v1.schemas` module (no separate `operational.yaml` — same
  convention as every other Wave 2/3 module).

### 10.8 RBAC changes
- `Permission.READ_OPERATIONAL` **already exists** in `security.py`, currently unused by any
  route — this module is its first consumer. `Role.OPERATIONS_MANAGER` (already exists) already
  aligns to this permission by name.

### 10.9 AI considerations
- None — this module is observability/metrics, deliberately non-AI.

### 10.10 Integration requirements
- Reads from the existing `JobQueue`/`WorkflowRun` infrastructure and §2's `LOSSyncEvent` table —
  no new external integration.

### 10.11 UX considerations
- Reuses the Phase 11 design language (stat-row, hairline-divided panels) established for the
  Underwriter Home Dashboard — this is the Operations-role equivalent of that dashboard, not a
  visually distinct product.
- Poison-job alerts get a visually distinct (not just differently-labeled) treatment — this is a
  "needs immediate human attention" signal, matching the urgency-first hierarchy principle already
  established in the Phase 11 Dashboard redesign.

### 10.12 Acceptance criteria
- Given a job that has exceeded the retry ceiling, when viewed on the dashboard, then it is
  classified as a poison job, distinct from a normally-retrying job.
- Given the funnel view, when an application changes status, then the funnel reflects it within
  the 5-minute freshness target (via scheduled materialized-view refresh).
- **Constitution check**: Principle X (Operational Excellence: queue/funnel/failure visibility) ✅;
  no principle requires re-check for AI/decision-authority since this module is non-AI.

### 10.13 Risks
- **Metric explosion**: an unstructured `metricKey` namespace could sprawl uncontrolled — mitigated
  by a documented, reviewed naming convention (`domain.metric.dimension`), not enforced by a DB
  constraint (a soft governance control, acceptable at this scale).
- **Materialized view staleness during incident**: if the refresh job itself fails during an
  incident, the dashboard could show stale data exactly when it matters most — mitigate by
  surfacing the view's own `last_refreshed_at` timestamp on the dashboard, honestly, rather than
  presenting stale data as current.

### 10.14 Future extensibility
- `OperationalMetricSnapshot`'s generic shape is deliberately the seed for §11's Business Analytics
  — that module builds richer, longer-retention analytics on top of the same time-series
  substrate, not a competing one.

---

## 11. Business Analytics

> **Wave 3 implementation correction (2026-07-12)**: this section originally specified
> `ReportDefinition`/`ReportRun` scheduled-report infrastructure plus a
> `operational.finding_outcome_distribution` materialized view, with volume-trend reporting over a
> 12-month historical window. As implemented, this module is a single **current-state snapshot**
> endpoint (`GET /v1/analytics/snapshot`) — application counts by status, finding lifecycle-state
> distribution, policy outcome distribution by version, document/evidence counts, and average
> review duration — computed on demand from existing repositories, exactly like §10's Operational
> Dashboard correction. No `ReportDefinition`/`ReportRun`/scheduling/email-delivery infrastructure
> is built (FR-BA-003 is out of scope this wave), and **no historical volume trend is reported at
> all** (FR-BA-001's "per period" framing is not implemented) — this platform has no time-series
> metrics substrate (confirmed in §10's correction note: no `metric_snapshots` table exists), so a
> "12 months of trend data" claim would be fabricated. This is the honest disclosure the user's own
> Wave 3 instructions required ("where trend data is unavailable, display an honest disclosure; do
> not invent historical metrics") rather than a silently-dropped requirement. RM productivity
> (per-owner `Assignment` counts) is also not included: `Assignment` has no `tenant_id` column, so a
> tenant-scoped breakdown would require a join through `MortgageApplication` not built this wave —
> disclosed as a real gap, not fabricated. FR-BA-002's finding-outcome/policy-calibration reporting
> is genuinely implemented — real data, correctly grounded (see §11.5–§11.8's implementation notes
> below). FR-BA-004 (analytics is never the compliance record) is upheld by construction: this
> endpoint has no write path and the existing Audit Timeline is completely untouched.

### 11.1 Business objectives
- Move beyond real-time operational visibility (§10) to longer-horizon business intelligence:
  volume trends, finding-type frequency, override/escalation rates, policy-pack effectiveness —
  the kind of reporting that informs process and policy decisions, not day-to-day operations.
- Builds on §10's metric substrate rather than duplicating it — Operational Dashboard is "what's
  happening now," Business Analytics is "what's the trend," same distinction the MVP already
  established between Timeline (narrative) and Audit (compliance record).

### 11.2 Functional requirements
- **FR-BA-001**: System MUST provide volume trend reporting (applications created/completed per
  period) using the existing `Application`/`AuditEvent` data — no new source-of-truth table.
- **FR-BA-002**: System MUST report Finding-outcome distribution (verified/overridden/escalated
  rates, by finding type and by policy version) — directly answers "is our policy calibrated
  correctly," using §3's now-exhaustive `PolicyResult` data as a prerequisite.
- **FR-BA-003**: System MUST support a **Report Definition** concept (saved query + schedule) so
  recurring reports (e.g. weekly override-rate report) don't require ad hoc querying each time.
- **FR-BA-004**: Analytics data MUST NEVER be the source of truth for compliance — Audit (§8
  foundational, unchanged) remains authoritative; analytics is a derived, read-only view, and this
  module must document that distinction explicitly in-product (an "analytics, not audit of record"
  disclosure, mirroring the honest-disclosure discipline already used for the Policy region's
  "cannot show rules that passed silently" banner in the MVP).

### 11.3 Non-functional requirements
- Analytics queries MUST run against a dedicated read/reporting path (materialized views,
  potentially a read replica at higher scale) — must not compete with transactional workload.
- Report generation (scheduled) MUST run asynchronously via the existing job queue.

### 11.4 User stories
- **US-BA-1 (P1)**: As an Operations Manager, I view monthly application volume trends over the
  last 12 months. *Independent test*: seeded historical data produces correct monthly aggregates.
- **US-BA-2 (P1)**: As a Compliance Officer, I view override rates by policy version to judge
  whether a policy pack is too aggressive (flagging too much) or too lax. *Independent test*:
  seeded findings across two policy versions produce distinct, correct override-rate figures.
- **US-BA-3 (P3)**: As an Operations Manager, I schedule a weekly report emailed to my team.

### 11.5 Domain model additions (as implemented)
None persisted — no `ReportDefinition`/`ReportRun` table. `BusinessAnalyticsSnapshot`/
`FindingOutcomeRow`/`PolicyOutcomeRow` (`mil.api.deps`) are plain, non-persisted dataclasses
shaping the output of real aggregate queries against `MortgageApplication`, `Finding`,
`PolicyResult` (correcting an important factual error in the original wording: **`Finding` has no
`policyVersion`/`state` column** — `policy_pack_id` is explicitly documented as "intentionally
omitted this sprint" on the `Finding` model itself, and `policyVersion`/`outcome` actually live on
the separate `PolicyResult` row, keyed by `finding_id`. The materialized view below as originally
written would not have compiled against the real schema — this is exactly the kind of spec/reality
mismatch the user's standing instruction requires correcting, not silently working around),
`Document`, and `EvidenceItem`.

### 11.6 Database schema changes (as implemented)
None. No new schema, table, or materialized view. All aggregates run directly against existing
tables (`core.applications`, `finding.findings`, `policy.policy_results`, `core.documents`,
`evidence.evidence_items`, `review.review_sessions`).

### 11.7 API contracts (as implemented)
- `GET /v1/analytics/snapshot` → `BusinessAnalyticsSnapshotResponse`: application counts by
  status, finding lifecycle-state distribution (`FindingRepository.count_by_lifecycle_state`),
  policy outcome distribution by version (`PolicyRepository.count_by_version_and_outcome` — the
  corrected FR-BA-002 signal), document/evidence counts, average review duration
  (`ReviewRepository.get_average_duration_seconds`, `null` when no session has closed).
- Schema lives in the existing `mil.api.v1.schemas` module (no separate `analytics.yaml` — same
  convention as every other Wave 2/3 module).

### 11.8 RBAC changes (as implemented)
- New permission: `Permission.READ_ANALYTICS` — granted to `OPERATIONS_MANAGER`,
  `COMPLIANCE_OFFICER` (`ADMIN` already bypasses all permission checks via `Permission.ADMIN`, so
  no explicit grant is needed for that role).
- `Permission.MANAGE_REPORTS` is not introduced — there is no report-scheduling capability to
  gate (§11's correction note).

### 11.9 AI considerations
- None in the reporting layer itself. A future Copilot-generated narrative summary of a report
  ("volume is up 12% month over month, driven by...") is a natural, explicitly-deferred extension
  (§11.14) — not built here, and if built later, must carry the same citation/grounding discipline
  as §8.

### 11.10 Integration requirements
- Scheduled report delivery depends on §13 (Notification System) for email/delivery channel.

### 11.11 UX considerations
- Table/badge-first presentation (matching this whole plan's established "no charting library
  added speculatively" discipline) for the initial release — simple trend tables and delta
  indicators, not a BI-dashboard visual language; a charting library is a deliberate future decision
  (§11.14), not defaulted to.

### 11.12 Acceptance criteria
- Given historical application data, when volume trend is queried, then monthly counts are
  correct and match a manual count over the same window.
- Given a scheduled report definition, when its schedule fires, then a `ReportRun` is created and
  completes asynchronously without blocking any user-facing request.
- **Constitution check**: Principle XI (analytics informs, never replaces, the Audit record) ✅;
  Principle X (Operational Excellence extended to a longer time horizon) ✅.

### 11.13 Risks
- **Analytics mistaken for audit**: the explicit in-product disclosure (FR-BA-004) is the primary
  mitigation for a real risk — a report number and an audit-log count could diverge (e.g. due to
  materialized view refresh timing), and users must never be misled into treating one as a
  replacement for the other.
- **Report sprawl**: an open `reportType` string risks becoming an ungoverned pile of one-off
  reports — mitigated by requiring new report types to be reviewed/registered (a lightweight
  process control, not a technical one).

### 11.14 Future extensibility
- Explicitly deferred: charting/visualization library adoption, AI-narrated report summaries,
  cross-tenant benchmarking (multi-tenant deployments comparing anonymized aggregate metrics — a
  significant privacy-review undertaking of its own, not assumed here).

---

## 12. Customer Portal

> **Wave 4 implementation correction (2026-07-12)**: this section originally specified
> `email` stored plaintext on `PortalAccount`, `document_checklist_items` living in the `core`
> schema, and separate `portal-internal.yaml`/`portal-external.yaml` OpenAPI files. Corrected as
> follows: `email` is stored only as `emailHash` (SHA-256), mirroring `identity.User.emailHash`'s
> exact discipline — MIL does not store borrower PII in plaintext anywhere else, and this module is
> no exception (Principle V). `document_checklist_items` lives in a new `portal` schema (not
> `core`), matching every other Wave 2/3 module's own-schema convention. No separate OpenAPI files
> are generated — this project's OpenAPI is produced from one FastAPI app (every prior wave's
> modules follow the same convention); the security separation the spec calls for is achieved
> instead by genuinely separate authentication dependencies (`get_current_user` vs. a new
> `get_current_portal_claims`, verified against a dedicated `Settings.mil_portal_secret_key` — a
> different HMAC key from internal token verification, not merely a different code path), which is
> the real mechanism the spec's acceptance criterion ("a portal token is rejected against an
> internal endpoint") requires — separate contract *files* would not have provided that guarantee on
> their own. Additionally: no email/SMS delivery provider exists anywhere in this platform
> (confirmed by inspection) — invitation delivery (§12.10's dependency on §13) is not implemented;
> the invite endpoint returns the raw activation token directly to the inviting internal user, who
> relays it out-of-band. This is a disclosed, honest gap, not a fabricated delivery mechanism. One
> new internal-only RBAC role, `Role.PORTAL_ACCOUNT` (exactly one permission,
> `Permission.UPLOAD_DOCUMENT`), is constructed synthetically by the composition layer solely to
> satisfy `DocumentService.ingest_document`'s existing RBAC check when a borrower uploads through
> the reused contract (FR-CP-003) — never assignable to a real user, never surfaced through any
> admin UI, and not a violation of §12.8's "portal accounts are never evaluated through internal
> RBAC" principle in spirit: the portal account itself is never assigned a role or checked against
> `has_permission` anywhere in its own auth flow; only this one narrow, internal composition-layer
> detail reuses the permission *gate already built into* the document upload path, to honor
> FR-CP-003's stronger requirement of no separate upload pipeline.

### 12.1 Business objectives
- Give borrowers a secure, limited self-service surface to upload requested documents and check
  status — reducing RM/Underwriter time spent chasing paperwork, while strictly preserving MIL's
  core trust boundary: borrowers never see AI findings, evidence, policy results, or anything
  resembling a decision (Principle I applies with maximum force here — a borrower-facing surface
  that leaked a Finding would be a severe trust and regulatory failure).
- This is the first genuinely **external**, unauthenticated-until-login user population MIL has
  ever supported — a distinct trust boundary from every internal role, and must be engineered as
  such (separate auth realm, not an extension of internal RBAC roles).

### 12.2 Functional requirements
- **FR-CP-001**: A borrower MUST authenticate through a distinct portal auth flow (e.g.
  magic-link or credential-based, tied to their `Party` record via a secure invitation token) —
  never sharing session/token infrastructure with internal staff authentication.
- **FR-CP-002**: A borrower MUST see only: their application's status (a simplified, borrower-safe
  status label, not the internal `ApplicationStatus` enum verbatim), a **Document Checklist**
  (what's requested, what's received, what's missing), and an upload action per checklist item.
- **FR-CP-003**: Document upload from the portal MUST reuse the existing `POST
  /v1/applications/{id}/documents` contract (same 25MB limit, same content-hash computation) —
  no separate, divergent upload pipeline.
- **FR-CP-004**: A borrower MUST NOT be able to see any other borrower's application, any Finding,
  Evidence, Policy result, internal comment (§9), or Timeline/Audit detail — enforced by a
  portal-specific, minimal read API, not by reusing and filtering the internal API surface (a
  smaller, purpose-built surface is safer than a large surface with hope-based filtering).
- **FR-CP-005**: Document Checklist items MUST be created by an Underwriter/RM ("please upload your
  latest bank statement") — the portal is where a borrower fulfills a request, not where they
  freely upload arbitrary documents.

### 12.3 Non-functional requirements
- Portal MUST run on a genuinely separate authentication/session boundary from the internal
  application — a compromised portal session must never grant any internal capability.
- Portal-facing endpoints MUST be rate-limited more aggressively than internal endpoints (public
  internet exposure, unauthenticated-until-login attack surface).
- Must meet WCAG-level accessibility given a broader, less-technical user population than internal
  staff (higher bar than "nice to have" here).

### 12.4 User stories
- **US-CP-1 (P1)**: As a borrower, I receive an invitation link, set up portal access, and see a
  checklist of documents I need to provide. *Independent test*: invitation token → portal account
  creation → checklist visible, scoped to my application only.
- **US-CP-2 (P1)**: As a borrower, I upload a requested bank statement and see the checklist item
  move from "requested" to "received," and my Underwriter sees the same document appear in the
  normal Documents region. *Independent test*: portal upload → same document row visible in the
  internal workspace via the existing document list.
- **US-CP-3 (P2)**: As a borrower, I check my application status in plain language ("Documents
  under review") rather than an internal enum value.

### 12.5 Domain model additions (as implemented — `mil.portal`)
- **`PortalAccount`** — `id`, `tenantId`, `partyId` (FK — ties portal identity to the existing
  `Party`, not a new borrower-identity concept competing with §5), `emailHash` (SHA-256, never
  plaintext — see this section's implementation-correction note), `status`
  (`INVITED`/`ACTIVE`/`SUSPENDED`), `invitationTokenHash` (nullable — cleared on activation, so an
  already-consumed token can never be replayed), `invitedAt`, `activatedAt`.
- **`DocumentChecklistItem`** — `id`, `tenantId`, `applicationId`, `partyId` (nullable — some
  requests are application-level, not party-specific), `label`, `documentType` (matches the existing
  free-string convention), `status` (`REQUESTED`/`RECEIVED`/`WAIVED`), `requestedByUserId`,
  `fulfilledDocumentId` (nullable, set once a matching document is uploaded), `requestedAt`.

### 12.6 Database schema changes (as implemented — migration `0020_portal.py`)
```sql
CREATE SCHEMA IF NOT EXISTS portal;

CREATE TABLE portal.portal_accounts (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    party_id UUID NOT NULL REFERENCES core.parties(id) UNIQUE,
    email_hash VARCHAR(128) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'INVITED',
    invitation_token_hash VARCHAR(128),
    invited_at TIMESTAMPTZ NOT NULL,
    activated_at TIMESTAMPTZ
);

CREATE TABLE portal.document_checklist_items (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    application_id UUID NOT NULL REFERENCES core.applications(id),
    party_id UUID REFERENCES core.parties(id),
    label TEXT NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'REQUESTED',
    requested_by_user_id UUID NOT NULL REFERENCES core.users(id),
    fulfilled_document_id UUID REFERENCES core.documents(id),
    requested_at TIMESTAMPTZ NOT NULL
);
```

### 12.7 API contracts (as implemented)
- **Internal-facing** (existing internal auth — `mil.api.v1.checklist`):
  `POST /v1/applications/{id}/checklist-items`, `GET .../checklist-items`,
  `POST .../checklist-items/{id}/waive`, `POST .../checklist-items/{id}/invite-borrower`.
- **Portal-facing** (separate auth realm — `mil.api.v1.portal`, gated by `CurrentPortalClaims`, not
  `CurrentUser`): `POST /v1/portal/auth/activate`, `GET /v1/portal/checklist`,
  `GET /v1/portal/status`, `POST /v1/portal/checklist/{id}/upload`. No `request-link` endpoint —
  the invite step (internal-side) is what issues the raw activation token today (see this section's
  correction note on email/SMS delivery).
- Schemas live in the existing `mil.api.v1.schemas` module (no separate `portal-internal.yaml`/
  `portal-external.yaml` — see this section's correction note for why).

### 12.8 RBAC changes (as implemented)
- Portal accounts are **not** part of the internal `Role`/`ROLE_PERMISSIONS` system in their own
  auth flow at all — `mil.portal.auth`'s HMAC verification and `PortalService`'s portal-safe
  primitives never call `has_permission`/`require_permission`. The one narrow exception (documented
  in this section's correction note): a synthetic `Role.PORTAL_ACCOUNT` principal, constructed only
  inside `PortalWorkspace.upload_for_claims`, reuses `DocumentService.ingest_document`'s existing
  RBAC gate — never exposed, never assignable, never checked anywhere else in the portal's own
  request path.
- New internal permission: `Permission.MANAGE_CHECKLIST` — granted to `UNDERWRITER`,
  `RELATIONSHIP_MANAGER`.

### 12.9 AI considerations
- None borrower-facing, by design (Principle I, maximum force as noted in §12.1). No AI-generated
  content of any kind reaches the portal in this spec.

### 12.10 Integration requirements
- Reuses the existing document upload contract (FR-CP-003) — no new ingestion pipeline.
- Depends on §13 for invitation-link delivery (email/SMS).

### 12.11 UX considerations
- A deliberately minimal, plain-language, non-technical UI — no design-system component shared
  verbatim with the internal Workspace's dense, information-rich style; the portal needs a calmer,
  more guided register (closer to a consumer banking app than an enterprise console) — this is a
  new, small, purpose-built UI, not a cut-down version of the Underwriter Workspace.
- Checklist status uses plain, reassuring language ("We've received this" / "Please upload this
  when ready") — never exposes internal status vocabulary or urgency framing meant for staff.

### 12.12 Acceptance criteria
- Given a borrower with an active portal account, when they view their checklist, then they see
  only items for their own `partyId`/application, never another borrower's.
- Given a borrower uploads a document against a checklist item, then the item transitions to
  `RECEIVED` and the document appears in the internal Documents region identically to a
  staff-initiated upload.
- Given an attempt to use a portal session token against an internal API endpoint, then it is
  rejected (proves the auth realms are genuinely separate, not just conventionally separate).
- **Constitution check**: Principle I (zero AI/finding/decision exposure to borrowers) ✅; Principle
  V (Zero Trust — portal is a distinct, more aggressively verified trust boundary, not a relaxed
  extension of internal trust) ✅.

### 12.13 Risks
- **This is the platform's largest new attack surface** — internet-facing, external-user
  authentication. Requires its own dedicated security review (pen-test) before launch, beyond the
  standard review other modules receive — called out explicitly, not left implicit.
- **Borrower confusion from over-simplified status**: mapping internal statuses to a small
  borrower-safe vocabulary risks under-informing borrowers — mitigated by user testing the plain-
  language mapping, not solved by this spec alone.
- **Checklist/document mismatch**: a borrower could upload the wrong document against a checklist
  item — `fulfilledDocumentId` links are set by upload-time association, not content verification;
  a human (RM/Underwriter) still confirms fulfillment is substantively correct, matching Principle I.

### 12.14 Future extensibility
- Portal e-signature/consent capture, portal-side messaging with the RM (a scoped extension of §9,
  not a new system), and a mobile app wrapper are all explicitly out of scope here, noted as
  natural next steps once the base portal is proven.

---

## 13. Notification System

### 13.1 Business objectives
- Provide one, consistent, cross-module notification substrate — §1 (assignment), §2 (LOS sync
  failure), §4 (approval requests), §9 (mentions), §11 (scheduled reports), and §12 (borrower
  invitations/checklist reminders) all need to notify a user or borrower of something. Without this
  module, each would invent its own ad hoc mechanism — this module exists specifically to prevent
  that duplication (Principle IX: don't invent parallel infrastructure per module).

### 13.2 Functional requirements
- **FR-NOTIF-001**: System MUST provide a single `NotificationEvent` model with a `notificationType`
  (open string) and a `payload` (JSON), emitted by any module via one shared internal service
  interface (`emit_notification(userId | portalAccountId, type, payload)`).
- **FR-NOTIF-002**: System MUST support at least two delivery channels: in-app (a notification
  bell/inbox, matching the existing `Toast`/`uiStore` pattern's spirit but persistent, not
  ephemeral) and email — SMS is named as future (§13.14), not built now.
- **FR-NOTIF-003**: Users MUST be able to configure per-notification-type channel preferences
  (e.g. "email me on mentions, in-app only for assignment changes").
- **FR-NOTIF-004**: Notification delivery MUST be logged (`NotificationDeliveryLog`) with success/
  failure per channel — a failed email send must be visible to Operations (§10), not silently lost.
- **FR-NOTIF-005**: High-volume notification sources (e.g. many mentions in a short window) MUST
  support digesting/batching rather than one email per event — specifically named because §9's own
  risk section calls this out.

### 13.3 Non-functional requirements
- Notification delivery MUST be asynchronous (existing job queue) — never block the triggering
  request (a comment post must not wait on an email send to complete).
- Delivery failures MUST NOT retry indefinitely without a ceiling — reuses the same
  poison-job-awareness this spec's §10 already surfaces for other job types.

### 13.4 User stories
- **US-NOTIF-1 (P1)**: As a user, I receive an in-app notification when assigned an application,
  and can click through directly to it. *Independent test*: assignment write → notification
  created → in-app inbox shows it with a correct deep link.
- **US-NOTIF-2 (P2)**: As a user, I set my mention notifications to email-only and stop seeing them
  in-app, while assignment notifications remain in-app. *Independent test*: preference change
  changes only the targeted notification type's channel behavior.
- **US-NOTIF-3 (P3)**: As Operations, I see a failed email delivery in the operational dashboard
  with the real provider error.

### 13.5 Domain model additions
- **`NotificationEvent`** — `id`, `recipientUserId` (nullable if `recipientPortalAccountId` set
  instead — mutually exclusive), `recipientPortalAccountId`, `notificationType`, `payload`,
  `createdAt`, `readAt` (nullable, in-app read receipt).
- **`NotificationPreference`** — `id`, `userId`, `notificationType`, `channels` (array:
  `IN_APP`/`EMAIL`/future `SMS`).
- **`NotificationDeliveryLog`** — `id`, `notificationEventId`, `channel`, `status`
  (`SENT`/`FAILED`), `errorMessage`, `attemptedAt`.

### 13.6 Database schema changes
```sql
CREATE SCHEMA IF NOT EXISTS notification;

CREATE TABLE notification.notification_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID REFERENCES identity.users(id),
    recipient_portal_account_id UUID REFERENCES portal.portal_accounts(id),
    notification_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ,
    CHECK (
        (recipient_user_id IS NOT NULL AND recipient_portal_account_id IS NULL) OR
        (recipient_user_id IS NULL AND recipient_portal_account_id IS NOT NULL)
    )
);

CREATE TABLE notification.notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES identity.users(id),
    notification_type TEXT NOT NULL,
    channels TEXT[] NOT NULL DEFAULT '{IN_APP}',
    UNIQUE (user_id, notification_type)
);

CREATE TABLE notification.notification_delivery_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_event_id UUID NOT NULL REFERENCES notification.notification_events(id),
    channel TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('SENT','FAILED')),
    error_message TEXT,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 13.7 API contracts
- `GET /v1/notifications` (in-app inbox, paginated) / `POST /v1/notifications/{id}/read`.
- `GET /v1/notifications/preferences` / `PUT /v1/notifications/preferences`.
- No public "create notification" endpoint — `emit_notification` is an internal service call other
  modules invoke, never a directly-callable API (prevents notification spoofing/spam via the API).
- New OpenAPI file: `notifications.yaml`.

### 13.8 RBAC changes
- None beyond "a user manages only their own notifications/preferences" (identity-scoped, not
  role-scoped).

### 13.9 AI considerations
- None. Purely a delivery/preference substrate.

### 13.10 Integration requirements
- Requires an email delivery provider integration (SMTP relay or a transactional email API) — the
  first genuinely new *outbound* third-party integration in this spec (distinct from the LOS
  integration in §2, and from the existing Gemini inference integration). Vendor selection is an
  implementation-time decision, not fixed by this spec; the service interface must be provider-
  agnostic (mirrors §2's adapter-interface discipline).

### 13.11 UX considerations
- In-app notification bell + inbox panel, following the same design-system extension pattern as
  Toast (Phase 0 of the prior UI plan) — a new, but consistent, primitive.
- Deep links from a notification always land the user on the exact resource referenced (an
  assignment notification opens that application; a mention opens that comment thread) — never a
  generic "go to dashboard" fallback.

### 13.12 Acceptance criteria
- Given a user's preference set to email-only for a notification type, when that type fires, then
  no in-app notification row is marked for in-app display (or is marked read-suppressed, per
  implementation choice) and an email delivery is attempted and logged.
- Given an email delivery failure, then it is visible in `NotificationDeliveryLog` with the real
  provider error, surfaced to Operations (§10).
- **Constitution check**: Principle IX (one shared substrate, not N ad hoc mechanisms) ✅; no
  conflict with Principle V — notification payloads must not carry more data than needed for the
  in-app/email rendering (least-data principle, applied to notification payloads exactly as to AI
  prompts).

### 13.13 Risks
- **Notification fatigue** is a real cross-cutting risk (this module's own §13.2 FR-NOTIF-005
  exists specifically to mitigate it) — batching/digest logic must ship alongside the base feature,
  not as an afterthought once users complain.
- **Email deliverability**: a new outbound email dependency introduces SPF/DKIM/domain-reputation
  operational concerns — a Production Infrastructure (§14) concern to configure correctly, noted
  here as a dependency, not solved in this module.

### 13.14 Future extensibility
- SMS/push channels are additive (`channels` array already supports future values without a schema
  change). A future "notification digest email" (daily summary) is a natural batching extension of
  the existing delivery-log/preference model.

---

## 14. Production Infrastructure

> **Wave 4 implementation correction (2026-07-12)**: this section originally specified replacing
> the job queue with a real broker-backed implementation (FR-INFRA-001) — but direct inspection of
> `mil.kernel.job_queue` confirmed `RedisJobQueue` **already existed and was already the real,
> process-safe, cross-process implementation** (an `InProcessJobQueue` exists too, but only as a
> documented dev/test convenience). The actual, concretely-documented gap (RC1 release checklist)
> was narrower and more precise: no redelivery/visibility-timeout for a worker that crashes between
> dequeuing a job and acknowledging/rejecting it. This wave fixes exactly that gap: `RedisJobQueue`
> now tracks a `claimed_at` timestamp per in-flight job and exposes `reclaim_stale(visibility_
> timeout_seconds)` (a periodic reaper call — not automatic, since automatic reclaiming from inside
> the class itself would need its own background thread/process, which is a deployment-topology
> decision, not application code) plus a real dead-letter list surfaced via `dead_letter_count()`.
> This was verified against a real Redis instance via `testcontainers`, not merely unit-tested with
> mocks. FR-INFRA-002 (secrets manager), FR-INFRA-003 (OpenTelemetry tracing/structured logging
> beyond what already exists), and FR-INFRA-004 (backup/DR tooling) are genuinely infrastructure/
> deployment-topology decisions that cannot be honestly "implemented" as application code in this
> repository — they depend on an actual Vault/cloud-KMS instance, an actual OTel collector, and an
> actual backup target existing in a real deployment environment. Per the user's own instruction
> for this module ("if infrastructure already exists, expose it; do not invent functionality"),
> these are documented in `docs/deployment/` (§17) as concrete, actionable runbook items rather than
> fabricated with placeholder code that would falsely claim the capability exists. The new `GET
> /v1/operational/job-queue-health` endpoint (reusing §10's `OperationalWorkspace`, not a new
> dashboard) surfaces the real `pending_count`/`processing_count`/`dead_letter_count` counters this
> wave added — the one new UI-visible capability from this section.

### 14.1 Business objectives
- Move the platform from its documented current state — "Ready for Demo, not yet Ready for
  Production," per the MVP's own RC1 release checklist, explicitly because "a broker-backed job
  queue" doesn't yet exist — to a real production deployment posture. This module is where that
  explicit, already-known gap gets closed, alongside the infrastructure needs every other module in
  this spec introduces (secrets management for §2's LOS credentials, email delivery for §13, object
  storage scaling for §3/§11 report artifacts).

### 14.2 Functional requirements
- **FR-INFRA-001**: System MUST replace the current in-memory/dev-mode job queue with a real,
  broker-backed queue (Redis Streams, RabbitMQ, or equivalent — a deployment-time choice per the
  existing architecture's own "broker implementation is a replaceable deployment configuration"
  principle from `specs/001-mil-platform-spec/plan.md`) supporting **redelivery on worker crash**
  and a **visibility timeout** — the exact two gaps the MVP's RC1 pass documented and left open.
- **FR-INFRA-002**: System MUST integrate a real secrets manager (Vault, AWS Secrets Manager, or
  equivalent) for all credentials — LOS connection secrets (§2), email provider credentials (§13),
  database credentials, LLM provider API keys — none embedded in configuration or environment
  files checked into source control (Principle V, explicit non-negotiable).
- **FR-INFRA-003**: System MUST provide structured logging, distributed tracing, and metrics
  (OpenTelemetry, per the existing Technical Context in `specs/001-mil-platform-spec/plan.md`) for
  every module added in this spec, not only the original MVP scope.
- **FR-INFRA-004**: System MUST define a backup/disaster-recovery procedure for PostgreSQL (the
  system of record for Evidence/Audit — Principle VIII's immutability guarantee is worthless
  without a real backup story) and object storage (document archive).
- **FR-INFRA-005**: System MUST support horizontal scaling of stateless API/worker processes
  without a data-model change, per the existing plan's stated 10x-growth accommodation target.

### 14.3 Non-functional requirements
- Job queue redelivery MUST guarantee at-least-once processing with idempotent job handlers (a
  job that's redelivered after a crash must not double-write Evidence/Findings — existing pipeline
  code must be audited for idempotency as part of this module's rollout, not assumed).
- Recovery Point Objective (RPO) and Recovery Time Objective (RTO) targets MUST be explicitly
  defined and tested (not just documented aspirationally) — specific numbers are a deployment-
  context decision (this spec defines the requirement to have them, not the numbers themselves,
  which depend on the hosting institution's own regulatory requirements).
- Air-gapped/on-premises deployability (already a stated constraint in the existing plan) MUST be
  preserved by every infrastructure choice in this module — no mandatory external SaaS dependency
  introduced without an on-premises equivalent path.

### 14.4 User stories
- **US-INFRA-1 (P1)**: As Operations, when a worker process crashes mid-job, the job is redelivered
  to another worker and completes correctly, with no data duplicated and no job silently lost.
  *Independent test*: kill a worker mid-job in a test environment; confirm the job completes exactly
  once downstream (idempotent), not zero or two times.
- **US-INFRA-2 (P1)**: As a Security Engineer, I confirm no credential exists in any config file,
  environment variable dump, or source-controlled file — all resolve through the secrets manager.
  *Independent test*: a repo-wide secret-scan finds zero hardcoded credentials.
- **US-INFRA-3 (P2)**: As Operations, I restore the database from backup in a DR drill and confirm
  RPO/RTO targets are met.

### 14.5 Domain model additions
- None — this module is infrastructure, not domain model. No new business entities.

### 14.6 Database schema changes
- None new at the application schema level. Operational changes: enabling PostgreSQL WAL archiving/
  point-in-time-recovery configuration, connection pooling (PgBouncer or equivalent) for horizontal
  API scaling — deployment configuration, not schema DDL.

### 14.7 API contracts
- None new at the product API level. A `GET /healthz`/`GET /readyz` pair (if not already present)
  for orchestrator health checks is the only API-shaped addition.

### 14.8 RBAC changes
- None at the application RBAC level — infrastructure access (secrets manager, DB admin) is
  governed by infrastructure-layer IAM, deliberately outside the application's own `Role`/
  `Permission` system (separation of concerns between application RBAC and infrastructure IAM).

### 14.9 AI considerations
- None directly, though FR-INFRA-002's secrets management is a direct enabler of Principle V's
  "AI context isolation" and "least-data principle for AI prompts" — infrastructure is what makes
  those principles enforceable in practice, not just statable.

### 14.10 Integration requirements
- Message broker (Redis Streams/RabbitMQ), secrets manager (Vault/cloud-native equivalent),
  observability backend (OpenTelemetry-compatible collector — Jaeger/Tempo/cloud-native equivalent),
  backup tooling (`pg_basebackup`/WAL-G or equivalent, cloud-native snapshotting).

### 14.11 UX considerations
- None end-user-facing. Operations-facing infrastructure health surfaces (queue health, backup
  status) integrate into §10's Operational Dashboard rather than a separate ops console — one
  operational surface, not two.

### 14.12 Acceptance criteria
- Given a simulated worker crash mid-job, when the job is redelivered, then it completes exactly
  once from the domain's perspective (no duplicate Evidence/Finding rows).
- Given a full secret-scan of the repository and deployed configuration, then zero hardcoded
  credentials are found.
- Given a DR drill, then the database is restored within the defined RTO and data loss is within
  the defined RPO.
- **Constitution check**: Principle V (secrets management, encryption) ✅; Principle VIII (backup
  strategy protects the immutable audit/evidence record from being un-recoverably lost) ✅;
  Principle IX (broker choice remains a replaceable deployment configuration, per the existing
  architectural decision) ✅.

### 14.13 Risks
- **Idempotency gaps in existing pipeline code**: the existing `finding_pipeline.py`/
  `policy_pipeline.py`/`document_pipeline.py` were built and tested against a dev-mode queue
  without redelivery — this module's rollout MUST include an explicit idempotency audit of each
  pipeline before enabling real redelivery, or FR-INFRA-001 will surface **new** data-duplication
  bugs rather than fixing the crash-recovery gap.
- **Secrets migration cutover risk**: moving live credentials (especially the LLM provider key and
  any already-configured LOS test credentials) to a secrets manager is itself a risky, one-time
  cutover — requires a documented rollback path.

### 14.14 Future extensibility
- Multi-region deployment and read-replica scaling are named in §17 (Deployment Architecture), not
  duplicated here — this module defines the single-region production-readiness bar; §17 defines
  how deployment topology scales beyond it.

---

## 15. Enterprise Administration

### 15.1 Business objectives
- Give an Administrator a real UI/API onto the identity/RBAC domain layer that **already exists**
  (`src/mil/identity/`: `User`, `Role`, `RoleAssignment`, `rbac.py`, `abac.py`, `dev_seed.py` —
  confirmed, per §0's ground-truth table, with no HTTP route today) — user management, role
  assignment, and tenant-level configuration.
- Provide the administrative surface every other module in this spec assumes exists (§1's
  `REGIONAL_MANAGER` region assignment, §4's Policy Administrator role grant, §2's connection
  management, §13's provider configuration) — this module is the control plane the rest of the
  spec's roles/permissions are actually granted through.

### 15.2 Functional requirements
- **FR-ADMIN-001**: An Administrator MUST be able to create/deactivate users and assign/revoke
  roles, using the existing `User`/`Role`/`RoleAssignment` domain model — this module adds the API/
  UI, not new domain concepts.
- **FR-ADMIN-002**: System MUST support tenant-level configuration (feature flags per tenant,
  branding, active LOS connections list from §2, notification provider config from §13) — a
  **`TenantConfiguration`** entity distinct from any single module's own config.
- **FR-ADMIN-003**: System MUST support **API Keys** for service-to-service integration (distinct
  from the `SERVICE_ACCOUNT` role already defined) — scoped, revocable, with an expiry, never a
  permanent unexpiring credential by default.
- **FR-ADMIN-004**: Every administrative action (user create/deactivate, role grant/revoke, tenant
  config change, API key issuance/revocation) MUST be an immutable Audit Event (Principle VIII) —
  administration is exactly the kind of action the constitution already requires auditing, this
  module doesn't get an exception.
- **FR-ADMIN-005**: An Administrator MUST NOT be able to grant themselves a role they don't already
  have the authority to grant (e.g. a tenant-scoped Admin cannot grant themselves a
  platform-superuser role, if such a distinction exists in a multi-tenant deployment) —
  self-escalation prevention.

### 15.3 Non-functional requirements
- Administrative endpoints are lower-throughput, higher-sensitivity — favor strict validation and
  full audit logging over raw performance; no specific latency target beyond standard API response
  norms.
- Role/permission changes MUST take effect for a user's *next* request at the latest (session
  invalidation or short-TTL permission caching, not a stale permission set persisting for a full
  session lifetime after revocation) — a security-relevant freshness requirement.

### 15.4 User stories
- **US-ADMIN-1 (P1)**: As an Administrator, I create a new user, assign them the `UNDERWRITER` role,
  and they can immediately access the Underwriter Workspace. *Independent test*: user creation →
  role assignment → login → correct permission set observed.
- **US-ADMIN-2 (P1)**: As an Administrator, I revoke a user's role and their next request reflects
  the reduced permission set, not their prior session's cached permissions.
- **US-ADMIN-3 (P2)**: As an Administrator, I issue a scoped, expiring API key for a new LOS
  integration test and revoke it once testing is done.

### 15.5 Domain model additions
- No new entities for user/role management — `User`, `Role`, `RoleAssignment` already exist.
  Additions:
- **`TenantConfiguration`** — `id`, `tenantId`, `configKey`, `configValue` (JSON), `updatedByUserId`,
  `updatedAt`.
- **`ApiKey`** — `id`, `tenantId`, `name`, `hashedKey` (never the raw key, stored hashed like a
  password), `scopes` (array of permission strings), `expiresAt`, `revokedAt`, `createdByUserId`.
- **`User.regionId`** (new column) — the attribute §1's `REGIONAL_MANAGER` ABAC scoping needs.

### 15.6 Database schema changes
```sql
ALTER TABLE identity.users ADD COLUMN region_id UUID;

CREATE TABLE identity.tenant_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    config_key TEXT NOT NULL,
    config_value JSONB NOT NULL,
    updated_by_user_id UUID NOT NULL REFERENCES identity.users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, config_key)
);

CREATE TABLE identity.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    hashed_key TEXT NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT '{}',
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_by_user_id UUID NOT NULL REFERENCES identity.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 15.7 API contracts
- `POST /v1/admin/users` / `GET /v1/admin/users` / `PATCH /v1/admin/users/{id}/deactivate`.
- `POST /v1/admin/users/{id}/roles` / `DELETE /v1/admin/users/{id}/roles/{roleId}`.
- `GET /v1/admin/tenant-config` / `PUT /v1/admin/tenant-config/{key}`.
- `POST /v1/admin/api-keys` (returns the raw key exactly once, never retrievable again) /
  `DELETE /v1/admin/api-keys/{id}`.
- New OpenAPI file: `administration.yaml`.

### 15.8 RBAC changes
- `Role.ADMIN` (already exists, already holds the `admin` super-permission) is this module's
  primary consumer — no new role required for basic administration.
- New, narrower permission for large deployments: `Permission.MANAGE_USERS` and
  `Permission.MANAGE_ROLES` **already exist** in `security.py`, currently unused by any route —
  this module is their first consumer, allowing a future "User Administrator" role narrower than
  full `ADMIN` without a security-model change.

### 15.9 AI considerations
- None — pure administrative CRUD and access control.

### 15.10 Integration requirements
- Feeds tenant configuration to §2 (LOS connections), §13 (notification provider config) — this
  module is the configuration root other modules read from, not a new integration itself.

### 15.11 UX considerations
- A dedicated Administration section in the navigation shell — the MVP's Phase 0 navigation config
  was explicitly built so "a future Administration section... can be added later without
  restructuring" (direct quote from the prior UI plan) — this module is that anticipated addition,
  confirming the earlier design decision was correctly future-proofed.
- User/role management uses the existing `Table`/`Dialog`/`Drawer` design-system components — no
  new list/form primitives needed.

### 15.12 Acceptance criteria
- Given a role revocation, when the affected user makes their next request, then it reflects the
  reduced permission set (not a stale cached one).
- Given an API key is revoked, when used afterward, then requests using it are rejected.
- Given a non-Admin attempts any `/v1/admin/*` endpoint, then 403.
- **Constitution check**: Principle V (least-privilege, RBAC administration itself audited) ✅;
  Principle VIII (every admin action is an immutable Audit Event) ✅.

### 15.13 Risks
- **Self-escalation**: FR-ADMIN-005 exists specifically because administrative surfaces are a
  classic privilege-escalation vector — must be enforced server-side, not merely hidden in the UI.
- **API key leakage**: a leaked, long-lived API key with broad scopes is a severe risk — mitigated
  by mandatory expiry (`expiresAt` NOT NULL) and scoped permissions, never an unscoped "full access"
  key by default.

### 15.14 Future extensibility
- `TenantConfiguration`'s generic key/value shape supports future per-tenant feature flags without
  a schema change. Multi-tenant platform-level (cross-tenant) administration, if the platform ever
  hosts multiple institutions on shared infrastructure, is a further extension noted in §17, not
  built here (this module assumes single-tenant-per-deployment administration, matching the
  existing plan's Phase-5-not-yet-scoped multi-tenancy note).

---

## 16. Security and Compliance

> **Wave 4 implementation correction (2026-07-12)**: this section originally specified a
> persisted `ComplianceReportRequest` table with async report generation (`status`/`resultRef`,
> implying a job-queue-driven report artifact). As implemented, FR-SEC-003's access-log report is a
> single on-demand endpoint (`GET /v1/compliance/access-log`) querying the existing, already-
> persisted `AuditEvent` table directly via a new `AuditRepository.get_for_application_in_range`
> method — no new parallel logging mechanism, exactly as the spec's own NFR requires, and no
> fabricated async job/report-artifact infrastructure for what is, at this platform's real data
> volumes, a fast, synchronous query. `DataRetentionPolicy`'s DB-level immutability guarantee
> (FR-SEC-004/16.12's acceptance criterion) was verified against a real PostgreSQL instance during
> implementation — a direct `INSERT ... action='DELETE', data_category='AUDIT_EVENT'` is rejected
> by the `CHECK` constraint, confirmed live, not merely asserted in code review. Consent recording
> (FR-SEC-002) is wired into the real Customer Portal activation flow (§12) — every portal account
> activation now creates a real, timestamped `ConsentRecord`, not a placeholder. `Permission.
> READ_COMPLIANCE` is granted to `AUDIT_TEAM`; `Permission.MANAGE_COMPLIANCE` to `COMPLIANCE_OFFICER`
> (`ADMIN` already bypasses all permission checks via `Permission.ADMIN`).

### 16.1 Business objectives
- Operationalize Constitution Principle V (Security and Privacy by Design) and Principle XI
  (Regulatory Alignment) as concrete, testable platform capabilities — data retention, consent
  tracking, encryption verification, and compliance reporting — rather than leaving them as
  narrative principles with no enforcement surface.

### 16.2 Functional requirements
- **FR-SEC-001**: System MUST enforce a configurable **data retention policy** per data category
  (Documents, Evidence, Audit Events, Notification logs) — Audit Events, per Principle VIII, are
  never deleted early, but retention *beyond* the regulatory minimum MUST be governable, and
  eventual archival (not deletion, for Audit) to cheaper storage MUST be supported.
- **FR-SEC-002**: System MUST record borrower **consent** where required (e.g. consent to data
  processing captured at portal account activation, §12) as an explicit, timestamped
  `ConsentRecord` — never inferred from "they used the portal."
- **FR-SEC-003**: System MUST support a **compliance report** generation capability (e.g. "list
  every access to Application X's data in the last 90 days," directly satisfying Principle V's
  "full auditability of data access" requirement) — built on existing Audit Event data, not a new
  parallel logging mechanism.
- **FR-SEC-004**: System MUST verify (not just assert) encryption at rest for PII columns —
  this module specifies which columns require column-level encryption (building on the existing
  Constitution requirement) and a periodic automated check that it remains configured correctly.
- **FR-SEC-005**: System MUST support **data subject access/erasure requests** at the granularity
  regulation requires — for MIL specifically, this means a documented procedure for what can and
  cannot be erased given the immutable Audit/Evidence requirement (Principle VIII creates a real
  tension with a naive "right to erasure" that this module must resolve explicitly: audit
  immutability is itself often a *separate* regulatory requirement that supersedes deletion
  requests for financial records, and this module's job is to document that resolution, not paper
  over the tension).

### 16.3 Non-functional requirements
- All new schemas introduced by this entire spec (§1–§17) MUST be reviewed against this module's
  data-classification/retention policy before their migrations are finalized — this module is a
  gate other modules pass through, not an independent afterthought bolted on at the end.
- Compliance report generation MUST NOT degrade the performance of the live Audit Event write path
  (append-only writes must stay fast; reporting reads from a replica or scheduled export).

### 16.4 User stories
- **US-SEC-1 (P1)**: As a Compliance Officer, I generate a report of every user who accessed a
  specific application's data over a date range, sourced entirely from existing Audit Events.
  *Independent test*: seeded audit events → report reflects exactly those accesses.
- **US-SEC-2 (P2)**: As a Compliance Officer, I configure a retention policy that archives (not
  deletes) documents older than N years to cold storage, and confirm archived documents remain
  retrievable through the existing document API (transparently, from the caller's perspective).
- **US-SEC-3 (P2)**: As a Compliance Officer, I review the documented data-erasure procedure and
  confirm it correctly distinguishes what MUST be retained (audit/evidence, per financial
  recordkeeping law) from what CAN be erased (e.g. a portal account's non-audit profile data).

### 16.5 Domain model additions (as implemented — `mil.compliance`)
- **`DataRetentionPolicy`** — `id`, `tenantId`, `dataCategory` (`DOCUMENT`/`AUDIT_EVENT`/
  `NOTIFICATION_LOG`/etc.), `retentionPeriodDays`, `action` (`ARCHIVE`/`DELETE` — `DELETE` is
  disallowed for `AUDIT_EVENT`/`EVIDENCE` categories by both the domain factory
  (`DataRetentionPolicy.create`) and a database `CHECK` constraint — defense in depth, verified live
  against PostgreSQL, not code-review-asserted).
- **`ConsentRecord`** — `id`, `partyId` or `portalAccountId` (exactly one set, enforced by a
  database `CHECK` constraint), `consentType`, `consentTextVersion`, `grantedAt`, `withdrawnAt`
  (nullable).
- No `ComplianceReportRequest` — see this section's implementation-correction note above.

### 16.6 Database schema changes (as implemented — migration `0021_compliance.py`)
```sql
CREATE SCHEMA IF NOT EXISTS compliance;

CREATE TABLE compliance.data_retention_policies (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    data_category VARCHAR(50) NOT NULL,
    retention_period_days INT NOT NULL,
    action VARCHAR(20) NOT NULL,
    CHECK (NOT (data_category IN ('AUDIT_EVENT','EVIDENCE') AND action = 'DELETE'))
);

CREATE TABLE compliance.consent_records (
    id UUID PRIMARY KEY,
    party_id UUID REFERENCES core.parties(id),
    portal_account_id UUID REFERENCES portal.portal_accounts(id),
    consent_type VARCHAR(100) NOT NULL,
    consent_text_version VARCHAR(50) NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL,
    withdrawn_at TIMESTAMPTZ,
    CHECK (
        (party_id IS NOT NULL AND portal_account_id IS NULL) OR
        (party_id IS NULL AND portal_account_id IS NOT NULL)
    )
);
```
No `compliance_report_requests` table — see this section's implementation-correction note.

### 16.7 API contracts (as implemented)
- `GET /v1/compliance/retention-policies` — list this tenant's policies.
- `PUT /v1/compliance/retention-policies` — create/update a policy (body carries `dataCategory`,
  not a path parameter — matches every other Wave 2/3 write-endpoint convention in this codebase).
- `GET /v1/compliance/access-log?applicationId=&fromDate=&toDate=` — the FR-SEC-003 report,
  replacing the originally-specified `POST /v1/compliance/reports`/`GET .../reports/{id}` async
  pair (see this section's correction note).
- No separate `POST /v1/compliance/consent` endpoint — consent is recorded server-side, as a direct
  consequence of `PortalWorkspace.activate_account` (§12), not a client-callable endpoint; a
  borrower never explicitly "calls" a consent API, they activate their account and consent is
  recorded as part of that same transaction.
- Schemas live in the existing `mil.api.v1.schemas` module (no separate `compliance.yaml`).

### 16.8 RBAC changes (as implemented)
- New permission: `Permission.MANAGE_COMPLIANCE` — granted to `COMPLIANCE_OFFICER` (`ADMIN` already
  bypasses all permission checks via `Permission.ADMIN`).
- `Role.AUDIT_TEAM` (already exists) gains read access to compliance data (`READ_COMPLIANCE`,
  new permission) without gaining `MANAGE_COMPLIANCE` (read/write separation for the audit function
  itself — the audit team reviews, it doesn't configure policy).

### 16.9 AI considerations
- None directly — this module is policy/governance tooling. It does, however, formalize the
  enforcement of Principle V's AI-specific requirements (AI context isolation, least-data for
  prompts) as auditable configuration rather than only code-review-time discipline — e.g. a
  `DataRetentionPolicy` entry could apply to any future stored-prompt-log data.

### 16.10 Integration requirements
- Depends on §14's backup/archival infrastructure for the `ARCHIVE` retention action's actual
  storage tier.

### 16.11 UX considerations
- Compliance-facing screens (retention config, report requests) live in the Administration section
  alongside §15, not a separate app — one governance surface, RBAC-gated per screen.

### 16.12 Acceptance criteria
- Given a retention policy attempting `DELETE` on `AUDIT_EVENT`, then the write is rejected at the
  database constraint level, not only at the application layer.
- Given a compliance access-log report request, when generated, then it reflects exactly the Audit
  Events matching the requested application/date range.
- **Constitution check**: Principle V (retention, consent, access-report capabilities all present)
  ✅; Principle VIII (audit immutability is structurally protected — a DB CHECK constraint, not
  just a code path that could be bypassed) ✅; Principle XI (this module *is* the regulatory-
  alignment operationalization) ✅.

### 16.13 Risks
- **Erasure-vs-immutability tension** (named explicitly in FR-16.2's FR-SEC-005) is the single
  hardest legal/product question in this module — this spec resolves it at the *policy* level
  (audit/evidence are retained per financial recordkeeping law, superseding erasure requests for
  those categories) but the exact regulatory boundary MUST be confirmed with legal/compliance
  counsel for each deployment jurisdiction before this module ships — flagged, not silently assumed.
- **Retention policy misconfiguration**: an overly aggressive retention policy on `DOCUMENT` could
  archive a document an underwriter still needs mid-review — mitigate by excluding
  non-terminal-status applications' documents from any retention action, regardless of age.

### 16.14 Future extensibility
- Per-jurisdiction retention policy variants (different countries' regulatory minimums) are
  supported by `DataRetentionPolicy` already being tenant-scoped — a future multi-jurisdiction
  deployment adds rows, not schema.

---

## 17. Deployment Architecture

> **Wave 4 implementation correction (2026-07-12)**: this section's own scope ("Domain model
> additions: None... Database schema changes: None new... API contracts: None new... RBAC changes:
> None") is confirmed accurate and unchanged — this module is genuinely architecture/process, not
> application code, matching the user's own instruction ("do not introduce unnecessary
> infrastructure abstractions; build around the existing deployment model"). What Wave 4 added: a
> real migration-safety CI gate (`scripts/check_destructive_migrations.py`, wired into `.github/
> workflows/ci.yml`) satisfying FR-DEPLOY-005's "destructive migrations require explicit sign-off"
> requirement — a mechanical pattern check blocking `drop_table`/`drop_column`/`drop_constraint`/
> destructive-`ALTER COLUMN`/`DELETE FROM audit|finding|evidence` in a changed migration file unless
> a literal `# destructive-migration-approved` marker is present. `docs/deployment/README.md` was
> also corrected: it previously claimed neither `JobQueue` nor `EventBus` had a broker-backed
> implementation; direct inspection of `mil.kernel.container.build_container` found `JobQueue` is
> already Redis-backed in every environment (confirmed in §14's own correction note) — `EventBus`
> remains the actual, sole reason `_reject_in_process_messaging` refuses to start a non-development
> process today. Everything else in this section — Kubernetes topology, environment promotion,
> service-extraction candidacy, RLS/multi-tenancy retrofit risk — remains accurate as originally
> written and is not re-litigated here.

### 17.1 Business objectives
- Define how the now-17-module platform is actually deployed, scaled, and evolved beyond a single
  institution's single-region footprint — building on, not replacing, the existing "Modular
  Monolith" architectural decision documented in `specs/001-mil-platform-spec/plan.md` (justified
  there in detail: evidence-chain consistency, simpler audit-record assembly, still-stabilizing
  domain boundaries, smaller attack surface, enterprise on-premises deployment reality).

### 17.2 Functional requirements
- **FR-DEPLOY-001**: System MUST support deployment as a single-tenant, single-institution instance
  (the primary target per the existing plan) **and** document the path to multi-tenant hosting
  (shared infrastructure, tenant-isolated data — already anticipated by `TenantId` appearing
  throughout the domain model, e.g. §2, §5, §15, §16) without requiring a rewrite.
- **FR-DEPLOY-002**: System MUST support containerized deployment (Docker) with a defined
  Kubernetes (or equivalent orchestrator) topology: stateless API/worker pods scaling horizontally,
  a managed PostgreSQL instance, a managed/self-hosted message broker (§14), object storage.
- **FR-DEPLOY-003**: System MUST define environment promotion (dev → staging → production) with
  migration/schema-change gating — no schema change (any of §1–§16's proposed migrations) reaches
  production without passing through staging with real data-shape validation.
- **FR-DEPLOY-004**: The **first candidate for service extraction**, per the existing plan's own
  explicit note ("Document Processing... naturally asynchronous, CPU/memory-intensive, clearest
  service boundary"), MUST remain extractable without a domain-model change — this spec's modules
  must not introduce any new direct cross-module database access that would make that future
  extraction harder than it already is documented to be.
- **FR-DEPLOY-005**: System MUST define a CI/CD pipeline enforcing: the existing test suite (unit +
  contract + the Playwright E2E suite), `tsc`/ESLint/production build (frontend), and a
  migration-safety check (additive-only migrations flagged for review; destructive migrations
  require explicit sign-off) — building on the discipline already established informally during
  the MVP's RC1 stabilization pass (`tsc -b`/ESLint/build were only correctly wired to CI during
  that pass — this module makes that permanent and codified, not ad hoc).

### 17.3 Non-functional requirements
- Air-gapped/on-premises deployability (an existing, explicit constraint) MUST remain possible —
  every infrastructure choice in §14/§17 needs a non-SaaS, self-hosted equivalent path documented,
  even if a managed-cloud option is the default recommendation.
- Zero-downtime deployment for API/worker tiers (rolling deploys) — the frontend's existing
  non-optimistic-mutation discipline already tolerates brief backend unavailability gracefully
  (mutations surface real errors rather than silently failing), which this module should note as a
  favorable existing property, not something to re-engineer.

### 17.4 User stories
- **US-DEPLOY-1 (P1)**: As an Operations/Platform Engineer, I deploy the platform to a new
  institution's environment (on-premises or private cloud) using the documented topology, and every
  module in this spec functions correctly against real infrastructure (not just MSW-mocked
  frontend tests or dev-mode backend).
- **US-DEPLOY-2 (P1)**: As a Platform Engineer, I promote a schema migration through dev → staging
  → production and the pipeline blocks a destructive migration from reaching production without
  explicit sign-off.
- **US-DEPLOY-3 (P3)**: As an Architect, I extract Document Processing into an independent service
  in a future phase and confirm no other module's code required a change beyond its documented
  service-interface boundary.

### 17.5 Domain model additions
- None — this module is architecture/process, not domain model.

### 17.6 Database schema changes
- None new. Migration tooling/process (Alembic, already the existing choice per
  `specs/001-mil-platform-spec/plan.md`) gains a policy: additive-by-default, destructive changes
  require a documented, reviewed exception — a process control over the existing tool, not a new
  tool.

### 17.7 API contracts
- None new. This module governs how existing/proposed contracts are versioned and rolled out
  (Principle IX: breaking API changes must be versioned and communicated with lead time) — applies
  to every OpenAPI file proposed across §1–§16.

### 17.8 RBAC changes
- None at the application layer — deployment/infrastructure access control is governed by
  infrastructure IAM (consistent with §14.8's separation).

### 17.9 AI considerations
- None directly, beyond ensuring the LLM provider integration (Gemini, per the existing
  `gemini_inference.py`) remains swappable behind the existing provider abstraction at deployment
  time — a vendor-agnostic-core principle applied to AI infrastructure exactly as §2 applies it to
  LOS vendors.

### 17.10 Integration requirements
- Consolidates every external integration introduced across this spec: LOS adapters (§2), email
  provider (§13), secrets manager/broker/observability backend (§14) — this module is where their
  combined deployment topology is documented as one coherent picture, not 5 disconnected diagrams.

### 17.11 UX considerations
- None end-user-facing.

### 17.12 Acceptance criteria
- Given the documented Kubernetes topology, when deployed to a fresh environment, then all 17
  modules' health checks pass and the existing Playwright E2E suite passes against the real
  deployment (not only MSW-mocked mode).
- Given a destructive migration is proposed, when it reaches the CI gate, then it is blocked pending
  explicit sign-off, never auto-applied.
- **Constitution check**: Principle VI (vendor-agnostic, on-premises-capable) ✅; Principle IX
  (incremental evolution — modular monolith preserved, extraction remains possible, no premature
  microservices) ✅.

### 17.13 Risks
- **Multi-tenancy retrofit risk**: although `TenantId` already threads through the domain model,
  this spec has not implemented row-level security (RLS) enforcement at the database layer for
  every new table introduced across §1–§16 — each new table's tenant-scoping must be verified, not
  assumed, before any real multi-tenant deployment is attempted.
- **Migration volume**: §1–§16 collectively propose roughly a dozen new schemas/tables — sequencing
  and dependency ordering across modules (e.g. §1's `assignments` table depends on §15's
  `identity.users` being real, not just an ORM model) must be planned explicitly in the per-module
  `plan.md`/`tasks.md` that follow this spec, or migrations will fail on foreign-key dependencies.

### 17.14 Future extensibility
- Document Processing service extraction (already named as the first candidate in the existing
  plan) remains the leading candidate; this spec's own modules (§3 Policy, §8 Copilot) are
  secondary candidates for extraction once their read/write patterns are well-understood in
  production, per the existing plan's "extract only when scale demands it, never prematurely"
  discipline.

---

## Cross-cutting concerns (apply to all 17 modules)

### Module sequencing and dependencies
```
Foundational (build first, unblocks others):
  §15 Enterprise Administration  (identity.users must be real before §1, §2, §4 can FK to it)
  §14 Production Infrastructure  (broker/secrets/observability underpin every async module)

Second wave (depend only on the foundational layer):
  §2  LOS Integration Layer
  §3  Policy Engine              (extends existing PolicyPack/PolicyRule/PolicyResult)
  §4  Policy Administration      (depends on §3)
  §8  AI Case Copilot            (extends existing copilot/ domain layer)
  §9  Collaboration              (extends existing review/ domain layer)
  §13 Notification System        (many modules depend on it — build early, not last)

Third wave (depend on second-wave modules):
  §1  RM/Banker Workspace         (depends on §15 identity + assignment)
  §5  Borrower Identity Resolution
  §10 Operational Dashboard       (depends on §14's real job queue to have real metrics to show)
  §12 Customer Portal             (depends on §13 for invitations, §14 for a separate auth realm)
  §16 Security and Compliance     (reviews every schema from every other module)

Fourth wave (depend on third-wave modules):
  §6  Cross-Application Intelligence  (depends on §5)
  §7  Universal Search                (benefits from, but doesn't strictly require, §5/§6)
  §11 Business Analytics              (depends on §10's metric substrate, §3's exhaustive PolicyResult)
  §17 Deployment Architecture          (documents the whole system's final topology)
```

### Master domain entity additions (summary table)
| Entity | Module | Schema |
|---|---|---|
| `Assignment`, `AssignmentHistory` | §1 | `core` |
| `LOSConnection`, `LOSFieldMapping`, `LOSSyncEvent`, `LOSPushRequest` | §2 | `integration` |
| `PolicyRule.appliesTo` (column) | §3 | `policy` |
| `PolicyPackApproval`, `PolicyRuleChange` | §4 | `policy` |
| `BorrowerMasterRecord`, `BorrowerMasterRecordMember`, `IdentityMatchCandidate` | §5 | `identity_resolution` |
| `CrossApplicationSignal` | §6 | `core` |
| `SearchQueryLog` | §7 | `core` |
| *(none — existing `copilot` schema)* | §8 | `copilot` |
| `ReviewComment` additive columns | §9 | `review` |
| `OperationalMetricSnapshot` | §10 | `operational` |
| `ReportDefinition`, `ReportRun` | §11 | `operational` |
| `PortalAccount`, `DocumentChecklistItem` | §12 | `portal` / `core` |
| `NotificationEvent`, `NotificationPreference`, `NotificationDeliveryLog` | §13 | `notification` |
| *(infrastructure only, no entities)* | §14 | — |
| `TenantConfiguration`, `ApiKey`, `User.regionId` (column) | §15 | `identity` |
| `DataRetentionPolicy`, `ConsentRecord`, `ComplianceReportRequest` | §16 | `compliance` |
| *(architecture only, no entities)* | §17 | — |

### Master RBAC additions (summary table)
| Permission | Granted to (new or existing role) |
|---|---|
| `MANAGE_ASSIGNMENT` | `RELATIONSHIP_MANAGER`, `REGIONAL_MANAGER` (new role) |
| `MANAGE_INTEGRATION` *(existing, unused)* | `ADMIN` |
| `PUSH_LOS_STATUS` | `UNDERWRITER`, `RELATIONSHIP_MANAGER` |
| `READ_POLICY_RESULTS` | existing `READ_FINDINGS` role set |
| `DRAFT_POLICY_PACK` | `POLICY_ADMINISTRATOR` (new role) |
| `MANAGE_POLICY_PACKS` *(existing, unused)* | `COMPLIANCE_OFFICER` |
| `READ_CROSS_APPLICATION_IDENTITY`, `CONFIRM_IDENTITY_MATCH` | `UNDERWRITER`, `COMPLIANCE_OFFICER`, `RISK_ANALYST` |
| `QUERY_COPILOT` *(existing, unused)* | existing `READ_FINDINGS` role set |
| `COMMENT_ON_APPLICATION` | every role except `SERVICE_ACCOUNT` |
| `READ_OPERATIONAL` *(existing, unused)* | `OPERATIONS_MANAGER` |
| `READ_ANALYTICS`, `MANAGE_REPORTS` | `OPERATIONS_MANAGER`, `COMPLIANCE_OFFICER`, `ADMIN` |
| `MANAGE_CHECKLIST` | `UNDERWRITER`, `RELATIONSHIP_MANAGER` |
| *(portal auth is a separate, non-RBAC realm)* | — |
| *(notifications are identity-scoped, not role-scoped)* | — |
| *(infrastructure access is IAM, not application RBAC)* | — |
| `MANAGE_USERS`, `MANAGE_ROLES` *(existing, unused)* | `ADMIN` |
| `MANAGE_COMPLIANCE`, `READ_COMPLIANCE` | `COMPLIANCE_OFFICER`/`ADMIN`, `AUDIT_TEAM` |
| *(deployment access is IAM, not application RBAC)* | — |

New roles introduced across this spec: `Role.REGIONAL_MANAGER` (§1), `Role.POLICY_ADMINISTRATOR`
(§4). No existing role is removed or renamed. `Role.RELATIONSHIP_MANAGER`, `Role.RISK_ANALYST`,
and every existing role's current permission grant is preserved unchanged except for the additive
grants listed above.

### Non-goals (explicit, across the whole platform)
- No module in this spec grants any AI system the authority to approve, reject, or autonomously
  action a lending decision, a policy activation, an identity merge, or a compliance determination
  — every AI-adjacent capability (§3 policy evaluation, §5 identity matching, §6 signals, §8
  Copilot) is advisory, human-confirmed, and reversible before taking effect.
- No module replaces or weakens the existing Underwriter Workspace, AI pipeline, Evidence, Findings,
  Policy evaluation, Timeline, Audit, or Human Review — all are extended via new read paths, new
  events, or new adjacent entities, never rewritten.
- No module introduces a second, competing identity/auth system for internal staff — §12's Customer
  Portal is deliberately the only new, separate auth realm, and only because borrowers are
  genuinely external users.
- This spec does not select a specific message broker, secrets manager, email provider, or cloud
  vendor — those are deployment-time decisions within the architectural constraints this spec and
  the existing `specs/001-mil-platform-spec/plan.md` define.

### How this spec preserves every MVP principle
- **AI assists but never decides** — enforced per-module in every §*.9 (AI considerations) and
  re-checked in every §*.12 Constitution check against Principle I.
- **Human-in-the-loop** — every advisory AI output (§3, §5, §6, §8) requires explicit human
  confirmation before it has any effect; nothing auto-applies.
- **Explainability** — §5's match candidates and §6's cross-application signals are structurally
  required to carry the same five explainability fields as a `Finding` (Principle III), not a
  lighter-weight substitute.
- **Traceability & Auditability** — every module's Acceptance Criteria include a Constitution check
  against Principle VIII; new administrative, policy-authoring, and integration actions are all
  immutable Audit Events, matching the existing standard.
- **Enterprise-first architecture** — §14/§17 close the MVP's own documented production-readiness
  gap (broker-backed queue, redelivery, secrets management) rather than deferring it further.
- **Honest UX** — every module's UX considerations section carries forward the MVP's "never a
  generic error, always the real message" and "never fabricate a field the backend doesn't
  provide" discipline (explicit examples: §2's real sync error surfacing, §11's analytics-vs-audit
  disclosure, §16's retention/erasure documentation).
- **Extensibility** — every module's §*.14 (Future extensibility) names its next natural
  extension explicitly rather than over-building for it now, matching the MVP plan's own repeatedly
  demonstrated discipline of "note the seam, don't build it speculatively."

---

## Next steps

This spec is deliberately **not implemented**. Per standard workflow, the next steps are:

1. Review and sign-off on this spec (particularly §12 Customer Portal's expanded attack surface and
   §16's erasure-vs-immutability legal resolution, both flagged as needing dedicated review beyond
   normal engineering sign-off).
2. Run `/speckit-plan` against this spec, per module or per dependency-wave cluster (see the
   sequencing table above), to produce each module's `research.md`/`data-model.md`/`contracts/`/
   `quickstart.md` — this document intentionally stops short of that level of technical design
   detail, which belongs in the plan phase, not the spec phase.
3. Sequence delivery according to the dependency waves above; §15 (Enterprise Administration) and
   §14 (Production Infrastructure) should be planned and built first, since a majority of the
   remaining modules have a hard foreign-key or infrastructure dependency on them.
