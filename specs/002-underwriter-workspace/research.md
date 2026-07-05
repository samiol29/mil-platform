# Phase 0 Research: MIL Frontend Technology Decisions

**Feature**: Underwriter Workspace implementation | **Governing specs**: 002 (Underwriter Workspace), 003 (Design System), 004 (Evidence-Based Product Research)

Every decision below follows the Decision / Rationale / Alternatives Considered format. Decisions are technology choices, not new product requirements — they exist entirely to satisfy requirements already stated in 002 and 003, interpreted through the evidence in 004.

---

## Language & Type Safety

**Decision**: TypeScript, in strict mode, for 100% of application code.

**Rationale**: The existing `frontend/` scaffold (legacy, being replaced per project decision) is plain JavaScript. For a multi-year, multi-engineer, regulated-domain product with ~100 functional requirements already specified before a line of UI code exists, compile-time type safety is not a stylistic preference — it is the primary defense against the exact kind of silent contract drift the research in 004 identifies as a recurring failure mode in aging enterprise products (Salesforce, ServiceNow: "the same concept looks different in different modules"). TypeScript also lets the frontend encode the backend's Pydantic response shapes as source-of-truth types, catching contract drift at build time rather than in production.

**Alternatives considered**: Plain JavaScript with JSDoc type hints (rejected — weaker, optional enforcement, no compiler gate in CI) — Flow (rejected — materially smaller ecosystem and hiring pool than TypeScript, no longer a competitive choice for new projects in 2026).

---

## UI Framework

**Decision**: React 19.

**Rationale**: Already present in the (legacy) scaffold; the dominant choice for this class of application; the entire recommended ecosystem below (TanStack Router/Query/Table/Virtual) is React-first and best-supported there. React's component model maps directly onto the Design System's closed component/state-model architecture (003 FR-078).

**Alternatives considered**: Vue 3 (rejected — smaller enterprise data-grid/PDF-viewer ecosystem; no material advantage for this domain) — Svelte/SolidJS (rejected — excellent performance profile, but materially smaller hiring pool and third-party component ecosystem for the specific hard problems this product has: virtualized tables at 100k+ rows, PDF rendering, accessible complex widgets; not justified given "do not over-engineer, do not introduce unnecessary complexity").

---

## Build Tooling

**Decision**: Vite.

**Rationale**: Already present in the scaffold; fast HMR is directly relevant to the "every interaction should feel intentional" engineering culture this plan wants to encourage; native ESM, first-class TypeScript support, and the fastest production-build story among mainstream options.

**Alternatives considered**: webpack (rejected — slower dev iteration, more configuration surface, no material advantage) — Next.js/full-stack meta-framework (rejected — MIL's backend is already a complete, stable FastAPI service per project status; a meta-framework's server-rendering and API-route features would either go unused or duplicate backend responsibilities the constitution assigns elsewhere — see Constitution Principle VI, API-First Integration. A pure client-rendered SPA behind the existing API is the correct fit, not a compromise).

---

## Routing

**Decision**: TanStack Router.

**Rationale**: 002 requires extensive, reliable deep-linking (FR-005: every application, document, evidence item, and finding must be reachable via a direct link) and requires filter/sort state to persist and restore correctly (FR-004, FR-068–071). TanStack Router provides fully type-safe route params *and* type-safe, validated URL search-params (the natural home for filter/sort/saved-view state), which a large, long-lived, deep-linking-heavy application benefits from directly — a mistyped or missing param in a linked URL becomes a compile error, not a runtime bug discovered by a user.

**Alternatives considered**: React Router v7 (the incumbent choice in the legacy scaffold) — a mature, extremely well-known, perfectly viable choice; rejected only in favor of TanStack Router's stronger compile-time guarantees for the specific URL-state-heavy pattern this product requires (filters, saved views, and deep-linked evidence/finding anchors all live in the URL). This is a genuine, debatable trade-off, not an obvious win: TanStack Router is newer and has a smaller hiring pool than React Router. **If the engineering team weighs hiring/onboarding familiarity above type-safety of URL state, React Router v7 is an entirely reasonable, lower-risk substitute** — this is the one recommendation in this document explicitly flagged as a close call rather than a clear best-in-class pick.

