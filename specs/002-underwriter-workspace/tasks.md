# Tasks: MIL Frontend — Underwriter Workspace

**Input**: Design documents from `specs/002-underwriter-workspace/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md), governed jointly with `specs/003-design-system/spec.md` and informed by `specs/004-evidence-based-product-research/spec.md`.

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Included. Spec 002's Success Criteria and Acceptance Scenarios are stated as concrete, measurable, testable outcomes throughout, and the Design System spec (003) requires automated accessibility conformance as a hard gate — both are treated as an explicit test request, not optional.

**Organization**: Tasks are grouped by user story (from spec.md's 6 prioritized stories) to enable independent implementation, testing, and incremental delivery, exactly as spec 002 requires each story to be independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US6, mapping to spec.md's prioritized user stories
- File paths are exact, per the structure defined in `plan.md`

## Path Conventions

Per `plan.md`'s Structure Decision (Option 2 — web application): the existing FastAPI backend lives at `src/` (unchanged in architecture; additive-only changes per `contracts/api-gaps.md`); the frontend is a full replacement of the legacy `frontend/` directory at the same path, internally structured as `frontend/src/{app,design-system,entities,features,routes,shared,test}` per `plan.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Replace the legacy scaffold and initialize the real project tooling. No product/domain code yet.

- [X] T001 Remove obsolete legacy scaffold contents (`frontend/src/App.jsx`, `frontend/src/pages/CustomerRegistrationPage.jsx`, `frontend/src/pages/CustomerSearchPage.jsx`, `frontend/src/pages/LoginPage.jsx`, `frontend/src/pages/RegisterPage.jsx`, `frontend/src/context/AuthContext.jsx`, `frontend/src/components/DashboardLayout.jsx`, `frontend/src/components/ProtectedRoute.jsx`, `frontend/src/api/client.js`) and create the new directory skeleton (`frontend/src/{app,design-system/tokens,design-system/components,entities,features,routes,shared,test}`) per `plan.md`
- [X] T002 Initialize TypeScript strict-mode configuration in `frontend/tsconfig.json`
- [X] T003 [P] Configure ESLint with TypeScript and `jsx-a11y` rule sets, replacing `oxlint`, in `frontend/eslint.config.ts` (see `research.md`: CI/CD Tooling decision)
- [X] T004 [P] Configure a formatting tool (Prettier or equivalent) in `frontend/.prettierrc`
- [X] T005 [P] Update `frontend/vite.config.ts` for TypeScript, path aliases (`@app`, `@design-system`, `@entities`, `@features`, `@routes`, `@shared`), and a same-origin dev proxy to the local API (see `plan.md` Deployment Strategy)
- [X] T006 [P] Update `frontend/package.json` dependencies: `react@19`, `@tanstack/react-router`, `@tanstack/react-query`, `@tanstack/react-table`, `@tanstack/react-virtual`, `zustand`, `react-hook-form`, `zod`, `axios`, `pdfjs-dist` (see `research.md`)
- [X] T007 [P] Configure Vitest + React Testing Library in `frontend/vitest.config.ts` and `frontend/src/test/setup.ts`
- [X] T008 [P] Initialize Storybook with the `a11y` addon in `frontend/.storybook/`
- [X] T009 [P] Initialize Playwright (with `@axe-core/playwright`) in `frontend/e2e/playwright.config.ts`
- [X] T010 [P] Add a parallel frontend job (lint → typecheck → test → Storybook build+a11y gate → Vite build → Playwright) to `.github/workflows/ci.yml`, mirroring the backend's existing `make ci` gate structure (see `research.md`)
- [X] T126 [P] Create a deterministic 100,000+-application seed/fixture-generation script (realistic borrower names, loan numbers, LOS references, status distribution, SLA ages) in `scripts/seed_large_dataset.py`, runnable standalone and reusable by both Playwright E2E (T081, T082, T108) and manual QA — resolves post-analysis finding G1

**Checkpoint**: Tooling in place; no product code exists yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The Design System (003) implementation and app shell every user story composes. **No user story may begin until this phase is complete.**

### Design tokens (spec 003)

