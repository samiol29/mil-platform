# Implementation Plan: Enterprise Platform — Wave 1

**Branch**: `feature/v2-roadmap` | **Date**: 2026-07-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification `specs/005-enterprise-platform/spec.md`, scoped to the five
modules approved for Wave 1: §15 Enterprise Administration, §3 Policy Engine, §4 Policy
Administration, §8 AI Case Copilot, §9 Collaboration.

**Sequencing** (per user decision): implement one module fully end-to-end, verified, before
starting the next. Order: **Enterprise Administration → Policy Engine + Policy Administration →
AI Case Copilot → Collaboration.** Enterprise Administration is first because `identity.users`
must be a real, migrated, routed table before Policy Administration's maker-checker approver
checks, Collaboration's mention resolution, and Assignment (a later wave) can hold real foreign
keys to it.

---

## Summary

Wave 1 wires four backend bounded contexts that already have real domain models/services
(`policy`, `identity`, `copilot`, `review`) onto real HTTP APIs, migrations, RBAC, and — for the
three that need one — a frontend, without touching the existing Underwriter Workspace, AI
pipeline, Evidence/Finding/Audit/Human-Review code. A pre-implementation audit (§0 of the spec,
corrected during this planning pass) found:

- **`copilot`**: backend + API + contract + router registration **already fully exist and are
  live** in `src/main.py`. Wave 1 work here is **frontend only**.
- **`policy`**: `PolicyPack`/`PolicyRule`/`PolicyResult` ORM models + `PolicyService` +
  `PolicyRepository` exist; no API route, no migration confirmed applied, no frontend. Wave 1 adds
  the route, the exhaustive per-rule result recording (spec FR-POL-002/003), the maker-checker
  authoring workflow (§4), and a frontend Policy Administration screen plus extension of the
  existing (already-shipped) reviewer-facing Policy region.
- **`identity`**: `User`/`Role`/`RoleAssignment` ORM models + `rbac.py`/`abac.py` exist; no API
  route, no migration confirmed applied, no frontend. Wave 1 adds the route and a frontend
  Administration screen.
- **`review`**: `ReviewComment` model + `add_comment()` exist; no API route, no frontend. Wave 1
  adds the route and a frontend Collaboration panel.

## Technical Context

**Language/Version**: Python 3.12+ (backend, matching `specs/001-mil-platform-spec/plan.md`
unchanged), TypeScript/React (frontend, matching the existing `frontend/` app unchanged).

**Primary Dependencies**: FastAPI, SQLAlchemy, Pydantic, Alembic (backend — all already in use,
no new dependency introduced by Wave 1); TanStack Router/Query, Zustand, the existing
`design-system/` component library (frontend — no new dependency).

**Storage**: PostgreSQL, existing `policy`/`identity`/`copilot`/`review` schemas — this wave adds
migrations to schemas that already exist as ORM models but have not been confirmed migrated;
first implementation step for each module is verifying/creating the Alembic migration.

**Testing**: pytest (backend, existing convention — colocated `tests/unit/`, contract tests
against the OpenAPI schema); Vitest + Storybook/axe-core (frontend, existing convention).

**Target Platform**: unchanged — the existing containerized Linux deployment target.

**Project Type**: Web application (backend API + frontend), matching Option 2 below.

**Performance Goals**: interactive endpoints p95 < 300ms (matches the existing platform target);
Copilot query latency is LLM-round-trip-bound and explicitly exempted from that target (spec §8.3).

**Constraints**: no existing contract, table, or UI may be altered destructively (spec §0); every
new permission/role is additive to `src/mil/kernel/security.py`'s existing `ROLE_PERMISSIONS` map;
every mutating action must emit an Audit Event per Principle VIII.

