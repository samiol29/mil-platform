# Implementation Plan: MIL Frontend — Underwriter Workspace

**Branch**: `002-underwriter-workspace` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-underwriter-workspace/spec.md`, governed jointly with `specs/003-design-system/spec.md` and informed by `specs/004-evidence-based-product-research/spec.md`.

**Governing precedence** (as instructed): 003 (Design System) > 002 (Underwriter Workspace) > 004 (Research). In practice, no material conflict was found between the three documents during this planning pass — 004 was authored to ground and justify decisions already reflected in 002 and 003, not to compete with them. Where this plan makes an implementation-technology choice 004's research specifically informs (e.g., SSE over WebSockets, PDF.js over a commercial SDK, TanStack ecosystem consistency), that choice sits entirely within the implementation-technology space 002/003 deliberately left unspecified (both explicitly forbid naming a framework or library) — see `research.md` for the one genuinely close call (TanStack Router vs. React Router) flagged as debatable rather than a clear best-in-class win.

---

## Summary

Build a TypeScript/React single-page application, served from the same origin as the existing FastAPI backend, that implements the Underwriter Workspace (002) exactly as specified, using only the Design System's (003) closed token/component vocabulary, validated against the enterprise UX evidence base (004). The plan's central engineering findings are: (1) the backend's domain logic for Evidence and Finding exists but is not yet exposed via HTTP — a defined, additive set of new endpoints is required before the core review workflow (User Story 1) can be built at all (see `contracts/api-gaps.md`); (2) the two hardest, genuinely novel engineering problems are PDF evidence-highlighting (no library solves this out of the box) and virtualized-table performance at 100,000+ rows — both are named explicitly as risks with dedicated mitigation, not assumed to be solved by library selection alone.

## Technical Context

**Language/Version**: TypeScript 5.x (strict mode), targeting evergreen browsers (see Non-Functional Requirements, spec 002)

**Primary Dependencies**: React 19, TanStack Router, TanStack Query, TanStack Table, TanStack Virtual, React Hook Form, Zod, Zustand — full rationale in `research.md`

**Storage**: N/A on the client beyond TanStack Query's in-memory cache and `localStorage` for non-sensitive UI preferences only (theme, panel widths) — no application, evidence, or finding data is persisted client-side beyond the active session's query cache (Constitution Principle V, least-data/data-minimization)

**Testing**: Vitest + React Testing Library (unit/component), Playwright + axe-core (E2E, accessibility) — see `research.md`

**Target Platform**: Evergreen desktop browsers (Chrome, Edge, Firefox, Safari), laptop-minimum viewport (002 Assumptions)

**Project Type**: Web application — existing FastAPI backend (unchanged in architecture) + new frontend SPA, replacing the legacy `frontend/` scaffold

**Performance Goals**: Per 002 Success Criteria — sub-2s search/open at 100,000+ applications, sub-100ms interaction latency, sub-1s filtered results at scale; see Performance Budgets below for the frontend-specific numeric targets that satisfy these

**Constraints**: WCAG 2.1 AA (003 FR-067); zero backend contract changes to existing endpoints (governing instruction); no client-side computation of audit-relevant state (Constitution Principle VIII)

**Scale/Scope**: 100,000+ applications, thousands of evidence items per application, hundreds of documents per application (002 Non-Functional Requirements)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — no changes required; PASS both times.*

| Principle | Compliance |
|---|---|
| I. Human Decision Authority | No client-side code path ever advances application/finding state without an explicit, confirmed human action (data-model.md: Verification/Override state transition rule) |
| II. Evidence First | PDF highlight-overlay architecture and evidence-chip pattern make every AI claim one action from its source (Evidence Explorer & Document Viewer Architecture, below) |
| III. Explainability by Default | Finding rendering is type-gated on all five explainability fields being present (data-model.md: Finding entity) — a partial Finding cannot compile-time-satisfy the render component's required props |
| IV. Trust Before Automation | No automation beyond what 002 specifies is introduced; optimistic UI is selectively, not universally, applied (research.md: TanStack Query) |
| V. Security & Privacy by Design | Auth flow uses PKCE + in-memory token + httpOnly refresh cookie (Authentication Flow, below); Copilot requests are constructed only from the active application's data (data-model.md: Copilot Session) |
| VI. API-First Integration | Frontend consumes the existing API surface unchanged; all additions are new, additive routes (contracts/api-gaps.md) |
| VII. Domain-Driven Design | Frontend type names match backend/domain entity names exactly (data-model.md: Naming Rule) |
| VIII. Auditability | Audit Trail Entry (mapping 1:1 to the backend's `AuditEvent` record — see data-model.md's Naming Rule) and Verification/Override types expose no update/delete affordance at the type level, not just the UI level (data-model.md) |
| IX. Incremental Evolution | All required backend additions are purely additive (contracts/api-gaps.md); frontend delivery itself is sequenced by the Workspace spec's own prioritized user stories |
| X. Operational Excellence | Client-side structured error/performance telemetry included (Observability, below) |
| XI. Regulatory Alignment | No feature in this plan reduces explainability or traceability versus what 002/003 specify |
| XII. Deterministic Intelligence | Model/prompt/policy version fields are carried through every cache layer untransformed (data-model.md: Finding, Copilot Message) |

No violations requiring Complexity Tracking were identified.

## Project Structure

### Documentation (this feature)

```text
specs/002-underwriter-workspace/
├── spec.md                     # Feature specification (already authored)
├── plan.md                     # This file
├── research.md                 # Phase 0 — technology decisions
├── data-model.md               # Phase 1 — frontend entity/state shapes
├── contracts/
│   ├── existing-api-surface.md # What the backend already exposes
│   └── api-gaps.md             # Required, additive backend endpoints
├── quickstart.md               # Phase 1 — architecture validation guide
└── tasks.md                    # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