- [X] T011 [P] Define primitive color tokens in `frontend/src/design-system/tokens/color.primitives.ts`
- [X] T012 [P] Define semantic surface/interaction/focus tokens (light + dark) in `frontend/src/design-system/tokens/color.semantic.ts`
- [X] T013 [P] Define the Status color family (workflow/SLA state only) in `frontend/src/design-system/tokens/color.status.ts`
- [X] T014 [P] Define the Evidence/Confidence color family (structurally distinct from Status) in `frontend/src/design-system/tokens/color.confidence.ts`
- [X] T015 [P] Define the AI-signal color family (structurally distinct from Status and Confidence) in `frontend/src/design-system/tokens/color.ai.ts`
- [X] T016 [P] Define the type scale (6–8 steps incl. tabular/monospaced numeric treatment) in `frontend/src/design-system/tokens/typography.ts`
- [X] T017 [P] Define the spacing scale in `frontend/src/design-system/tokens/spacing.ts`
- [X] T018 [P] Define elevation levels and border-radius scale in `frontend/src/design-system/tokens/elevation.ts`
- [X] T019 [P] Define motion tokens (durations/easing per transition category, plus reduced-motion equivalents) in `frontend/src/design-system/tokens/motion.ts`
- [X] T020 Implement `ThemeProvider` resolving all tokens for light/dark theme in `frontend/src/design-system/theme/ThemeProvider.tsx` (depends on T011–T019)

### Closed base component set (spec 003 FR-078)

- [X] T021 [P] Implement `Button` (all required states) in `frontend/src/design-system/components/Button/Button.tsx`
- [X] T022 [P] Implement `LoadingState` + `SkeletonState` in `frontend/src/design-system/components/LoadingState/`
- [X] T023 [P] Implement `EmptyState` in `frontend/src/design-system/components/EmptyState/EmptyState.tsx`
- [X] T024 [P] Implement `ErrorState` (plain-language, retry-capable, granular) in `frontend/src/design-system/components/ErrorState/ErrorState.tsx`
- [X] T025 [P] Implement `StatusBadge` (Status color family + non-color signal) in `frontend/src/design-system/components/StatusBadge/StatusBadge.tsx`
- [X] T026 [P] Implement `ConfidenceIndicator` (fixed band scale, Evidence/Confidence family) in `frontend/src/design-system/components/ConfidenceIndicator/ConfidenceIndicator.tsx`
- [X] T027 [P] Implement `AiSignalBadge` (AI color family, persistent non-decorative indicator) in `frontend/src/design-system/components/AiSignalBadge/AiSignalBadge.tsx`
- [X] T028 [P] Implement `EvidenceChip` (single reusable citation/evidence-reference pattern) in `frontend/src/design-system/components/EvidenceChip/EvidenceChip.tsx`
- [X] T029 [P] Implement `Drawer` (focus trap, keyboard dismiss, returns focus on close) in `frontend/src/design-system/components/Drawer/Drawer.tsx`
- [X] T030 [P] Implement `Dialog` (blocking-confirmation-only, focus trap) in `frontend/src/design-system/components/Dialog/Dialog.tsx`
- [X] T031 [P] Implement the virtualized `Table` primitive (TanStack Table + TanStack Virtual composition) in `frontend/src/design-system/components/Table/Table.tsx`
- [X] T032 [P] Implement the `CommandPalette` shell (fuzzy search, keyboard-first, empty of commands for now) in `frontend/src/design-system/components/CommandPalette/CommandPalette.tsx`
- [X] T033 Write Storybook stories covering every defined state, and confirm the `a11y` addon passes, for every component in T021–T032 (depends on T021–T032)

### App shell & cross-cutting infrastructure

- [X] T034 Implement the HTTP client with a token-attachment interceptor in `frontend/src/app/auth/httpClient.ts`
- [X] T035 Implement the auth abstraction module (token acquisition behind one interface; dev-bearer flow as the initial implementation) in `frontend/src/app/auth/authProvider.ts` (depends on T034; see `plan.md` Authentication Flow)
- [X] T036 Configure the TanStack Query client with per-entity-tier `staleTime` defaults (audit-critical / informational / long-lived / preference, per `data-model.md`) in `frontend/src/app/queryClient.ts`
- [X] T037 Configure the TanStack Router root route tree and compose root providers (Theme, Query, Router) in `frontend/src/app/router.tsx` (depends on T020, T036)
- [X] T038 Implement the Zustand store for ephemeral UI state (command palette query, panel open/closed, theme choice) in `frontend/src/app/uiStore.ts`
- [X] T039 Implement the root Error Boundary in `frontend/src/app/ErrorBoundary.root.tsx`
- [X] T040 [P] Implement the route-level Error Boundary wrapper in `frontend/src/shared/errors/RouteErrorBoundary.tsx`
- [X] T041 [P] Implement the panel-level Error Boundary wrapper in `frontend/src/shared/errors/PanelErrorBoundary.tsx`
- [X] T042 [P] Implement the client-side telemetry module (error + Performance Budget metric reporting) in `frontend/src/shared/telemetry/telemetry.ts`
- [X] T043 Establish the shared entity-layer convention: a Zod-parsing + query-hook helper every `entities/*` module will use in `frontend/src/shared/api/createEntityQuery.ts` (depends on T034, T036)
- [X] T044 [P] Configure MSW contract-shaped mock handlers for local dev and tests in `frontend/src/test/msw/handlers.ts`
- [X] T127 [P] Implement the persistent user-identity indicator and always-reachable sign-out control (FR-007) in `frontend/src/app/UserMenu.tsx` (depends on T035) — resolves post-analysis finding C1

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Assess a Single Application (Priority: P1) 🎯 MVP