---

## Server State & Caching

**Decision**: TanStack Query.

**Rationale**: This is the single most direct technology mapping to 002 and 003's requirements: tiered data freshness (002 State Management & Data Strategy: audit-critical data confirmed-fresh, informational data tolerant of staleness with background refresh), background refetch without disrupting scroll/selection (002 Performance Strategy), and a confirmed-not-optimistic write path for audit-critical actions versus an optimistic path for low-risk preference actions (002 Assumptions; 004 Design Decision on selective optimistic UI) map directly onto TanStack Query's query/mutation model, `staleTime`/`refetchInterval` tiering, and `onMutate`/rollback primitives.

**Alternatives considered**: Redux + RTK Query (rejected — more ceremony for equivalent capability; Redux's global-store model is not needed once server state is fully owned by a dedicated cache) — SWR (rejected — smaller feature surface than TanStack Query, notably weaker mutation/optimistic-update primitives, which this product needs precisely and selectively) — hand-rolled fetch + Context (rejected outright — reimplementing caching, dedup, and staleness tiering by hand is exactly the kind of unnecessary complexity/reinvention this plan is explicitly instructed to avoid).

---

## Client (UI-only) State

**Decision**: Zustand for cross-cutting UI state (command palette open/closed, active theme, panel layout); local component state (`useState`/`useReducer`) for everything else; URL state (via the router) for anything that should survive a refresh or be shareable (filters, sort, active tab).

**Rationale**: Once TanStack Query owns all server state and the router owns all shareable/URL-relevant state, the remaining client-only state surface is small and does not justify Redux-scale ceremony. Zustand provides a minimal, un-opinionated store for the few genuinely global UI concerns (matching "do not over-engineer").

**Alternatives considered**: Redux Toolkit (rejected — its primary value, normalized server-state caching, is now TanStack Query's job; using it only for a handful of UI flags is disproportionate ceremony) — React Context alone for all global UI state (rejected — Context re-render characteristics make it a poor fit for frequently-changing global state like command-palette query text; fine, and used, for rarely-changing state like the authenticated user or theme).

---

## Tables & Virtualization

**Decision**: TanStack Table (headless table logic: sorting, column model, selection) + TanStack Virtual (row/column virtualization).

**Rationale**: 002 requires the Application Queue and every other list surface to remain responsive at 100,000+ rows without loading the full dataset (FR-017, Performance Strategy) — this is precisely windowed rendering plus server-driven pagination, the design point of TanStack Virtual. TanStack Table's headless model keeps the actual visual presentation fully governed by the Design System (003) rather than importing a pre-styled grid component whose visual opinions would fight the closed design system.

**Alternatives considered**: AG Grid (rejected — an excellent, capable product, but its enterprise tier is a paid, closed-source dependency with its own strong visual/interaction opinions that would conflict with 003's closed, self-owned design system; introduces vendor lock-in this plan is not willing to accept for a component this central to the product) — a hand-rolled virtualization layer (rejected — reinventing a well-solved, subtle problem; unnecessary complexity for no benefit over a mature, headless library).

---

## PDF / Document Viewing

**Decision**: Mozilla PDF.js as the rendering engine, with a custom-built coordinate-mapping overlay layer for evidence highlighting.

**Rationale**: 002 (FR-038–044) and 003 (FR-058) require in-viewer rendering (no forced download), page/field-level jump-to navigation, and pixel-accurate highlighting of the exact region an evidence item came from. PDF.js is the free, open-source, battle-tested rendering engine used by Firefox itself and widely embedded in enterprise document tools; it exposes the low-level text/page geometry needed to build a highlight overlay. **No PDF library, commercial or open-source, provides mortgage-evidence-highlighting out of the box** — this is real, original engineering work regardless of vendor choice (see Risks & Mitigations in plan.md): mapping an evidence item's stored provenance (page number, field location) onto PDF.js's rendered coordinate space, correctly across zoom level and page rotation.

**Alternatives considered**: A commercial PDF SDK (e.g., PSPDFKit/Nutrient, Apryse) (rejected — these offer substantial built-in annotation/collaboration tooling MIL does not need, at real recurring per-seat licensing cost and vendor lock-in; MIL's actual requirement — render plus a custom, domain-specific highlight overlay — does not justify paying for capability that goes unused) — rendering PDFs via `<embed>`/native browser PDF viewer (rejected outright — provides no programmatic access to page geometry, making evidence highlighting and jump-to-page/field navigation impossible).

---

## Forms & Validation

**Decision**: React Hook Form + Zod.

**Rationale**: 002's forms are comparatively few and lightweight (override/escalation reasons, filter criteria, saved-view naming) rather than complex wizards — React Hook Form's uncontrolled-input model keeps re-render cost low even in dense, table-adjacent forms. Zod schemas are used for two purposes with one tool: form validation, and (paired with TanStack Query) as a lightweight runtime contract-verification layer at the API boundary — a Zod-parsed API response that doesn't match its expected shape fails loudly and immediately in development rather than silently propagating a subtly wrong value into the UI, directly supporting the "clean architecture" and contract-safety goals of this plan.

**Alternatives considered**: Formik (rejected — materially higher re-render cost at scale than React Hook Form's uncontrolled approach; the project is otherwise not using it already) — no schema validation library, hand-written validators (rejected — loses the dual form-validation/API-contract-verification benefit for no savings).

---

## Component Documentation

**Decision**: Storybook, with the accessibility (`a11y`) addon enabled as a required, CI-gated check.

**Rationale**: Explicitly requested; also the direct enforcement mechanism for 003's closed component/token system — every component in the Design System's closed set (003 FR-078–081) is documented, visually reviewable, and accessibility-checked in isolation before it is ever composed into a full screen, which is the practical mechanism that prevents the "one meaning, two representations" drift 004's research identifies as Atlassian/Salesforce/ServiceNow's most repeated failure.

**Alternatives considered**: No component documentation tool, relying on code review alone (rejected — explicitly requested, and insufficient as an enforcement mechanism at the scale of a multi-year, multi-engineer product) — Ladle (a lighter Storybook alternative) (rejected — smaller ecosystem, notably weaker accessibility-addon and visual-testing integration than Storybook, which are the two capabilities this plan actually needs from this tool).

---

## Testing

**Decision**: Vitest (unit/component tests) + React Testing Library (component behavior, enforcing accessible queries by construction) + Playwright (end-to-end, cross-browser, keyboard/screen-reader-adjacent testing) + axe-core (automated WCAG scanning, wired into both Storybook and Playwright).

**Rationale**: Vitest is Vite-native (shared config, fast, no separate bundler needed for tests). React Testing Library's query model (`getByRole`, `getByLabelText`) makes writing an inaccessible component *harder* to test than an accessible one, turning 003's accessibility mandate into a structural nudge rather than a manual checklist item. Playwright's strong keyboard-simulation and multi-browser support directly exercises 002's "every primary workflow keyboard-complete" requirement (FR-088) and 003's WCAG AA requirement (SC-009) as automated, CI-enforced gates rather than only manual QA.

**Alternatives considered**: Jest (rejected — Vitest is a drop-in-compatible, faster, Vite-native alternative with no meaningful downside for this project) — Cypress (rejected in favor of Playwright — comparable capability, but Playwright's native multi-tab/multi-context support fits this product's drawer/panel-heavy, deep-linking-heavy interaction model better, and its accessibility-testing integration is more mature).

---

## Real-Time & Streaming Delivery

**Decision**: Server-Sent Events (SSE) as the single mechanism for both Copilot response streaming (002 FR-060) and notification delivery (002 FR-084), introduced as an additive backend capability (see `contracts/api-gaps.md`); short-interval polling via TanStack Query's `refetchInterval` as the interim/fallback mechanism wherever SSE is not yet available.

**Rationale**: Copilot responses must progressively reveal (FR-060) and notifications must appear within 30 seconds (FR-084) — both are one-directional, server-to-client delivery problems. SSE satisfies both with a single, simple, HTTP-native mechanism (automatic reconnection built into the browser's `EventSource` API, no new protocol, works cleanly through standard reverse proxies) rather than introducing a second, heavier mechanism.

**Alternatives considered**: WebSockets (rejected — bidirectional capability is not needed for either use case; WebSockets carry materially more operational complexity — connection/session management, reverse-proxy configuration, reconnection handling the browser doesn't provide for free — that this product's actual (one-directional) requirement does not justify; this is a direct application of "do not over-engineer") — pure polling for both features (rejected as the *sole* long-term mechanism for Copilot streaming specifically — polling cannot deliver a genuinely progressive token-by-token reveal; acceptable only as the interim mechanism for notifications, where a 30-second tolerance makes polling entirely sufficient and SSE an optimization, not a requirement).

---

## Search

**Decision**: The frontend issues structured queries (borrower name / loan number / LOS reference) against a backend search endpoint; no client-side search index or third-party search service is introduced.

**Rationale**: 002 (FR-009–015) requires sub-2-second, human-identifier search at 100,000+ record scale — this must be served by the backend's own indexed query capability (e.g., Postgres trigram/full-text indexing), not reproduced or duplicated in the browser. Introducing a dedicated search service (Elasticsearch/Algolia/Meilisearch) is explicitly not recommended at this stage: it is a real, mature option if Postgres-native indexing later proves insufficient at true production scale, but adopting it pre-emptively, before that limit is actually observed, would be exactly the unnecessary complexity this plan is instructed to avoid. This decision is flagged as a backend dependency in `contracts/api-gaps.md`.

**Alternatives considered**: A dedicated search service introduced from day one (rejected for now, explicitly named as a future escalation path if Postgres-native search proves insufficient) — client-side fuzzy search over a locally cached dataset (rejected outright — fundamentally incompatible with the 100,000+ record, real-time-data requirement; a local index would be enormous, immediately stale, and would violate the "never load the entire dataset" performance principle).

**Post-analysis addendum**: combining relevance ranking with cursor pagination requires a composite `(rank, id)` cursor, and total-count-at-scale requires a planner-estimate-first strategy — both are backend contract requirements, specified in full in `plan.md`'s Search Architecture section and tracked in `plan.md`'s Risks and Mitigations table, so they are decided now rather than discovered mid-implementation.

---

## CI/CD Tooling

**Decision**: Extend the existing GitHub Actions `ci.yml` with a parallel frontend job mirroring the backend's existing gate structure (`make ci` = lint + format-check + type-check + test + compileall) — for the frontend: lint (ESLint, replacing the legacy scaffold's oxlint once the codebase is TypeScript-first, since ESLint's TypeScript/accessibility plugin ecosystem is materially more mature), `tsc --noEmit` type-check, Vitest unit/component tests, Storybook build with the `a11y` addon as a hard gate, Vite production build, and a Playwright E2E suite run against the existing docker-compose-provisioned backend.

**Rationale**: Matches the backend's own established, working CI discipline rather than inventing a parallel convention; keeps both halves of the codebase held to an equivalent bar.

**Alternatives considered**: A separate CI provider/pipeline for the frontend (rejected — no justification for split tooling when GitHub Actions already serves the backend well) — keeping `oxlint` (rejected — ESLint's TypeScript-aware and `jsx-a11y` rule sets are more mature and are directly relevant to this plan's accessibility-enforcement goals; oxlint is a fine choice for a minimal JS scaffold but not for a TypeScript-strict, accessibility-gated enterprise codebase).
