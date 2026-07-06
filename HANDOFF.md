# MIL Frontend Implementation — Handoff

**Date**: 2026-07-06
**Branch**: `002-underwriter-workspace`
**Governing artifacts**: `specs/002-underwriter-workspace/{spec.md,plan.md,tasks.md,research.md,data-model.md,contracts/}`, `specs/003-design-system/spec.md`, `specs/004-evidence-based-product-research/spec.md`

**Nothing has been committed, pushed, or merged.** All work described below is uncommitted in the working tree — a human must review before any commit happens.

---

## 1. Current State in One Sentence

Phase 2 (Foundational) is **fully complete**; User Story 1 is complete through **T064** (PDF.js rendering layer) plus T067–T069, T070–T071, and T128; **T065 (evidence-highlight coordinate mapping) has deliberately not been started**, per explicit instruction to stop before it — this is an intentional review checkpoint, not a blocker encountered mid-task.

---

## 2. STOP — Architectural Decision Needed Before T046–T049 Can Be Considered Fully Resolved

**This was investigated and resolved as far as it safely could be without your input; one real gap remains.** Before touching `POST /v1/findings/{id}/escalate` (T049) or the "reject" edge case below, this needs a decision.

### What was found

The Review bounded context (`src/mil/review/`) already implements exactly what "verify" and "override" need — `ReviewService.approve_finding()` and `.override_finding()` — fully built, audited, and tested (US2 Sprint 6, predates this session). T047 and T048 are genuine, unambiguous exposure of existing logic, and are now implemented and tested.

**Escalation is not implemented anywhere in the domain layer.** `src/mil/review/__init__.py`'s own module docstring states: *"Escalation, verification-of-evidence, and any Copilot/notification/reporting integration are out of scope for this sprint."* There is no `ESCALATED` `ReviewStatus`, no `ACTION_ESCALATED`, no `escalate_finding()` method, and no transition rule for it in `_VALID_TRANSITIONS`. `mil.kernel.security.Permission.ESCALATE_FINDING` exists (a permission string), but nothing checks or grants it a real effect.

A second, smaller, related gap: `ReviewStatus` includes `REJECTED` (a real, reachable status via `ReviewService.reject_finding()`), but spec 002's `Finding.state` enum (`data-model.md`) only defines four values: `unreviewed / verified / overridden / escalated` — there is no `"rejected"` frontend state at all, and no endpoint in this workspace calls `reject_finding()` either.

### What was decided without asking (safe, reversible, non-guessing)

- **`findings.py`'s `_finding_state()` maps `REJECTED` (and any other unrecognized status) conservatively to `"unreviewed"`** — never to `"verified"`/`"overridden"`, so a rejected-by-some-other-path finding is never misrepresented as resolved. This is the safe failure direction for a compliance-sensitive review state, not a guess at what it "should" mean.
- **Confidence banding** (`EvidenceItem`/`Finding` raw `Decimal` scores → `"high"/"medium"/"low"`) reuses the platform's own existing, single-source-of-truth `mil.kernel.types.Confidence.label` — not a newly-invented threshold.
- **`policy_version` attribution** is resolved via `PolicyRepository.get_for_finding(finding_id)` (an existing method, joined on `finding_id`) — not omitted, not guessed.
- **Document content retrieval**: no endpoint existed to serve a document's raw bytes at all (`documents.py`'s own docstring: *"Document content (bytes) is not returned — use the Storage API or a signed URL (US2)"*). This directly blocked T064 (PdfRenderer has nothing to render without it). Added `GET /v1/applications/{id}/documents/{id}/content`, following the *exact* existing `StorageProvider.retrieve()` pattern already used by `workers.document_pipeline` — mechanical, not a design decision. Always serves `application/pdf` (the product's only supported document type per the PDF.js architecture decision in `plan.md`; the backend doesn't track a separate real MIME type yet).
- **`Document.filename`**: `DocumentResponse` never exposed `Document.original_filename` (the column has always existed; the response schema simply omitted it). Added as an additive field — the Document Viewer has no other way to label an open document.
- **`Application.borrowerName`**: NOT added to the frontend `Application` type. The backend has no such column (`MortgageApplication` has no borrower-name field at all); a borrower's display name is a `Party.display_name`, sourced separately via the existing `GET /v1/applications/{id}/parties` endpoint. Documented in `entities/application/types.ts`.
- **Queue-row aggregate fields** (`documentCount`, `evidenceCount`, `flaggedFindingCount`, `lastActivityAt`, `slaState`) are NOT on the `Application` entity type — they belong to the Queue endpoint enhancement (User Story 2, T073), which doesn't exist yet. Adding them now would mean parsing fields the API never sends.