**Scale/Scope**: four bounded contexts, ~5 new/extended API route modules, ~4 Alembic migrations,
~3 new frontend feature areas (Administration, Policy Administration + Policy region extension,
Copilot panel, Collaboration panel).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Human Decision Authority | Copilot remains query-only (no writer adapters added); Policy evaluation remains rule-based, not a decision; identity/comment actions are human-initiated | ✅ PASS |
| II. Evidence First | No change to Evidence provenance; Policy per-rule results reference existing Evidence-backed Findings | ✅ PASS |
| III. Explainability by Default | Copilot answers carry mandatory citations (existing `citations.py` discipline preserved) | ✅ PASS |
| IV. Trust Before Automation | No new automation; Policy Administration adds a *stricter* human gate (maker-checker) than exists today | ✅ PASS |
| V. Security and Privacy by Design | New RBAC permissions are least-privilege scoped; identity module reuses existing `abac.py` tenant isolation | ✅ PASS |
| VI. API-First Integration | All new capability is API-first, versioned under `/v1/` | ✅ PASS |
| VII. Domain-Driven Design | No new entity invents a generic abstraction — `PolicyPackApproval`, `PolicyRuleChange` extend the existing Policy domain; `TenantConfiguration`/`ApiKey` extend Identity | ✅ PASS |
| VIII. Auditability | Policy pack draft/approve/reject/activate, role grant/revoke, and (informally, per spec §9.2) comment post are all either full Audit Events or explicitly scoped as lighter-weight discussion, matching spec's own distinction | ✅ PASS |
| IX. Incremental Evolution | Every change is additive to an existing bounded context; no rewrite | ✅ PASS |
| X. Operational Excellence | Out of scope for Wave 1 (§10/§11 are Wave 3 per spec's sequencing table) — no regression | ✅ PASS (N/A) |
| XI. Regulatory Alignment | Policy maker-checker directly strengthens regulatory alignment vs. today's no-approval-gate state | ✅ PASS |
| XII. Deterministic Intelligence | Policy evaluation stays deterministic; Copilot response attribution (model/prompt version) preserved unchanged | ✅ PASS |

**GATE RESULT: ALL PRINCIPLES PASS. Proceed.**

## Project Structure

### Documentation (this feature)

```text
specs/005-enterprise-platform/
├── spec.md               # Master spec (all 17 modules)
├── plan.md               # This file — Wave 1 plan
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   ├── administration.yaml
│   ├── policy.yaml
│   ├── policy-administration.yaml
│   ├── collaboration.yaml
│   └── copilot.yaml      # Already exists (specs/001-mil-platform-spec/contracts/copilot.yaml) — referenced, not duplicated
└── tasks.md               # Phase 2 output (/speckit-tasks) — implementation proceeds module-by-module per the sequencing above
```

### Source Code (repository root)

```text
src/mil/
├── identity/              # EXISTS — models.py, rbac.py, abac.py, dev_seed.py; ADD: no new package
├── policy/                # EXISTS — models.py, service.py, repository.py; ADD: no new package
├── review/                # EXISTS — ReviewComment model; ADD: no new package
├── copilot/                # EXISTS, fully wired; NO backend changes in Wave 1
└── api/v1/
    ├── admin.py            # NEW — Enterprise Administration routes
    ├── policy.py           # NEW — Policy Engine + Policy Administration routes
    └── comments.py         # NEW — Collaboration routes

alembic/versions/           # NEW migrations: identity tables, policy additive columns/tables,
                             # review additive columns — verify existing tables' migration state
                             # first; do not assume "model exists" implies "table exists in DB"

frontend/src/
├── entities/
│   ├── admin/              # NEW — users, roles, tenant-config queries
│   ├── policy/             # NEW — policy pack, policy result queries
│   ├── copilot/            # NEW — copilot query/session queries
│   └── comment/            # NEW — collaboration queries
├── features/
│   ├── administration/     # NEW — user/role management screens
│   ├── policy-administration/  # NEW — draft/diff/approve authoring UI
│   ├── application-workspace/   # EXTEND — Policy region gets rule-level breakdown;
│   │                              # NEW Copilot panel; NEW Collaboration panel
routes/
├── admin.*.tsx              # NEW
├── policy-administration.*.tsx   # NEW
```

**Structure Decision**: Web application (Option 2) — unchanged from the existing MVP. No new
top-level project. All Wave 1 additions are new files inside the existing `src/mil/`,
`src/mil/api/v1/`, and `frontend/src/` trees, plus new Alembic migrations.

## Complexity Tracking

No constitution violations requiring justification. No new project/service/repository pattern is
introduced beyond what the existing modular monolith already uses.