**Structure Decision**: Option 2 (web application: separate backend/frontend), matching the repository's existing top-level layout. The legacy `frontend/` directory is replaced in place — same path, entirely new internal structure — per the project decision to treat it as obsolete scaffolding rather than a foundation to extend.

```text
src/                        # Existing FastAPI backend — unchanged by this plan
tests/                      # Existing backend tests — unchanged by this plan

frontend/
├── src/
│   ├── app/                # Router configuration, root providers (Query client, theme, auth)
│   ├── design-system/      # Implementation of spec 003 — tokens, primitives, closed component set
│   │   ├── tokens/         # Primitive + semantic token definitions (colors, type, spacing, elevation, motion)
│   │   └── components/     # The closed set: Button, Table, Drawer, Dialog, EvidenceChip, ConfidenceIndicator, etc.
│   ├── entities/            # One folder per domain entity (application, document, evidence, finding, copilot,
│   │                          notification, saved-view, audit) — each owns its types, API client functions,
│   │                          and TanStack Query hooks; mirrors data-model.md exactly
│   ├── features/            # One folder per Workspace user-facing capability (application-queue,
│   │                          application-workspace, document-viewer, evidence-explorer, copilot-panel,
│   │                          knowledge-graph, search, notifications) — composes entities + design-system
│   │                          components; no feature imports another feature directly (see Component
│   │                          Architecture, below)
│   ├── routes/              # TanStack Router route tree (thin — composes features, owns URL param/search parsing)
│   ├── shared/              # Cross-cutting, non-domain utilities (formatting, accessibility helpers, telemetry)
│   └── test/                # Shared test setup (RTL config, MSW handlers for contract-shaped mocks)
├── .storybook/
├── e2e/                     # Playwright specs
└── vite.config.ts
```

**Why `entities/` and `features/` are separate**: this is the direct structural expression of Constitution Principle VII (domain-driven naming) plus 004's repeated finding that configurability/growth without a forcing function toward consistency is the most common enterprise-UX failure mode. `entities/` is intentionally boring and rule-following (mirrors `data-model.md`); `features/` is where product behavior lives. A `feature` may depend on any number of `entities` and on `design-system`, but never on another `feature` — this is the one structural rule most responsible for preventing the kind of cross-cutting inconsistency 004 documents in Salesforce/Atlassian/ServiceNow.