**Goal**: An underwriter opens an application (via direct deep link, bypassing the queue), reviews every finding's five explainability elements, opens supporting evidence and its exact source-document location, and records a verification or override with a mandatory, preserved-on-failure reason.

**Independent Test**: Deep-link directly to a seeded application; complete the full evidence-review-to-decision loop without ever touching the queue.

### Backend additions for User Story 1 (additive only — see `contracts/api-gaps.md`)

- [X] T045 [US1] Add `GET /v1/applications/{id}/evidence` in new router `src/mil/api/v1/evidence.py`, exposing the existing `mil.evidence` service
- [X] T046 [US1] Add `GET /v1/applications/{id}/findings` in new router `src/mil/api/v1/findings.py`, exposing the existing `mil.finding` service, with resolved evidence refs
- [X] T047 [US1] Add `POST /v1/findings/{id}/verify` in `src/mil/api/v1/findings.py` (idempotent, attributed, immutable per Constitution Principle VIII)
- [X] T048 [US1] Add `POST /v1/findings/{id}/override` in `src/mil/api/v1/findings.py`, rejecting an empty `reason`
- [X] T049 [US1] Add `POST /v1/findings/{id}/escalate` in `src/mil/api/v1/findings.py`, requiring `reason` and a target role — implemented per the approved Review/Escalation domain design (see docs/archive/HANDOFF.md): `ESCALATED` is a non-terminal `ReviewSession` status resolved by the existing verify/override/reject actions; ownership transfers to the target role's (or, optionally, a specific person's) queue; resolution is restricted to that role/person
- [X] T050 [US1] Add `GET /v1/applications/{id}/audit` in new router `src/mil/api/v1/audit.py`, read-only chronological projection of existing audit events
- [X] T051 [US1] Register the new routers in `src/main.py`

### Frontend entity layer for User Story 1

- [X] T052 [P] [US1] Create `Application` types + Zod schema in `frontend/src/entities/application/types.ts` (per `data-model.md`)
- [X] T053 [P] [US1] Create `Application` single-record query hook in `frontend/src/entities/application/queries.ts`
- [X] T054 [P] [US1] Create `Document` types + Zod schema in `frontend/src/entities/document/types.ts`
- [X] T055 [P] [US1] Create `Document` query hooks (list-for-application, get) in `frontend/src/entities/document/queries.ts`
- [X] T056 [P] [US1] Create `EvidenceItem` types + Zod schema in `frontend/src/entities/evidence/types.ts`
- [X] T057 [US1] Create `EvidenceItem` query hooks in `frontend/src/entities/evidence/queries.ts` (depends on T045, T056)
- [X] T058 [P] [US1] Create `Finding` types + Zod schema (five explainability fields required, not optional, at the type level) in `frontend/src/entities/finding/types.ts`
- [X] T059 [US1] Create `Finding` query hook + verify/override/escalate mutation hooks (confirmed writes only — no optimistic update) in `frontend/src/entities/finding/queries.ts` (depends on T046–T049, T058)
- [X] T060 [P] [US1] Create `AuditTrailEntry` types + read-only query hook (no mutation exposed at the type level) in `frontend/src/entities/audit/queries.ts` (depends on T050)

### Frontend features for User Story 1