### What genuinely needs your decision

**Only `POST /v1/findings/{id}/escalate` (T049) itself** — this requires real domain design, not exposure:

1. Does escalation need a new terminal `ReviewStatus` (e.g., `ESCALATED`), added to `_VALID_TRANSITIONS`? From which states can it be reached?
2. How is the "target role" (spec 002 FR-054 requires one) recorded and attributed — a new column on `ReviewAction`, or reuse `new_value`?
3. Does escalating close the review (like approve/reject/override do), or does it stay open, pending pickup by the target role? If it stays open, what re-opens it?
4. Should `REJECTED` ever be reachable from this workspace at all, or is `reject_finding()` reserved for a different, not-yet-built persona/flow?

**Not touched pending this decision**: `POST /v1/findings/{id}/escalate` endpoint, the `useEscalateFinding` mutation hook, and an escalate control in `FindingActions.tsx`. `FindingActions` currently exposes verify/override only — a real, working subset, not a broken placeholder.

---

## 3. Completed Work (this session)

### Phase 2 completion: T034–T044, T127 (app shell & cross-cutting infra)

| File | Purpose |
|---|---|
| `frontend/src/app/auth/authProvider.ts` | Token/user abstraction; dev-bearer flow; `useAuthUser()` hook |
| `frontend/src/app/auth/httpClient.ts` | Shared Axios instance; auth interceptor; **snake_case→camelCase response interceptor** (see Real Issues below) |
| `frontend/src/app/queryClient.ts` | TanStack Query client + `STALE_TIME` tier constants |
| `frontend/src/app/router.tsx`, `frontend/src/routes/__root.tsx`, `frontend/src/routes/index.tsx` | TanStack Router file-based route tree; `AppProviders` composes Theme+Query+Router |
| `frontend/src/app/uiStore.ts` | Zustand store — command palette + panel-expand state only |
| `frontend/src/app/ErrorBoundary.root.tsx`, `frontend/src/shared/errors/{ErrorBoundaryBase,RouteErrorBoundary,PanelErrorBoundary}.tsx` | Three-tier error boundaries, all reporting through `telemetry.ts` |
| `frontend/src/shared/telemetry/telemetry.ts` | Real console-based `TelemetryReporter`, swappable via `setTelemetryReporter` |
| `frontend/src/shared/api/createEntityQuery.ts` | `fetchEntity`/`useEntityQuery` — the shared Zod-parsing query convention |
| `frontend/src/shared/api/caseTransform.ts` | The snake_case→camelCase transform (see Real Issues) |
| `frontend/src/test/msw/{handlers,server,browser}.ts` | MSW contract-shaped mocks; wired into `test/setup.ts` for all unit tests; browser worker opt-in via `VITE_USE_MSW=true` |
| `frontend/src/app/UserMenu.tsx` | Persistent identity + one-action sign-out (FR-007), mounted in `routes/__root.tsx` |

### Backend additions for User Story 1: T045–T048, T050–T051 (T049 blocked, see §2)