**Entity sub-modules are permitted for a single reason**: where an entity's query surface splits into genuinely distinct concerns (e.g., `entities/finding/queries.ts` for the Finding record itself versus `entities/finding/relationships.ts` for its Knowledge Graph relationship edges — a different backend endpoint, a different response shape, and a different consuming feature), a same-folder sub-module is allowed. This is not a license for arbitrary fragmentation: a sub-module is justified only when it corresponds to a distinct endpoint and a distinct concern, not merely to keep an individual file shorter.

## Overall Frontend Architecture

A single-page application, server-rendering not required (the backend is a pure API; per Constitution Principle VI, MIL is an intelligence layer consumed via API, and the frontend is one such consumer, not a hybrid server). Three architectural layers, strictly one-directional in their dependencies:

1. **Design System layer** (`design-system/`) — implements spec 003 exactly; has no knowledge of mortgage domain concepts at all. A `ConfidenceIndicator` component takes a confidence band and renders it per 003's rules; it does not know what a "Finding" is.
2. **Entity layer** (`entities/`) — implements `data-model.md`; owns API communication (TanStack Query hooks) and domain types for exactly one entity each; has no knowledge of any specific screen or workflow.
3. **Feature layer** (`features/`) — implements spec 002's actual screens and workflows by composing entity hooks and design-system components; this is the only layer that knows what "the Application Workspace" or "the Evidence Explorer" is.

This layering is the direct architectural answer to 004's central cross-product lesson (Cross-Product Comparisons: "why enterprise CRMs often feel slow" — configurability without a forcing function toward consistency): a strict, one-directional dependency rule between layers is the forcing function.

## Routing Strategy