- [X] T061 [US1] Implement the Application Workspace shell (overview/findings/evidence/documents/Copilot regions, no full reload between them) in `frontend/src/features/application-workspace/ApplicationWorkspace.tsx` (depends on T052–T055) — **no Copilot region: User Story 3, out of scope this session**
- [X] T062 [US1] Implement the Finding presentation component, type-gated on all five explainability fields, in `frontend/src/features/application-workspace/FindingCard.tsx` (depends on T058)
- [X] T063 [US1] Implement verify/override/escalate action controls with a React Hook Form + Zod reason form (blocks empty submission; preserves input across a failed submit; the confirming action per FR-078 is a distinct second step — e.g. a "Review & Confirm" button separate from the reason field itself — never implicit in typing the reason) in `frontend/src/features/application-workspace/FindingActions.tsx` (depends on T059, T030)
- [X] T064 [US1] Implement the PDF.js rendering layer (first-page-usable-first, no full-document wait) in `frontend/src/features/document-viewer/PdfRenderer.tsx` — required a new additive `GET .../documents/{id}/content` endpoint (see docs/archive/HANDOFF.md)
- [X] T065 [US1] Implement the evidence-highlight coordinate-mapping overlay (page/field-location → rendered coordinates, correct across zoom and rotation) in `frontend/src/features/document-viewer/EvidenceHighlightOverlay.tsx` (depends on T064) — **highest-risk task in this plan; see `plan.md` Risks and Mitigations**; coordinate math (`coordinate-mapping.ts`) built on PDF.js's own `convertToViewportPoint` API and verified with unit tests against an independent re-implementation of PDF.js's transform formula across all four rotations (0/90/180/270) and multiple zoom scales
- [X] T066 [US1] Implement Document Viewer navigation (page jump, zoom, document switcher) in `frontend/src/features/document-viewer/DocumentViewer.tsx` (depends on T064, T065) — "pinned-vs-preview tabs" (plan.md's framing of FR-044) deliberately not built as a distinct interaction mode; see file header comment for why a plain document selector satisfies FR-044's literal text without guessing UI behavior no FR specifies
- [X] T067 [US1] Implement the Audit Timeline component (read-only, chronological, immutable-feeling presentation) in `frontend/src/features/application-workspace/AuditTimeline.tsx` (depends on T060)
- [X] T068 [US1] Implement the stale-record indicator and one-action refresh (FR-036) in `frontend/src/features/application-workspace/StaleRecordBanner.tsx`
- [X] T069 [US1] Wire the deep-linkable Application Workspace route in `frontend/src/routes/applications.$applicationId.tsx` (depends on T037, T061)
- [X] T128 [US1] Implement the role-gated read-only Application Workspace variant for the auditor/compliance role (FR-037): verify/override/escalate controls are entirely absent from the render tree for this role, not merely disabled-but-visible, while all evidentiary and decision content remains identical, in `frontend/src/features/application-workspace/ApplicationWorkspace.tsx` (depends on T061, T062, T063) — resolves post-analysis finding C3

### Tests for User Story 1

- [X] T070 [P] [US1] Component test: `FindingCard` never renders with a missing explainability field, in `frontend/src/features/application-workspace/FindingCard.test.tsx`
- [X] T071 [P] [US1] Component test: override submission blocks on empty reason and preserves input on simulated network failure, in `frontend/src/features/application-workspace/FindingActions.test.tsx`
- [X] T072 [US1] E2E test covering 002 Acceptance Scenarios 1–5 (explainability, evidence-to-document navigation, override with reason, interrupted-submission recovery, status advance) in `frontend/e2e/application-workspace.spec.ts` — scenarios 1–4 implemented and passing; scenario 5 (application status advance + leaving the queue) is `test.fixme` — requires the application-level "all findings resolved" status transition and the underwriter queue, neither of which exists yet (User Story 2); also covers escalate and Document Viewer navigation. Mutation-heavy specs (override/escalate) are scoped to Chromium — see file header comment for the Firefox/WebKit Playwright+MSW navigation-timing quirk this works around (the same flows are covered browser-independently by `FindingActions.test.tsx`)
- [X] T129 [US1] E2E test: an auditor/compliance-role session renders the Application Workspace with zero action controls present in the DOM (not merely disabled) while all evidentiary content matches the underwriter view, in `frontend/e2e/application-workspace-readonly.spec.ts` (depends on T128) — verifies post-analysis finding C3; uses a dev/E2E-only `?devRole=` override in `authProvider.ts` (no real multi-role login flow exists yet)

**Checkpoint**: User Story 1 is fully functional and independently testable — the MVP.

---

## Phase 4: User Story 2 - Locate Applications Without Technical Identifiers (Priority: P1)

**Goal**: Find any application by borrower name, loan number, or LOS reference, in a queue defaulting to newest-first, responsive at 100,000+ rows.

**Independent Test**: Against a seeded 100,000+-row dataset, search by partial name, exact loan number, and LOS reference; confirm the unsearched default queue is newest-first.

### Backend additions for User Story 2

- [ ] T073 [US2] Extend `GET /v1/applications` (existing endpoint, additive query params only) with `query`, `sort`, `filter`, and cursor-pagination support in `src/mil/api/v1/applications.py` — cursor MUST be composite `(rank|sort-column, id)` for stable pagination under ranking or any sort (see `plan.md` Search Architecture); total count MUST use a planner-estimate-first strategy, exact only below a small-row-count threshold
- [ ] T074 [US2] Add a Postgres trigram/full-text index migration over borrower name, loan number, and LOS reference in `migrations/versions/` (see `research.md`: Search decision — no dedicated search service introduced at this stage)

### Frontend

- [ ] T075 [US2] Extend `Application` query hooks with a paginated, filtered, sorted list query in `frontend/src/entities/application/queries.ts` (depends on T053, T073)
- [ ] T076 [US2] Implement the virtualized Application Queue table (columns: borrower name, loan number, LOS reference, status, assignee, SLA, flagged-finding summary) in `frontend/src/features/application-queue/ApplicationQueueTable.tsx` (depends on T031, T075)
- [ ] T077 [US2] Implement the global search input (debounced, matches name/loan-number/LOS-reference simultaneously, never a per-field selector) in `frontend/src/features/search/GlobalSearch.tsx` (depends on T075)
- [ ] T078 [US2] Implement the SLA/age indicator (non-color-alone signal) in `frontend/src/features/application-queue/SlaIndicator.tsx` (depends on T025)
- [ ] T079 [US2] Wire the Application Queue route with URL-state-synced search/sort/filter params in `frontend/src/routes/applications.index.tsx` (depends on T037, T076, T077)
- [ ] T080 [US2] Register global-search and jump-to-application commands in the Command Palette in `frontend/src/features/command-palette/commands.ts` (depends on T032, T077)

### Tests for User Story 2

- [ ] T081 [US2] E2E test: search by partial name / exact loan number / LOS reference at seeded 100,000+-row scale; confirm sub-2s results and disambiguating fields in results, in `frontend/e2e/search-queue.spec.ts`
- [ ] T082 [US2] Performance test enforcing the Performance Budgets (scroll frame budget, sub-1s filter round-trip) against a synthetic 100,000-row dataset in `frontend/e2e/performance/queue-scale.spec.ts`

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: User Story 3 - Interrogate Evidence via Grounded Copilot (Priority: P2)

**Goal**: Ask a natural-language question scoped to one application; receive a streamed, cited answer or an explicit insufficient-evidence response.

**Independent Test**: Against a seeded application, ask a directly-answerable question and confirm a cited, streamed response; ask an unanswerable one and confirm the explicit insufficient-evidence state.

### Backend additions for User Story 3

- [ ] T083 [US3] Add `GET /v1/copilot/sessions/{id}/stream` (SSE) in `src/mil/api/v1/copilot.py`
- [ ] T084 [US3] Add an `insufficientEvidence` boolean field to the existing Copilot response schema (additive field, not a breaking change) in `src/mil/api/v1/schemas.py`

### Frontend

- [ ] T085 [P] [US3] Create `CopilotSession`/`Message`/`Citation` types + Zod schema, constructor-scoped to exactly one `applicationId`, in `frontend/src/entities/copilot/types.ts`
- [ ] T086 [US3] Create Copilot query/mutation hooks and SSE stream consumption in `frontend/src/entities/copilot/queries.ts` (depends on T085, T083, T084)
- [ ] T087 [US3] Implement the Copilot panel — its component signature requires an `applicationId` prop; no route or composition can render it without one — in `frontend/src/features/copilot-panel/CopilotPanel.tsx` (depends on T086)
- [ ] T088 [US3] Implement progressive streamed-message rendering, with each citation becoming individually clickable as soon as it appears in the stream rather than only once the message completes, in `frontend/src/features/copilot-panel/StreamedMessage.tsx` (depends on T086)
- [ ] T089 [US3] Implement citation links resolving to the Evidence Explorer / Document Viewer in `frontend/src/features/copilot-panel/CitationLink.tsx` (depends on T057, T065)
- [ ] T090 [US3] Implement the insufficient-evidence response state (visually distinct from a grounded answer, per 002 FR-059) in `frontend/src/features/copilot-panel/InsufficientEvidenceState.tsx`
- [ ] T091 [US3] Wire the Copilot panel into the Application Workspace in `frontend/src/features/application-workspace/ApplicationWorkspace.tsx` (depends on T061, T087)

### Tests for User Story 3

- [ ] T092 [US3] E2E test covering 002 Acceptance Scenarios 1–4 (grounded citation, insufficient-evidence state, cross-application isolation, streamed in-progress state) in `frontend/e2e/copilot.spec.ts`

**Checkpoint**: User Stories 1–3 independently functional.

---

## Phase 6: User Story 4 - Investigate Discrepancies via Evidence Explorer & Relationships (Priority: P2)

**Goal**: See every evidence item for an application, with conflicts visually flagged and simultaneously comparable, and inspect a finding's or evidence item's relationships on demand.

**Independent Test**: Against a seeded application with two conflicting evidence items for the same fact, confirm the conflict is visually surfaced and both items are viewable together without manual comparison.

### Backend additions for User Story 4

- [ ] T093 [US4] Add `GET /v1/findings/{id}/relationships` in `src/mil/api/v1/findings.py`

### Frontend

- [ ] T094 [US4] Extend `EvidenceItem` query hooks to resolve `conflictsWith` pairs in `frontend/src/entities/evidence/queries.ts` (depends on T057)
- [ ] T095 [US4] Implement the selection-scoped Evidence Explorer side panel (shows only the selected item's context, per Figma-derived discipline in 004), including its one-action link to the item's exact source location per FR-048, in `frontend/src/features/evidence-explorer/EvidenceExplorer.tsx` (depends on T094, T029, T066)
- [ ] T096 [US4] Implement the simultaneous conflict-comparison view in `frontend/src/features/evidence-explorer/ConflictComparison.tsx` (depends on T095)
- [ ] T097 [US4] Create the relationship query hook in `frontend/src/entities/finding/relationships.ts` (depends on T093)
- [ ] T098 [US4] Implement the lightweight relationship view with a legibility-ceiling trigger (ceiling: 50 nodes — see `plan.md` Knowledge Graph Architecture) in `frontend/src/features/knowledge-graph/RelationshipView.tsx` (depends on T097)
- [ ] T099 [US4] Implement the structured list-based fallback view, used at/above the 50-node legibility ceiling, in `frontend/src/features/knowledge-graph/RelationshipListFallback.tsx` (depends on T097)
- [ ] T100 [US4] Wire the Evidence Explorer and relationship view into the Application Workspace in `frontend/src/features/application-workspace/ApplicationWorkspace.tsx` (depends on T061, T095, T098, T066)

### Tests for User Story 4

- [ ] T101 [US4] E2E test covering 002 Acceptance Scenarios 1–3 (conflict flagging, relationship inspection, no-false-positive-flagging) in `frontend/e2e/evidence-explorer.spec.ts`

**Checkpoint**: User Stories 1–4 independently functional.

---

## Phase 7: User Story 5 - Operational Triage of the Full Queue at Scale (Priority: P2)

**Goal**: Combine filters, save a named view, and keep the queue responsive and stateful (scroll position, filters) at 100,000+ rows.

**Independent Test**: Apply a multi-condition filter against the seeded 100,000+-row dataset, save it as a named view, reload, and confirm the same results reproduce.

### Backend additions for User Story 5

- [ ] T102 [US5] Add saved-view CRUD endpoints (`GET/POST/PATCH/DELETE /v1/saved-views`) in new router `src/mil/api/v1/saved_views.py`

### Frontend

- [ ] T103 [P] [US5] Create `SavedView` types + Zod schema in `frontend/src/entities/saved-view/types.ts`
- [ ] T104 [US5] Create `SavedView` query hooks and **optimistic** mutation hooks (low-risk/preference tier per `data-model.md`) in `frontend/src/entities/saved-view/queries.ts` (depends on T103, T102)
- [ ] T105 [US5] Implement the composable structured filter builder UI in `frontend/src/features/application-queue/FilterBuilder.tsx` (depends on T076)
- [ ] T106 [US5] Implement saved-view management UI (save / switch / share-with-team) in `frontend/src/features/application-queue/SavedViewMenu.tsx` (depends on T104)
- [ ] T107 [US5] Implement scroll-position and filter-state preservation across navigation (into an application and back) in `frontend/src/features/application-queue/queueStatePersistence.ts` (depends on T079)

### Tests for User Story 5

- [ ] T108 [US5] E2E test covering 002 Acceptance Scenarios 1–3 (large-scale filter responsiveness, saved-view reproducibility, scroll/filter-state preservation) in `frontend/e2e/saved-views.spec.ts`

**Checkpoint**: User Stories 1–5 independently functional.

---

## Phase 8: User Story 6 - Stay Informed via Notifications (Priority: P3)

**Goal**: Receive timely, actionable, groupable notifications without manual polling.

**Independent Test**: Trigger a seeded assignment event; confirm a notification appears within 30 seconds, is actionable, and can be dismissed.

### Backend additions for User Story 6

- [ ] T109 [US6] Add `GET /v1/notifications` and `PATCH /v1/notifications/{id}` in new router `src/mil/api/v1/notifications.py`
- [ ] T110 [US6] Add `GET /v1/notifications/stream` (SSE) in `src/mil/api/v1/notifications.py`

### Frontend

- [ ] T111 [P] [US6] Create `Notification` types + Zod schema in `frontend/src/entities/notification/types.ts`
- [ ] T112 [US6] Create `Notification` query hooks with SSE subscription and polling fallback in `frontend/src/entities/notification/queries.ts` (depends on T111, T109, T110)
- [ ] T113 [US6] Implement the notification bell + unread-count indicator in `frontend/src/features/notifications/NotificationBell.tsx` (depends on T112)
- [ ] T114 [US6] Implement the notification list panel (grouped by type/subject, individually actionable/dismissible) in `frontend/src/features/notifications/NotificationList.tsx` (depends on T112)
- [ ] T115 [US6] Wire notification-to-application/finding deep-link navigation in `frontend/src/features/notifications/NotificationList.tsx` (depends on T069, T114)

### Tests for User Story 6

- [ ] T116 [US6] E2E test covering 002 Acceptance Scenarios 1–3 (30-second delivery, actionable navigation, grouping) in `frontend/e2e/notifications.spec.ts`

**Checkpoint**: All 6 user stories independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements spanning all stories; not required for any single story's independent testability.

- [ ] T117 [P] Complete Storybook coverage and `a11y` addon review for every feature-level composed component (beyond the Foundational base set) in `frontend/.storybook/`
- [ ] T118 [P] Perform and document a full keyboard-only audit across all 6 user stories in `frontend/docs/accessibility-audit.md`
- [ ] T119 [P] Perform and document a full screen-reader audit (NVDA and VoiceOver, at minimum) in `frontend/docs/accessibility-audit.md`
- [ ] T120 Finalize same-origin reverse-proxy configuration for dev and production deployment in `frontend/vite.config.ts` and `infra/`
- [ ] T121 [P] Finalize CI-enforced Performance Budget gates (bundle-size regression check, synthetic large-dataset check) in `.github/workflows/ci.yml`
- [ ] T122 [P] Wire client-side telemetry to its actual reporting destination in `frontend/src/shared/telemetry/telemetry.ts`
- [ ] T123 Execute the full `quickstart.md` validation pass end-to-end against a fully deployed stack
- [ ] T124 [P] Security hardening review: confirm in-memory-only token storage, no sensitive data in `localStorage`, review response headers/CSP
- [ ] T125 [P] Replace the legacy Vite template `frontend/README.md` with real project documentation
- [ ] T130 Add `POST /v1/auth/refresh` (httpOnly, `SameSite=Strict` refresh cookie) and a double-submit CSRF token endpoint per `contracts/api-gaps.md`'s Authentication Endpoints section, in `src/mil/api/v1/auth.py` — pre-production-cutover dependency, resolves post-analysis finding S1
- [ ] T131 Wire the frontend auth abstraction (`frontend/src/app/auth/authProvider.ts`, from T035) to consume the refresh/CSRF endpoints from T130 — attach the CSRF header on every state-changing request — resolves post-analysis finding S1 (depends on T035, T130)
- [ ] T132 [P] Implement and verify responsive breakpoint behavior (FR-099–101): panel collapsing/relocation at narrower widths with zero loss of information or actions, and a regression test confirming relocation rather than removal, in `frontend/src/design-system/theme/breakpoints.ts` and `frontend/e2e/responsive.spec.ts` — resolves post-analysis finding C2

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks every user story.**
- **User Stories (Phase 3–8)**: All depend on Foundational completion. Ordered here by priority (P1 → P1 → P2 → P2 → P2 → P3) per spec.md; may proceed in parallel across engineers once Foundational is done, subject to the cross-story notes below.
- **Polish (Phase 9)**: Depends on all desired user stories being complete.

### Cross-Story Notes (not independence violations — shared, not blocking)

- User Story 3 (Copilot citations) and User Story 4 (Evidence Explorer) both link into the Document Viewer built in User Story 1 (T065) — US3's citation-linking task (T089) and US4's work can proceed once US1's Document Viewer tasks are merged, but neither US3 nor US4 needs to *rebuild* it.
- User Story 6 (notification navigation, T115) links into the Application Workspace route built in User Story 1 (T069) for the same reason.
- Every other cross-story reference in this document is a "depends on an earlier story's already-merged output," never a circular or blocking relationship — each story remains independently testable once its dependencies exist, per spec.md's own requirement.

### Within Each User Story

- Backend additions (where applicable) before frontend entity layer.
- Entity layer (types, Zod schemas, query hooks) before feature components.
- Feature components before route wiring.
- Route wiring before tests.
- Story complete and checkpointed before considering the next priority tier "in progress" (though parallel staffing across stories is supported once Foundational is done).

### Parallel Opportunities

- All Setup tasks marked `[P]` (T003–T010).
- All token-definition tasks in Foundational marked `[P]` (T011–T019), and all base-component tasks marked `[P]` (T021–T032) — each is an independent file.
- Once Foundational completes, User Stories 1 and 2 (both P1) can be staffed in parallel by different engineers; Stories 3–5 (P2) likewise, once Story 1's Document Viewer (a shared dependency for citations) is merged.
- Within each story, all entity-layer type/schema tasks marked `[P]` can run in parallel; all test tasks marked `[P]` can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch entity-layer type/schema tasks together (different files, no interdependency):
Task: "Create Application types + Zod schema in frontend/src/entities/application/types.ts"
Task: "Create Document types + Zod schema in frontend/src/entities/document/types.ts"
Task: "Create EvidenceItem types + Zod schema in frontend/src/entities/evidence/types.ts"
Task: "Create Finding types + Zod schema in frontend/src/entities/finding/types.ts"

# Launch component tests together once their components exist:
Task: "Component test: FindingCard never renders with a missing explainability field"
Task: "Component test: override submission blocks on empty reason and preserves input on failure"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational — this is the larger investment, but it is what prevents the design-system drift 004's research identifies as the most common enterprise-UX failure mode).
2. Complete Phase 3 (User Story 1).
3. **STOP and VALIDATE** using `quickstart.md` Scenarios 1, 3, 4, 6, 7 against User Story 1 specifically.
4. This alone is a demonstrable, deployable MVP: an underwriter can review a deep-linked application end-to-end with full evidence traceability and a recorded, audited decision.

### Incremental Delivery

Setup + Foundational → US1 (MVP) → US2 (search/queue at scale) → US3 (Copilot) → US4 (Evidence Explorer/relationships) → US5 (saved views/filtering at scale) → US6 (notifications) → Polish. Each checkpoint is independently demoable per spec.md's own story-priority ordering.

### Parallel Team Strategy

Once Foundational is complete: one engineer or pair on US1 (highest complexity: PDF highlight overlay is the single riskiest task in this plan, T065); a second on US2 (queue/search/virtualization); once US1's Document Viewer is merged, additional engineers can pick up US3 and US4 in parallel; US5 and US6 are the lowest-complexity, most parallelizable remaining stories and are good candidates for engineers rotating off other stories as they complete.

---

## Notes

- `[P]` tasks touch different files with no unresolved dependency.
- `[Story]` labels trace every task back to spec.md, including backend additions — a story is not "done" until its backend dependency (if any) is also delivered, per `contracts/api-gaps.md`'s sequencing recommendation.
- Backend tasks in this document are additive-only, per the governing instruction; none modify an existing endpoint's contract.
- T065 (evidence-highlight coordinate mapping) is the single task in this entire plan most likely to need re-estimation after a technical spike — flagged here, not buried in `plan.md` alone.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently before proceeding.
- **Post-analysis remediation (T126–T132)**: these tasks were added after a cross-artifact analysis pass, appended with new IDs rather than renumbering any existing task, per the analysis's own change rules (additive, minimal, reviewable). Each is physically placed within the phase/story it belongs to and cross-references the specific finding it resolves (C1, C2, C3, G1, S1). T073, T090, T095, T098, T099, T100, T063, T088 were amended in place (description text only, no ID or file-path change) to resolve I2, A1, A2, A3, D1, P1, and P2.