| File | Purpose |
|---|---|
| `src/mil/api/v1/evidence.py` | `GET /v1/applications/{id}/evidence` |
| `src/mil/api/v1/findings.py` | `GET /v1/applications/{id}/findings`, `POST /v1/findings/{id}/verify`, `POST /v1/findings/{id}/override` — no escalate |
| `src/mil/api/v1/audit.py` | `GET /v1/applications/{id}/audit` |
| `src/mil/audit/repository.py` (new) | `AuditRepository.get_for_application` — no reader existed before this session |
| `src/mil/evidence/service.py`, `src/mil/finding/service.py` | Added `list_for_application`/`get_by_id` read methods (permission-checked) |
| `src/mil/api/deps.py` | `get_evidence_service`, `get_finding_service`, `get_audit_repository`, `FindingReviewActions` (verify/override composition root), `get_storage_provider` |
| `src/mil/api/v1/documents.py` | **New** `GET /v1/applications/{id}/documents/{id}/content` (see §2 — required for T064) |
| `src/mil/api/v1/schemas.py` | `EvidenceItemResponse`, `FindingResponse`, `AuditEventResponse`, `VerifyFindingRequest`, `OverrideFindingRequest`; `DocumentResponse.filename` added |
| `src/main.py` | Registered the three new routers |
| Tests | `tests/unit/api/{test_evidence,test_findings,test_audit}.py` (new), `test_documents.py` (content endpoint tests added), `tests/unit/audit/test_repository.py` (new), `tests/unit/evidence/test_service.py` / `tests/unit/finding/test_service.py` (list/get tests added), `tests/unit/api/conftest.py` (new fixtures + factories) |

### Frontend entity layer: T052–T060 (all complete)

`frontend/src/entities/{application,document,evidence,finding,audit}/{types,queries}.ts`. All Zod schemas match the *actual* backend response field names (post-camelCase-transform), not `data-model.md`'s pre-implementation guesses, wherever the two diverged — each divergence is documented in the relevant file's header comment (Constitution Principle VII: match the real backend name).

### Frontend features: T061–T064, T067–T069, T128 (all complete except escalate, per §2)