TanStack Router (see `research.md`), file-based route tree under `routes/`. URL is the source of truth for anything a user should be able to bookmark, share, or return to via the back button: the active application, the active document/page, the active filter/sort/saved-view, and the active tab within the Application Workspace (overview/findings/evidence/documents/Copilot — 002 FR-029). Route loaders prefetch via TanStack Query before a route renders, so navigating to a deep link and navigating via the queue produce an identical, prefetched experience (satisfying 002 FR-005's deep-linking requirement structurally, not as an afterthought).

## State Management

Three explicit tiers, no overlap permitted between them (see `research.md` for the tooling and full rationale):

1. **Server state** (TanStack Query) — everything that originates from the backend: applications, documents, evidence, findings, Copilot sessions, notifications, saved views, audit entries.
2. **URL state** (the router) — anything shareable/bookmarkable: active filters, sort, active record, active tab.
3. **Ephemeral UI state** (Zustand + local component state) — command palette open/closed, transient panel expand/collapse, in-progress (unsaved) form input.

A concrete rule preventing drift: **no entity in `data-model.md` may ever be held in Zustand or component state as its source of truth** — if it came from the server, TanStack Query owns it, full stop. This single rule is the practical enforcement of the "server is always the source of truth" principle already stated in 002.

## Server State & API Integration Strategy

Every entity's TanStack Query hook set lives in its `entities/<name>/` folder and is the *only* place that constructs a request to that entity's endpoints — no feature component calls `fetch`/`axios` directly. Response shapes are parsed through a Zod schema at the entity layer (research.md), so a backend contract change (even an unintentional one) fails loudly, at the API boundary, in development and in CI contract tests — never silently, deep inside a feature component.

Freshness policy (per entity, matching `data-model.md`'s per-entity caching tier):

| Tier | `staleTime` behavior | Example entities |
|---|---|---|
| Audit-critical | Explicit staleness check before any mutation; background refetch never silently overwrites data mid-review | Application (when open for review), EvidenceItem, Finding |
| Informational | Short `staleTime`, background refetch permitted freely | Application (queue row), Document (while ingesting) |
| Long-lived | Long/effectively infinite `staleTime` | Document (once completed/failed), Audit Trail Entry |
| Preference | Optimistic mutation, `staleTime` irrelevant | Saved View, Notification `readAt` |

## Authentication Flow

Today, the only implemented `IdentityProvider` is `DevBearerIdentityProvider` (dev-only, per `contracts/existing-api-surface.md`); a production, signature-verifying provider is a known, pre-existing backend gap this plan does not resolve. The frontend is built against an **abstracted auth interface** so the eventual swap is contained:

- Token acquisition and attachment live behind a single module (`app/auth`), never called directly by feature code — every API call goes through one HTTP client instance that attaches the current token.
- **Recommended target flow** (once the backend ships a real provider): Authorization Code + PKCE, no client secret in the frontend. Access token held **in memory only** (not `localStorage`/`sessionStorage`, to reduce the impact of an XSS-class vulnerability — a stolen in-memory token dies with the tab); silent refresh via a short-lived, httpOnly, `SameSite=Strict` refresh cookie issued by the backend, scoped to the same origin as the API (see Deployment Strategy — this is precisely why same-origin deployment is recommended, not merely convenient: cross-origin cookie handling for refresh tokens is measurably riskier and more complex).
- **Refresh-cookie backend dependency (now explicitly scoped)**: issuing and validating the httpOnly refresh cookie is backend work that did not previously appear in `contracts/api-gaps.md` — it now does (see that document's Authentication section). This is a pre-production-cutover dependency; it does not block Setup/Foundational/US1–US6, all of which are built against the existing dev-bearer flow behind the same auth abstraction.
- **CSRF mitigation**: because the refresh mechanism relies on a cookie, every state-changing request (POST/PATCH/DELETE) additionally requires a double-submit CSRF token (a value the frontend reads from a non-httpOnly cookie and echoes back as a request header) — `SameSite=Strict` alone reduces but does not eliminate CSRF risk (e.g., it does not protect against same-site script-based misuse), so the two mechanisms are used together, not as alternatives. This is scoped as backend work alongside the refresh-cookie endpoint.
- Until the real provider ships, the dev flow is used as-is behind the same abstraction, so no feature code changes when the swap happens.

## Error Boundaries

Three tiers, each catching failures at the granularity 002 FR-083 requires ("a partial failure must be represented at the granularity of the failure"):

1. **Root boundary** — catches a truly unrecoverable error (e.g., the design-system provider itself fails to initialize); renders a full-screen, plain-language failure state with a reload action.
2. **Route boundary** — catches a failure loading a specific route's data (e.g., an application that fails to load); the surrounding app shell (navigation, command palette) remains usable.
3. **Panel boundary** — wraps each independently-loaded region within the Application Workspace (Copilot panel, Evidence Explorer, Knowledge Graph view) so, e.g., a Copilot failure never blanks the Findings view next to it.

## Loading Architecture

A single, shared `<LoadingState>` / `<SkeletonState>` pair from the design system, used by every entity hook's loading state — never a bespoke spinner per feature (003 FR-042–043). Skeletons are shaped to match the eventual content (a queue-row skeleton is row-shaped, a finding skeleton is finding-card-shaped) wherever the shape is known ahead of time, per 003's explicit skeleton-vs-spinner distinction. The 100ms threshold (002 FR-081) is enforced by a shared hook wrapping TanStack Query's `isFetching` state with a debounce, so a fast, cache-hit response never flashes a loading state at all.

## Component Architecture

The design system (003) defines the closed component vocabulary; this plan's job is enforcing that it stays closed. Concretely:

- Every component in `design-system/components/` is documented in Storybook with every state defined in 003 (default/hover/focus/active/disabled/loading/error, plus domain states like "AI-generated"/"overridden") before it may be used in a feature.
- Feature code may compose design-system components and entity hooks; it may not define new visual primitives (a new button style, a new color) — if a feature needs something the design system doesn't yet provide, that is a design-system change proposed through 003's own Future Extensibility process, not a local, one-off addition.
- This is enforced both procedurally (code review checklist referencing 003) and, where feasible, mechanically (lint rule flagging raw color/spacing values outside the token module).

## Design System Integration

`design-system/tokens/` is the single source of truth for every primitive and semantic value defined structurally (not with literal values) in spec 003 — the literal value palette (specific hex codes, specific rem values) is produced once, here, during implementation, exactly as 003's own Assumptions anticipate. Both light and dark themes are implemented from day one (003 FR-028), not retrofitted. Every token is exposed as a typed export (`theme.color.status.atRisk`, not a raw string), so a component referencing a nonexistent or misspelled token fails at compile time.

## PDF Viewer / Document Viewer Architecture

Built on PDF.js (`research.md`). Three layers:

1. **Rendering layer** — PDF.js canvas rendering, virtualized by page (only the visible page ± a small buffer is rendered, per 002 FR-038's "first page usable before the rest loads" requirement).
2. **Coordinate-mapping layer** — the genuinely novel engineering work (see Risks & Mitigations): maps an `EvidenceItem`'s stored provenance (page, field location) into PDF.js's rendered coordinate space, correct across zoom level and page rotation, to draw the highlight overlay (002 FR-040, 003 FR-058).
3. **Navigation layer** — page jump, zoom, pinned-vs-preview tabs for multiple open documents (002 FR-042, FR-044).

## Evidence Explorer Architecture

A selection-scoped side panel (per Figma's researched panel discipline, 004) — never a permanently-visible, ever-growing panel of every possible context (rejecting the Salesforce/ServiceNow anti-pattern documented in 004). Selecting an evidence item shows only that item's relationships (supports/conflicts-with/derived-from); it does not eagerly render the full relationship set for every evidence item on the application. Conflict pairs (002 FR-047) render both conflicting items simultaneously in the same panel, never requiring the reviewer to hold one value in memory while navigating to see the other.

## Copilot Architecture

A panel anchored to, and only reachable from within, the currently open Application Workspace (002 FR-056, FR-062; 004 Design Decision: no global chat destination) — architecturally, the Copilot panel component's props require an `applicationId`; there is no route or component composition that can render it without one. Responses stream via SSE (`research.md`) into a progressively-rendered message; citations are individually actionable links resolved through the same entity-layer hooks used by the Evidence Explorer (no duplicate citation-resolution logic). An `insufficientEvidence` response state is a distinct rendering path from a grounded answer, per `data-model.md`.

**Citation clickability during streaming**: a citation becomes individually clickable as soon as it appears in the streamed response, not only once the full message has finished streaming — this follows directly from the "one action" principle already established for citations (002 FR-058) and from the general rule that streaming must never make the interface *less* capable than a fully-loaded state, only progressively *more* complete.

## Knowledge Graph Architecture

An on-demand, secondary investigative view (002 FR-067) — never part of the primary review path, and never eagerly loaded. Below a defined node-count legibility ceiling, a lightweight graph-layout rendering is used; at or above that ceiling, the same relationship data renders as the structured list-based fallback required by 002 FR-065. Given this is the lowest-priority, most optional feature in the entire plan (both specs and research agree on this), the specific graph-rendering library is deliberately left as an implementation-time decision rather than committed to now — the architectural commitment made here is only the ceiling-triggered fallback behavior itself, which is the part that must not be skipped.

**Legibility ceiling**: set at **50 nodes** (evidence items + findings combined, for a given relationship query) as the initial working threshold. This number is a placeholder deliberately chosen to be low enough to be safe, not derived from a usability study — it is expected to be revisited after the first round of manual usability testing against real seeded relationship data (see `quickstart.md`), and any change to it is a design-system-level tuning decision, not a re-architecture.

## Search Architecture

The frontend issues one structured query (matching against borrower name, loan number, and LOS reference simultaneously — never a per-field selector the user must operate) to the backend search endpoint defined in `contracts/api-gaps.md`, debounced client-side, results rendered through the same virtualized table used by the default queue view — search is a filtered view of the queue, not a separate UI paradigm (consistent with 002 FR-014: an empty query shows the default newest-first queue).

**Ranking + cursor pagination strategy**: combining relevance-ranked results with cursor-based pagination is a known hard problem — a cursor built from rank alone is not stable, because rank is rarely unique, so naive rank-only cursors can duplicate or skip rows across pages. The backend endpoint (`contracts/api-gaps.md`) MUST use a **composite cursor**: `(rank, id)`, with `id` as a deterministic tie-breaker, so pagination remains stable and gap-free regardless of how many rows share a rank. This applies equally to the default newest-first ordering (`(lastActivityAt, id)`) and to any future sort column. This is a backend contract requirement, not a frontend concern — the frontend only ever passes back the opaque cursor it was given.

**Total-count-at-scale strategy**: FR-024 requires the total matching count always be visible. An exact `COUNT(*)` under an arbitrary filter combination at 100,000+ rows is a well-known Postgres performance trap. The backend endpoint should return a **planner-estimated count** by default (fast, always available) and fall back to an exact count only when the estimated count is below a threshold small enough for an exact count to be cheap (e.g., a few thousand rows) — the frontend renders whichever value it receives without needing to know which strategy produced it, so this is purely a backend-side optimization with no frontend contract impact.

## Table Virtualization

TanStack Table + TanStack Virtual (`research.md`), windowed row rendering, server-driven cursor pagination — the full 100,000+ row dataset is never fetched or held in memory at once, at any point, in any table in the product (Application Queue, Evidence Explorer list view, Audit Trail, Notifications). This is treated as an architectural invariant checked in Performance Budgets below, not an optimization applied only where convenient.

## Performance Budgets

Concrete, CI-checkable numbers translating 002's Success Criteria into frontend engineering targets:

| Budget | Target | Enforces |
|---|---|---|
| Initial JS payload (app shell, gzipped) | < 200KB | Fast first load; route-based code-splitting so PDF.js, table-virtualization, and (eventually) graph-rendering code load only when their route is visited |
| Time to first meaningful queue row | < 1s on a reference connection | 002 SC-002 |
| Application open → first finding + evidence visible | < 2s | 002 SC-003 |
| Search/filter round-trip at 100,000+ rows | < 1s (p95) | 002 SC-010 |
| Table scroll frame budget | ~16ms/frame (60fps) sustained during scroll | 002 FR-017 |
| Loading-state appearance | < 100ms after request start | 002 FR-081 |

These are enforced in CI via a synthetic large-dataset performance test and a bundle-size check that fails the build on regression — not left to manual spot-checking.

## Accessibility Strategy

Automated: Storybook `a11y` addon (every component, every defined state) + axe-core wired into the Playwright E2E suite (every primary user-flow page), both as hard CI gates (`research.md`). Manual: a keyboard-only pass and a screen-reader pass (NVDA and VoiceOver, at minimum) against every primary user story in 002, performed before each release, not only at initial launch. Both light and dark themes are checked independently for contrast (003 FR-029) — a theme is not considered complete until its own contrast audit passes, not inferred from the other theme's result.

## Testing Strategy

- **Unit/component** (Vitest + RTL): every entity hook, every design-system component in every defined state, every feature component's primary interaction paths. RTL's accessible-query-first API structurally discourages writing an inaccessible component (`research.md`).
- **Contract tests**: Zod-schema-parsed fixtures generated from the actual backend OpenAPI schema, so a backend response shape change is caught in CI before it reaches a running frontend.
- **E2E** (Playwright): the full set of Acceptance Scenarios already defined in 002's User Scenarios & Testing, run against the real docker-compose-provisioned backend — these are not new scenarios invented for this plan, they are the specification's own scenarios made executable.
- **Performance**: a synthetic 100,000+-row dataset E2E scenario asserting the Performance Budgets above.

## Component Documentation Strategy

Storybook is the living, browsable expression of spec 003 — every design-system component's full state matrix is demonstrated, every token is visually inspectable, and the `a11y` addon report is part of what a reviewer checks before approving a new or changed component. Storybook is built and published as part of CI on every merge to the frontend's main branch, so it never drifts out of sync with what is actually shipped (matching 004's central lesson about configurability without a forcing function toward consistency — Storybook-as-CI-artifact is the forcing function here).

## CI/CD Considerations

A new frontend job added to the existing `.github/workflows/ci.yml`, structurally mirroring the backend's own `make ci` gate (lint → type-check → test → build), per `research.md`: ESLint (TypeScript + `jsx-a11y` rules), `tsc --noEmit`, Vitest, Storybook build with `a11y` gate, Vite production build, Playwright E2E against the docker-compose stack. The frontend job runs independently of and in parallel with the existing backend job — neither blocks the other unless a change touches both.

## Deployment Strategy

The frontend builds to a static asset bundle, served from the **same origin** as the API behind a single reverse proxy/gateway — recommended specifically (not merely conventionally) because: (1) it eliminates the need for CORS entirely, removing an entire category of security configuration risk; (2) it makes the httpOnly refresh-cookie auth flow (Authentication Flow, above) simpler and safer, since same-origin cookies avoid the additional `SameSite`/credentialed-CORS complexity cross-origin deployment would otherwise require. The specific static-hosting mechanism (a minimal container behind the existing gateway vs. a CDN with origin-routing back to the same effective host) is an infrastructure-team decision outside this plan's scope, provided the same-origin property holds.

## Observability

Structured client-side error and performance telemetry (Constitution Principle X, Operational Excellence) — every unhandled error caught by an error boundary, and every Performance Budget metric above, is reported through a single, shared telemetry module (not scattered `console.error` calls), so operations teams gain frontend visibility comparable to what the backend's existing structured logging already provides. This plan does not select a specific telemetry vendor/backend — that is an infrastructure decision — but requires the client-side instrumentation itself to exist from the first release, not be retrofitted.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| **Backend API surface gap** (Evidence/Finding/verification/search/notifications/streaming endpoints do not exist yet) | Treated as an explicit, sequenced, cross-team dependency (`contracts/api-gaps.md`), not worked around by duplicating backend logic in the frontend. Frontend delivery is sequenced behind it, per the Workspace spec's own story priorities. |
| **PDF evidence-highlighting is genuinely novel engineering**, not a library feature | Named explicitly rather than assumed solved by PDF.js alone; budgeted as dedicated engineering effort with an early prototype/spike before it is on any feature's critical path. |
| **100,000+-row virtualized performance is a real engineering effort**, not default framework behavior | Enforced via CI-checked Performance Budgets (a synthetic large-dataset test), not left to code review judgment alone. |
| **No production-grade (OIDC/JWKS) IdentityProvider exists on the backend yet** | Frontend built against an abstracted auth interface (Authentication Flow, above) so the eventual swap is a contained, single-module change, not a cross-cutting rewrite. |
| **Design system drift over time** (004's most-repeated cross-product failure mode) | Storybook-as-CI-artifact, a closed component/token set, and a code-review checklist referencing spec 003 directly — the same forcing-function logic 004 identifies as absent in Salesforce/Atlassian/ServiceNow. |
| **Streaming (SSE) delivery is new backend infrastructure** | Scoped to exactly two use cases (Copilot streaming, notifications) using one mechanism, not introduced speculatively; polling remains an acceptable fallback for notifications specifically, given their 30-second tolerance. |
| **TanStack Router is a less common choice than React Router** (named explicitly in `research.md` as a close call) | If the team weighs hiring/onboarding familiarity more heavily than compile-time URL-state safety, React Router v7 is an accepted, lower-risk substitute — this decision is deliberately flagged as revisitable, not treated as closed. |
| **Relevance-ranked search combined with cursor pagination is a known-hard problem** at 100,000+-row scale (post-analysis finding) | Composite `(rank, id)` cursor required at the backend contract level (see Search Architecture, above) — specified now, before implementation, rather than discovered as a bug once pagination skips or duplicates rows. |
| **Exact `COUNT(*)` under arbitrary filters is a Postgres performance trap** at 100,000+-row scale (post-analysis finding) | Planner-estimated count as the default strategy, exact count only below a small-row-count threshold (see Search Architecture, above) — a backend-only decision with no frontend contract impact. |
| **The recommended production auth flow has a backend dependency (refresh-cookie issuance + CSRF) that was not originally scoped** (post-analysis finding) | Added explicitly to `contracts/api-gaps.md`'s Authentication section; tracked as a pre-production-cutover dependency, not a blocker for Setup/Foundational/US1–US6. |
| **E2E and performance tests assume a seeded 100,000+-row dataset that no task previously created** (post-analysis finding) | A dedicated, deterministic dataset-seeding task now exists in Setup (see `tasks.md`); required before User Story 2's checkpoint is considered met, not before Setup/Foundational/US1. |

## Complexity Tracking

No entries — no Constitution Check violation requires justification. The technology set chosen (TanStack ecosystem, PDF.js, Storybook, Vitest/Playwright) was deliberately evaluated against "do not over-engineer": no Redux, no premature search-service adoption, no WebSocket infrastructure where SSE suffices, no commercial PDF SDK where the actual requirement doesn't justify its cost.
