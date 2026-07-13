# Phase 0 Research: Enterprise Platform — Wave 1

## R1: What is the actual migration state of `identity`/`policy`/`review`/`copilot` schemas?

- **Decision**: Treat "ORM model exists" and "table exists in the deployed database" as two
  separate facts. Before writing any new route, run `alembic history`/`alembic current` against a
  real dev database and diff against `Base.metadata` for each of the four packages.
- **Rationale**: The spec's own ground-truth audit found Copilot's backend "exists" in every sense
  including being mounted — but the same confident-sounding "the ORM model exists" phrasing was
  nearly applied uncritically to `identity`/`policy`/`review` too. The one correction made during
  planning (Copilot was previously understated) is exactly the kind of error this check prevents
  in the other direction — assuming a table is migrated when only the Python class exists.
- **Alternatives considered**: Assume all four are equally unmigrated (rejected — contradicted by
  direct inspection of `src/main.py`, which already mounts Copilot); assume all four are equally
  migrated (rejected — no route/migration evidence found for the other three).

## R2: Maker-checker enforcement point for Policy Administration

- **Decision**: Enforce `requestedByUserId != decidedByUserId` at both the DB constraint level
  (`CHECK`) and the service layer (defense in depth), matching the existing codebase convention
  where domain invariants live on the aggregate/service and are backed by a DB constraint as a
  second line of defense (`MortgageApplication`'s own state-machine invariants follow this pattern).
- **Rationale**: A pure application-layer check is bypassable by a direct DB write or a future
  second code path; the existing codebase already trusts DB constraints for exactly this class of
  invariant (see `core.applications` status transition guards).
- **Alternatives considered**: Application-layer-only check (rejected — weaker, inconsistent with
  existing convention); a full workflow-engine dependency (rejected — Principle IX, no new
  infrastructure for a two-state approval gate).

## R3: Where does the Copilot frontend panel live?

- **Decision**: A collapsible panel inside `ApplicationWorkspace.tsx`, following the exact
  `DocumentInspector` split-panel precedent already built (per the prior UI plan's Phase 8) —
  reuse the pattern, not a new route.
- **Rationale**: Keeps the application always in view; avoids inventing a second navigation
  paradigm for a feature that is fundamentally "ask a question about the thing I'm already
  looking at."
- **Alternatives considered**: A dedicated `/applications/$id/copilot` route (rejected — breaks
  the "always see the application" property every other region preserves); a floating widget
  (rejected — inconsistent with the existing design system's panel/region vocabulary).

## R4: RBAC permission granularity for Administration

- **Decision**: Reuse the existing, already-declared-but-unused `Permission.MANAGE_USERS`/
  `MANAGE_ROLES` constants in `src/mil/kernel/security.py` rather than inventing new ones.
- **Rationale**: They already exist specifically for this purpose (per the module's own
  docstring listing them as part of "Identity & administration") — using them is the literal
  "wire it in, don't rebuild it" instruction for this wave.
- **Alternatives considered**: A single coarse `MANAGE_ADMIN` permission (rejected — the existing
  constants are already correctly grained; introducing a coarser one would be a regression).

## R5: Comment reference-target validation for Collaboration

- **Decision**: A `ReviewComment.referenceId` (Finding/Document/Evidence) is validated server-side
  against the same application's own data at write time (existence + application-scope check), not
  merely accepted as an opaque UUID.
- **Rationale**: Prevents a comment from referencing a resource on a different application (a
  cross-application data leak vector structurally similar to what `abac.py`'s
  `CrossApplicationDenialPolicy` already guards against elsewhere).
- **Alternatives considered**: Trust the client to only ever send a same-application reference
  (rejected — server-side validation is required wherever a resource boundary is security-relevant,
  per the existing ABAC discipline).

All NEEDS CLARIFICATION items from the plan template are resolved above; none remain open.