| File | Purpose |
|---|---|
| `frontend/src/features/application-workspace/ApplicationWorkspace.tsx` | Shell — overview/findings/evidence/documents regions, each in its own `PanelErrorBoundary`; no Copilot region (US3, out of scope) |
| `frontend/src/features/application-workspace/regions.ts` | `WorkspaceRegion` type + labels (split out to satisfy react-refresh's component-only-exports rule) |
| `frontend/src/features/application-workspace/FindingCard.tsx` | Type-gated on the full `Finding` type; all five explainability elements always rendered in the same order |
| `frontend/src/features/application-workspace/FindingActions.tsx` | Verify/override only; React Hook Form + Zod; confirm-as-distinct-step via `Dialog`; failed submissions preserve entered values (React Hook Form's default behavior — no extra recovery code needed) |
| `frontend/src/features/document-viewer/PdfRenderer.tsx` | Renders one page via `pdf.js`, fetched through `httpClient` (so auth applies) — no highlight overlay, no navigation (T065/T066) |
| `frontend/src/features/application-workspace/AuditTimeline.tsx` | Read-only chronological list |
| `frontend/src/features/application-workspace/StaleRecordBanner.tsx` | FR-036's explicit staleness check + one-action refresh |
| `frontend/src/routes/applications.$applicationId.tsx` | Deep-linkable route; `?region=` URL state; computes `readOnly` from the user's role (T128) |

### Tests: T070–T071

`FindingCard.test.tsx` (renders all five explainability elements; a `// @ts-expect-error` case proving the type system rejects an incomplete `Finding`), `FindingActions.test.tsx` (empty-reason blocks submission; a simulated 500 via MSW's `server.use()` proves entered values survive a failed submit).

### Real issues found and fixed this session (future maintainers should know these)

1. **The backend returns snake_case JSON; every entity Zod schema needs camelCase (Constitution Principle VII / `data-model.md`).** Without a transform, *no* entity schema could ever parse a real API response — this would have been discovered the moment any entity hook was used against the real backend. Fixed centrally in `httpClient.ts`'s response interceptor (`shared/api/caseTransform.ts`), not per-entity.
2. **No endpoint existed to retrieve a document's actual file bytes** — `documents.py` explicitly deferred this to "US2 signed URL," but T064 (PdfRenderer) cannot function without *some* way to fetch content. Added the additive `GET .../content` endpoint using the existing `StorageProvider.retrieve()` — see §2 for why this was judged safe to just build rather than another stop.
3. **`DocumentResponse` never exposed `filename`**, despite the column existing since the Document model was first written. Additive fix, tested.
4. See §2 for the Finding/Review/escalate analysis — the one item that remains a genuine open decision.

### Validation performed (this session, repeated after every batch)

```
Backend: ruff check src/ tests/ · ruff format --check · mypy src (120 files, clean) · pytest -q
         → 1747 passed, 1 pre-existing unrelated failure (test_config.py, reproduces on main, untouched by this session), 1 skipped
         compileall src migrations tests → clean

Frontend: npx tsc -b --noEmit · npx eslint . (0 errors; 1 informational React-Compiler note on Table.tsx, pre-existing)
          npx prettier --check . · npm run build · npx vitest run --project unit (all passing, 9 new tests this session)
          npx storybook build · npx vitest run --project storybook (47/47, zero a11y violations, unaffected by this session)
          npx playwright test (3/3, chromium/firefox/webkit)
```

---

## 4. Every File Changed This Session

**Backend — modified**: `src/main.py`, `src/mil/api/deps.py`, `src/mil/api/v1/documents.py`, `src/mil/api/v1/schemas.py`, `src/mil/evidence/service.py`, `src/mil/finding/service.py`, `tests/unit/api/conftest.py`, `tests/unit/api/test_documents.py`, `tests/unit/evidence/test_service.py`, `tests/unit/finding/test_service.py`

**Backend — new**: `src/mil/api/v1/{evidence,findings,audit}.py`, `src/mil/audit/repository.py`, `tests/unit/api/{test_evidence,test_findings,test_audit}.py`, `tests/unit/audit/test_repository.py`

**Frontend — modified**: `frontend/eslint.config.ts` (routes/router react-refresh exception), `frontend/package.json`/`package-lock.json` (added `@tanstack/router-plugin` wiring, `@hookform/resolvers`, MSW worker registration), `frontend/src/main.tsx`, `frontend/src/test/setup.ts`, `frontend/vite.config.ts` (TanStack Router plugin)

**Frontend — new**: `frontend/src/app/{ErrorBoundary.root,UserMenu,queryClient,router,uiStore}.tsx`/`.ts`, `frontend/src/app/auth/{authProvider,httpClient}.ts`, `frontend/src/entities/**` (application/document/evidence/finding/audit), `frontend/src/features/**` (application-workspace/*, document-viewer/PdfRenderer.tsx), `frontend/src/routes/{__root,index,applications.$applicationId}.tsx`, `frontend/src/routeTree.gen.ts` (generated), `frontend/src/shared/**` (errors/, api/, telemetry/), `frontend/src/test/msw/**`, `frontend/src/vite-env.d.ts`, `frontend/public/mockServiceWorker.js` (generated)

**Specs**: `specs/002-underwriter-workspace/tasks.md` (checkboxes updated per §1/§2)

---

## 5. Exact Next Step

**Stop here for review, per explicit instruction — do not begin T065 or any later task.**

1. Decide the four open questions in §2 for T049 (escalate).
2. Once decided, implement T049 (backend), the `useEscalateFinding` hook, and the escalate control in `FindingActions`/`FindingCard`.
3. Then T065 (evidence-highlight coordinate mapping) — flagged in `plan.md` as the single highest-risk task in the entire plan; prototype before treating it as a scheduled, estimable task.
4. T066 (Document Viewer navigation), T072/T129 (E2E tests — both need T065/T066 to be meaningful).

No other work is in flight. This document plus `specs/002-underwriter-workspace/tasks.md` are sufficient to resume from a cold start.
