> **Archived**: session handoff note from 2026-07-06, superseded by current specs under
> `specs/`. Kept for historical reference; still cited from code/doc comments that
> describe the Review/Escalation domain-design decisions made in this session.

# MIL Frontend Implementation — Handoff

**Date**: 2026-07-06
**Branch**: `002-underwriter-workspace`
**Governing artifacts**: `specs/002-underwriter-workspace/{spec.md,plan.md,tasks.md,research.md,data-model.md,contracts/}`, `specs/003-design-system/spec.md`, `specs/004-evidence-based-product-research/spec.md`

**Nothing has been committed, pushed, or merged.** All work described below is uncommitted in the working tree — a human must review before any commit happens.

---

## 1. Current State in One Sentence

**User Story 1 (the MVP) is complete and fully validated** — every task through T072/T128/T129 is implemented, tested, and passing; the only deliberately-out-of-scope pieces are the application-level "all findings resolved" status transition and the underwriter queue (both User Story 2), and one narrow, documented Chromium-only scoping decision in the E2E suite (see §4).

---

## 2. The Review/Escalation Domain Design (resolved this session)

The prior handoff flagged `POST /v1/findings/{id}/escalate` (T049) as blocked pending a real domain-design decision — no backend logic for escalation existed, only the permission string. A focused design review was performed (three designs proposed, trade-offs weighed against the Review bounded context's own stated philosophy and the *original*, more detailed `specs/001-mil-platform-spec/data-model.md` design — which had already fully thought through the lifecycle but was never implemented). **Design B was approved** with refinements:

- `ESCALATED` is a **non-terminal** `ReviewSession` status — resolved by the *existing* `approve_finding`/`reject_finding`/`override_finding` methods, not a new "resolve escalation" action.
- Escalating transfers ownership: `assigned_reviewer_id` is cleared, `escalated_to_role` (and, optionally, a specific `escalated_to_user_id` — a nullable slot for a future direct-assignment refinement) is set.
- Resolving an escalated session requires the existing `VERIFY_FINDING`/`OVERRIDE_FINDING` permission **and** that the acting user's role matches `escalated_to_role` (or, if set, that they *are* `escalated_to_user_id`).
- No new bounded context, no new generic "resolve escalation" permission — deliberately minimal, matching the Review module's own stated aversion to a fourth table/action for what a `ReviewAction` row (with two new columns, `target_role`/`target_user_id`) already fully captures.
- `REVIEW_FINDING_ESCALATED` is the new audit event; existing events (`REVIEW_FINDING_APPROVED`/`REJECTED`/`OVERRIDDEN`) now also fire when *resolving* an escalation — no new event type needed there, since `ReviewAction.previous_status/new_status` already threads the full `IN_REVIEW → ESCALATED → APPROVED` history.
- Notifications are explicitly **not** wired — that's User Story 6's job; consistent with the sibling actions (`approve`/`override`), which also publish nothing to the outbox today.

**A real, pre-existing security gap was found and fixed as part of this work**: the `POST /v1/findings/{id}/verify` and `/override` endpoints had **no permission check at all** — confirmed via grep, `require_permission` was never called for them. `FindingReviewActions.verify()`/`.override()` now require `VERIFY_FINDING`/`OVERRIDE_FINDING` respectively, matching the established per-service permission-check convention used elsewhere (`ApplicationService`, `EvidenceService`, `FindingService`).

Migration `0012_review_escalation.py` adds `review_sessions.escalated_to_role`/`escalated_to_user_id` and `review_actions.target_role`/`target_user_id`.

---

## 3. What Was Built This Session

### Backend
- `src/mil/review/models.py`: `ESCALATED` status (non-terminal), `_VALID_TRANSITIONS` extended (`{PENDING_REVIEW,IN_REVIEW} → ESCALATED → {APPROVED,REJECTED,OVERRIDDEN,ESCALATED}` — re-escalation permitted), `ACTION_ESCALATED`, `ReviewSession.escalate()`, new `ReviewAction.target_role`/`target_user_id` columns.
- `src/mil/review/service.py`: `ReviewService.escalate_finding()` — pure addition, zero changes to `approve_finding`/`reject_finding`/`override_finding` signatures (all 13+ existing tests pass unchanged).
- `src/mil/review/repository.py`: `get_escalated_for_role()` — not yet wired to an endpoint (queue endpoints are US2), provided so the "escalation places it into the target role's queue" data effect is real and queryable once that endpoint exists.
- `src/mil/api/deps.py`: `FindingReviewActions.verify()`/`.override()` now take the full `AuthenticatedUser` (not just `actor_user_id`) and enforce permission + `_authorize_resolution()` (the escalation-ownership check); new `.escalate()` method.
- `src/mil/api/v1/findings.py`: new `POST /v1/findings/{id}/escalate`; `_finding_state()` now maps `ESCALATED` → `"escalated"` (previously an unreachable branch).
- `src/mil/api/v1/schemas.py`: `EscalateFindingRequest`; `FindingResponse` gains `escalated_to_role`/`escalated_to_user_id`.
- Migration `0012_review_escalation.py`.
- Tests: `tests/unit/review/{test_models,test_service,test_repository}.py` (escalation transitions/service/repository), `tests/unit/api/test_findings.py` (rewritten — escalate endpoint, permission-error paths for all three actions).

### Frontend — T065 (evidence-highlight coordinate mapping)
- `frontend/src/features/document-viewer/coordinateMapping.ts`: the actual novel-engineering deliverable — `computeHighlightRect()` maps `FieldLocation.boundingBox` (image-convention `[x,y,w,h]` fractions, `[0,1]`) into PDF.js's rendered viewport space via `PDFPageViewport.convertToViewportPoint`, taking min/max of the transformed corners so it's correct across all four rotations (0/90/180/270) without a rotation-specific branch.
- `frontend/src/features/document-viewer/EvidenceHighlightOverlay.tsx`: renders the computed rect, `aria-hidden` (decorative — duplicates information already in text).
- `frontend/src/entities/evidence/types.ts`: `fieldLocation` upgraded from an untyped `z.record(...)` blob to a real `fieldLocationSchema` (`pageNumber`/`fieldName`/`boundingBox`).
- **Tests**: `coordinateMapping`/`EvidenceHighlightOverlay` covered by 25 unit tests verified against an *independent re-implementation* of PDF.js's own documented viewport-transform formula (not a mock of the library being tested) across multiple scales and all four rotations — this is the rigor plan.md's Risk table asks for ("prototype... before treating as a scheduled, estimable task").
- **Assumption flagged in code**: `boundingBox` is assumed top-left-origin, y-down (image/OCR convention) — no production extraction provider populates real coordinates yet (only `mock_extraction.py`'s synthetic fixture does); if a real provider later uses PDF-native bottom-left origin, only one small function needs to change.

### Frontend — T066 (Document Viewer navigation)
- `frontend/src/features/document-viewer/DocumentViewer.tsx`: page jump (prev/next + numeric entry), zoom (in/out, 0.6×–3.0×), a document switcher for multiple documents, and `jumpTarget` wiring for FR-039 (evidence-chip click → jump to that document/page/highlight).
- **Scoping decision, disclosed in the file's own header comment**: "pinned-vs-preview tabs" (plan.md's own architectural *framing* of FR-044) was not built as a distinct interaction mode — FR-044's literal text only requires "switching between documents without losing place in other regions" (already true structurally, since each workspace region mounts independently). A VS Code-style preview/pin model is a specific interaction design no FR specifies (which click pins? does a preview tab get replaced or accumulate?) — building it would be guessing UI behavior, which the session's own rules forbid.
- `ApplicationWorkspace.tsx` now lifts `jumpTarget` state to coordinate `FindingsRegion`'s evidence-chip clicks with `DocumentViewer` — clicking an evidence chip switches to the Documents region and jumps directly to that evidence's page/highlight (FR-039), replacing the prior no-op placeholder.
- `PdfRenderer.tsx` gained a `scale` prop (previously hardcoded to `1.2`) so `DocumentViewer` can drive zoom.
- 10 new component tests in `DocumentViewer.test.tsx`.

### Frontend — T072/T129 (E2E tests)
- `frontend/e2e/application-workspace.spec.ts`: covers spec 002's User Story 1 Acceptance Scenarios 1–4 (explainability, evidence-to-document navigation, override-requires-reason, interrupted-submission-preserves-input), plus escalate and Document Viewer page/zoom navigation. **Scenario 5** ("application status advances and leaves the queue") is `test.fixme` with a clear reason — it needs an application-level status transition and the underwriter queue, neither of which exists (User Story 2).
- `frontend/e2e/application-workspace-readonly.spec.ts`: T129 — verifies a `COMPLIANCE_OFFICER`/`AUDIT_TEAM` session renders zero action controls in the DOM (not disabled — absent), via a new dev/E2E-only `?devRole=` override in `authProvider.ts` (gated behind `import.meta.env.DEV`, compiled out of production builds entirely — there's no real multi-role login flow yet, which is intentionally out of scope until the production IdentityProvider ships).
- **Chromium-only scoping for the three mutation-heavy specs** (override/escalate flows): Firefox/WebKit exhibited a Playwright test-infrastructure interaction — MSW's browser Service Worker module state (used to make the mock findings list reflect prior verify/override/escalate calls) can outlive a single page's JS realm across sequential tests in the same worker process, and the reset-then-renavigate sequence needed to work around that triggered intermittent multi-minute "waiting for navigation to finish" hangs specific to those two engines. This is a test-tooling quirk, not a product defect — the identical flows (empty-reason validation, submission, network-failure-preserves-input) are already covered browser-independently by `FindingActions.test.tsx`. Documented in the spec file's own header comment (`skipUnlessChromium`).

### Real defects found and fixed along the way (not the main task, but necessary to get there)
1. **`httpClient.ts`'s response interceptor corrupted binary responses.** `camelCaseKeysDeep` treated an `ArrayBuffer` (PdfRenderer's document-content fetch) as a plain object (its own enumerable properties are empty), silently replacing it with `{}` — surfaced as `"bytes.slice is not a function"` the first time an E2E test actually exercised a full PDF fetch. Fixed by skipping the transform for `ArrayBuffer`/`Blob` responses.
2. **MSW fixtures had drifted from the real Zod schemas** in three places, each only surfacing once a test finally exercised a full successful round-trip through them (none had before): (a) placeholder UUIDs (`11111111-1111-1111-1111-...`) aren't RFC 4122-compliant, which `z.uuid()` rejects — fixed by using compliant variants; (b) `fixtureApplication` was missing `activePolicyPackId`/`partyCount` (required fields) and carried several fields the real endpoint doesn't send; (c) `fixtureEvidenceItem` used an entirely different, pre-schema field naming scheme (`value`/`fieldType`/`page`/`extractionConfidence`/`verificationStatus`/`conflictsWith` — none of which exist on the real type). All three rewritten to match their actual Zod schemas exactly.
3. **No MSW handlers existed at all for the documents list or content endpoints** — needed for `DocumentViewer`/`PdfRenderer` to function in dev mode or E2E. Added both, plus `pdfFixture.ts` — a minimal, valid single-page PDF built with *programmatically computed* `xref` byte offsets (not hand-typed magic numbers that would silently drift), verified directly against `pdfjs-dist` before being wired in.
4. **jsdom (the unit-test environment) doesn't implement `DOMMatrix`**, which `pdfjs-dist`'s bundle references at module-load time — merely *importing* `PdfRenderer.tsx` (as `DocumentViewer.tsx` now does) threw `ReferenceError: DOMMatrix is not defined` in any unit test. Added a minimal identity-only polyfill to `test/setup.ts`, scoped with a comment explaining it only needs to satisfy module evaluation (real PDF rendering is exercised in Storybook/Playwright's actual browser environment, not jsdom).

---

## 4. Validation (this session, repeated after every batch)

```
Backend:  ruff check · ruff format --check · mypy src (120 files, clean) · pytest -q
          → 1786 passed, 1 pre-existing unrelated failure (test_config.py, reproduces
            on main untouched by any session), 1 skipped
          compileall src migrations tests → clean

Frontend: tsc -b --noEmit · eslint . (0 errors; 1 informational React-Compiler note
          on Table.tsx, pre-existing, unrelated) · prettier --check
          vitest run --project unit → 35/35 passing (25 new: coordinateMapping/
          EvidenceHighlightOverlay rotation-correctness tests, DocumentViewer)
          npm run build → clean production build
          vitest run --project storybook → 47/47, zero a11y violations
          playwright test (all 3 browsers) → 27 passed, 9 skipped (Chromium-only
          scoping ×3 specs ×3 non-Chromium browsers, documented in §3), 0 failed
```

---

## 5. Every File Changed or Added This Session

**Backend — modified**: `src/mil/api/deps.py`, `src/mil/api/v1/findings.py`, `src/mil/api/v1/schemas.py`, `src/mil/review/{models,service,repository}.py`, `tests/unit/api/test_findings.py`, `tests/unit/review/{test_models,test_service,test_repository}.py`

**Backend — new**: `migrations/versions/0012_review_escalation.py`

**Frontend — modified**: `frontend/e2e/playwright.config.ts` (MSW-backed `webServer`), `frontend/src/app/auth/{authProvider,httpClient}.ts`, `frontend/src/entities/evidence/{types,queries}.ts`, `frontend/src/entities/finding/{types,queries}.ts`, `frontend/src/features/application-workspace/{ApplicationWorkspace,FindingActions,FindingCard}.tsx` (+ their `.test.tsx`), `frontend/src/features/document-viewer/PdfRenderer.tsx`, `frontend/src/test/msw/handlers.ts`, `frontend/src/test/setup.ts`, `frontend/tsconfig.node.json`

**Frontend — new**: `frontend/e2e/application-workspace{,-readonly}.spec.ts`, `frontend/src/features/document-viewer/{DocumentViewer,DocumentViewer.test,EvidenceHighlightOverlay,EvidenceHighlightOverlay.test,coordinateMapping}.{ts,tsx}`, `frontend/src/test/msw/pdfFixture.ts`

**Specs**: `specs/002-underwriter-workspace/tasks.md` (T049, T059, T063, T065, T066, T072, T129 checkboxes and annotations updated)

---

## 6. Remaining Work (beyond User Story 1)

Per `tasks.md`'s own phase ordering, the next work is **User Story 2** (Locate Applications Without Technical Identifiers — search/queue/virtualization), which is what scenario 5's application-status-advance-and-queue-departure ultimately depends on. Also still open, deferred to their own user stories per plan.md: US3 (Copilot), US4 (Evidence Explorer relationships/conflicts), US5 (saved filtered views), US6 (notifications) — none of these were touched this session and none were expected to be.

No other architectural questions are currently open for User Story 1.

---

## 7. Review Scores

| Dimension | Score | Why |
|---|---|---|
| **Architecture** | 9/10 | Escalation recovered and extended the *original* platform design (001) rather than inventing one; reused 100% of existing verify/override/reject machinery with zero signature breakage; coordinate mapping built on PDF.js's own public transform API, not a hand-rolled one; every scoping decision (pinned-vs-preview tabs, Chromium-only E2E, escalate target-role set) is disclosed in code, not silently absorbed. |
| **Code Quality** | 9/10 | Strong typing maintained throughout (no `any`, `exactOptionalPropertyTypes` respected); zero lint/type errors; the one `eslint-disable` in the codebase is narrowly scoped with a documented rationale for a confirmed tool false-positive. |
| **Production Readiness** | 8/10 | Fully validated end-to-end (unit, Storybook a11y, E2E, backend); the `?devRole=` E2E hook and Chromium-only E2E scoping are dev/test-only concerns compiled out of production, but both are worth a second pair of eyes before merge given they touch `authProvider.ts`. |
| **Performance** | 8/10 | `DocumentViewer` renders one page/document at a time (never all documents' PDFs simultaneously); no unnecessary re-renders introduced; the coordinate-mapping math is O(1) per highlight. Not yet measured against the Performance Budget CI gate (no large-dataset scenario exists until US2's virtualization work). |
| **Security** | 9/10 | A real, pre-existing gap (verify/override had zero permission checks) was found and fixed, not just worked around; the new escalation-resolution authorization check is enforced server-side (frontend disabling is documented as a UX nicety only, never the authorization boundary). |

---

Nothing has been committed. Ready for review.
