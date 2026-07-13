# Phase 1 Data Model: Enterprise Platform — Wave 1

Entities below are additive to the existing `identity`/`policy`/`review` ORM models
(`src/mil/identity/models.py`, `src/mil/policy/models.py`, `src/mil/review/models.py`). Full field
lists and rationale are in `spec.md` §3.5/§4.5/§9.5/§15.5; this file states only the delta and
relationships needed to implement Wave 1's migrations.

## Identity (§15)

- `User` (existing) — add `region_id: UUID | None` (reserved for a later wave's
  `REGIONAL_MANAGER`; included now since it's a single additive column on a table Wave 1 already
  migrates, cheaper to add once).
- `TenantConfiguration` (new) — `id, tenant_id, config_key, config_value: JSONB, updated_by_user_id → User, updated_at`. Unique on `(tenant_id, config_key)`.
- `ApiKey` (new) — `id, tenant_id, name, hashed_key, scopes: text[], expires_at NOT NULL, revoked_at NULL, created_by_user_id → User, created_at`.

Relationships: `TenantConfiguration.updated_by_user_id` and `ApiKey.created_by_user_id` →
`identity.users.id`. No relationship to `core.applications` in this wave.

## Policy (§3, §4)

**Correction found during Wave 1 implementation** (verified against `src/mil/policy/models.py`/
`service.py`/migration `0007_policy_schema.py`): `PolicyPack` has **no `status` column at all** —
lifecycle is represented by a nullable `activated_at`/`deactivated_at` timestamp pair (draft =
both null; active = `activated_at` set, `deactivated_at` null; retired = both set), enforced by a
partial unique index (`activated_at IS NOT NULL AND deactivated_at IS NULL`) already in migration
0007. `PolicyService.create_pack`/`activate_pack`/`deactivate_pack`/`add_rule` **already exist and
already emit audit events** (`POLICY_PACK_CREATED`/`_ACTIVATED`/`_DEACTIVATED`/`POLICY_RULE_ADDED`).
The data-model addition below is corrected to layer maker-checker as a pure **gate in front of**
the existing `activate_pack()` call, not a new status enum replacing the existing representation.

- `PolicyRule` (existing) — add `applies_to: JSONB | None`.
- `PolicyPackApproval` (new) — `id, policy_pack_id → PolicyPack, requested_by_user_id → User, decided_by_user_id → User (nullable), decision: PENDING|APPROVED|REJECTED, reason, decided_at`. `CHECK (requested_by_user_id != decided_by_user_id)`. The API's `activate` endpoint calls the existing `PolicyService.activate_pack()` only after confirming an `APPROVED` `PolicyPackApproval` row exists for that pack — the gate lives in the new admin API/service layer, not in `PolicyPack` itself.
- `PolicyRuleChange` (new) — `id, policy_pack_id → PolicyPack, rule_id, change_type: ADDED|MODIFIED|REMOVED, previous_definition: JSONB, new_definition: JSONB, changed_at`.
- `PolicyResult` (existing) — no schema change; **behavioral** change only (write one row per
  evaluated rule per run, not only triggering rules — see spec FR-POL-002/003). Add supporting
  indexes: `(outcome)`, `(finding_id)`.

Relationships: `PolicyPackApproval`/`PolicyRuleChange` → `policy.policy_packs.id`.
One active `PolicyPack` per `jurisdiction`, enforced by a partial unique index.

## Review (§9)

- `ReviewComment` (existing) — add `mentioned_user_ids: UUID[]`, `edited_at: timestamptz | None`,
  `deleted_at: timestamptz | None`. Verify the existing table's actual column set at
  implementation time (this spec assumes an `application_id`-scoped table per §0's ground truth;
  confirm before writing the migration).

Relationships: `ReviewComment.application_id → core.applications.id` (existing, assumed).
`mentioned_user_ids` elements → `identity.users.id` (soft reference, no FK — an array column
cannot carry a per-element FK in PostgreSQL without a join table; acceptable here since mentions
are informational, not a referential-integrity-critical relationship).

## Copilot (§8)

No schema change. Existing `CopilotSession`/`CopilotQuery`/`CopilotResponse` are consumed as-is by
the new frontend.

## Validation rules carried over from spec.md (not repeated in full here)

- `PolicyPackApproval`: rejection requires a non-empty `reason` (mirrors the existing
  Override/Escalate mandatory-reason convention in `src/mil/review/service.py`).
- `ApiKey.expires_at` is NOT NULL — no default "unscoped/unexpiring" key may be created.
- `PolicyRule.applies_to`, when present, must validate against a fixed JSON-schema (document/party
  type scoping only) at write time — not an arbitrary predicate DSL.

## State transitions

`PolicyPack.status`: `DRAFT → PENDING_APPROVAL → (ACTIVE | REJECTED)`; `ACTIVE → RETIRED` (only via
a new pack's activation superseding it in the same jurisdiction). `REJECTED → DRAFT` is allowed
(revise and resubmit); no other transition is valid — enforce via the existing
`_VALID_TRANSITIONS`-style guard pattern already used on `MortgageApplication`.

`PolicyPackApproval.decision`: `PENDING → (APPROVED | REJECTED)`, terminal once decided — a new
approval cycle is a new `PolicyPackApproval` row, never a re-opened one (append-only, consistent
with Evidence/Audit immutability elsewhere in the platform).
