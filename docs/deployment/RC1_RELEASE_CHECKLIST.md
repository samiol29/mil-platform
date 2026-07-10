# MIL — Release Candidate 1 (RC1) Checklist

This checklist is the outcome of the RC1 stabilization pass (2026-07-10):
a live, end-to-end verification of the platform against the real running
backend and real Gemini API, a full-stack bug-fix pass, and a final
consistency/UX review. It complements — does not replace — the existing
[Deployment Guide](./README.md) (`docs/deployment/README.md`), which already
documents the target process topology, environment variables, and a
production-readiness checklist (§6 there). This document adds what changed
or was newly discovered during this pass, organized by area, plus items the
existing guide didn't yet cover (frontend, testing, accessibility).

**Read this alongside `docs/deployment/README.md` §1** before treating any
item below as a green light: that section already states plainly that the
platform is supported **only in development** today (single-process,
in-memory job queue) pending a broker-backed `JobQueue`/`EventBus` — nothing
in this RC1 pass changes that. See the Roadmap (`docs/ROADMAP.md`) for what
closing that gap requires.

---

## Backend

- [x] Full pipeline verified live against the real backend + real Gemini API
      (not just unit tests): Application → Borrowers → Upload → OCR →
      Extraction → Evidence → Findings → Policy → Review → Timeline → Audit.
- [x] **Fixed**: Finding-generation prompt (`src/workers/finding_pipeline.py`
      `_build_context`) was phrased as a lookup question ("assess evidence
      for application {id}") against a strict grounded-QA system prompt that
      refuses when a fact isn't literally present in the grounding text —
      100% of findings came back as a generic refusal ("the grounding records
      do not contain information related to application X"). Rephrased as a
      direct synthesis instruction. Confirmed live: findings now correctly
      identify real cross-document discrepancies with citations.
- [x] **Fixed**: `GEMINI_MAX_OUTPUT_TOKENS` (was 1024) is shared between
      Gemini 2.5's invisible "thinking" tokens and the visible answer;
      confirmed live (raw API call, `usageMetadata.thoughtsTokenCount`) that
      thinking consumption is dynamic per call, not fixed by `temperature`,
      and can vary enough between similar calls to truncate a finding
      mid-sentence even at a generous budget. Raised to 8192 **and** added a
      new `InferenceContext.thinking_budget` field (additive, optional — see
      `src/mil/kernel/providers/inference.py`), set to `0` (disabled) for
      Finding generation specifically, since it's a deterministic, mechanical
      task where a complete answer matters more than extended reasoning.
- [x] **Fixed — reliability**: `finding_pipeline.py`'s "no evidence" guard and
      `policy_pipeline.py`'s "no active Policy Pack" guard both raised a bare
      domain error (`ValidationError` / `ConflictError`) that propagated past
      the job processor entirely. `workers/bootstrap.py`'s `process_next`
      requeues on **any** unhandled exception unconditionally (no
      retryability check), and `RedisJobQueue.reject` requeues via `LPUSH`
      (the head of the queue, ahead of legitimate jobs) — confirmed live,
      this turned a normal, expected business state (an app with no
      evidence, a tenant with no active Policy Pack) into a poison job that
      starved the entire FINDING or POLICY queue forever. Both are now
      routed through the same terminal-failure handling already used for a
      non-retryable `ProviderError` (mark the step FAILED, do not
      dead-letter, acknowledge the job instead of requeuing it).
      `document_pipeline.py` / `extraction_pipeline.py` / `review_pipeline.py`
      were checked and do not exhibit this pattern (their only bare raises
      are `NotFoundError` for genuine referential-integrity failures, not
      normal business states).
- [ ] **Known gap, not fixed this pass (see Roadmap)**: the job queue itself
      has no redelivery/visibility-timeout for a worker that dies *mid-job*
      (confirmed live: a POLICY job was lost this way during this session's
      own worker restarts, leaving its `WorkflowStep` stuck `PENDING` with
      nothing in Redis). This is a different, deeper problem than the poison
      job above — a proper fix needs either Redis Streams (`XCLAIM`) or an
      explicit heartbeat/visibility-timeout mechanism, which is a real
      architecture change, correctly out of scope for a stabilization pass.
      Already implicitly covered by `docs/deployment/README.md` §1's
      "not a distributed production deployment" caveat.
- [ ] **Known gap**: there is no API route or seed script anywhere that
      creates/activates a `PolicyPack` — confirmed by grep across
      `src/mil/api/v1/*.py` and `scripts/`. Every application in this
      project's history has had `policy_version: null` because Policy
      evaluation had never once had a pack to evaluate against, not because
      of a bug in the evaluation logic. A pack was created directly via the
      domain model for this pass's verification only (not committed as a
      migration/fixture) — see Roadmap for the real fix (a `PolicyPack`
      seed/admin capability).
- [x] `MIL_SECRET_KEY` / `POSTGRES_PASSWORD` placeholder-rejection reviewed —
      **flagged, not fixed**: `tests/unit/kernel/test_config.py::
      TestProductionSafetyValidator::test_placeholder_secret_key_fails_in_production`
      fails on a clean checkout with no code changes (confirmed via
      `git stash`) — the real production-safety validator this test exercises
      may not be catching a placeholder secret key in the real environment
      this test runs against. Investigate before relying on this gate.
- [ ] Multiple stale backend/worker processes were found running
      simultaneously from different sessions on the same dev machine (one set
      bound to `0.0.0.0:8000`, from two days prior) — caused a real, confusing
      flaky-404 symptom during this pass. Not a code bug, but worth a
      documented convention (a `make stop-dev`/pidfile check) so a fresh
      `make run-api` doesn't silently collide with an orphaned instance.

## Workers

- [x] All 5 workers (`document`, `extraction`, `finding`, `policy`, `review`
      pipelines) confirmed running and processing real jobs end-to-end.
- [x] Finding and Policy pipeline fixes above verified with a full
      stop/restart of all 5 workers + the API server (not just a hot-reload),
      confirming the fix survives a real process restart, not just the
      in-memory state of a long-running dev session.

## Database

- [x] Schema-per-bounded-context structure confirmed intact (`core`,
      `audit`, `evidence`, `finding`, `policy`, `orchestrator`, `review`,
      `copilot` schemas) via direct inspection this pass.
- [ ] No migration/fixture exists to seed a default `PolicyPack` for a new
      tenant (see Backend section above) — worth adding as part of the
      Policy Pack administration work in the Roadmap, not a schema change.

## Gemini configuration

- [x] `GEMINI_API_KEY` / `GEMINI_MODEL` / `GEMINI_BASE_URL` confirmed wired
      correctly end-to-end against the real API (OCR, extraction, and
      Finding-generation inference calls all verified live).
- [x] `GEMINI_MAX_OUTPUT_TOKENS` raised 1024 → 8192 (see Backend). Update
      `.env`/`.env.example` already applied.
- [x] New `thinking_budget` seam added to `InferenceContext` — future
      Gemini-backed features (e.g. a real Policy rule engine, Copilot) should
      consider explicitly setting it rather than relying on the model's
      dynamic default, especially for deterministic/mechanical tasks.
- [ ] **Free-tier quota is a real, hard constraint for demos**: confirmed
      live this pass — `generate_content_free_tier_requests, limit: 20`
      requests/day for `gemini-2.5-flash`. A single realistic 2-document
      application consumes ~3 calls (2 OCR/extraction + 1 Finding
      generation); the full 8-scenario demo dataset (see below) costs
      roughly 17 calls. Budget for a paid tier or spread demo-data seeding
      across multiple days before a real demonstration.

## Environment variables

- [x] Full inventory reviewed against `.env.example` (`MIL_ENV`,
      `MIL_SECRET_KEY`, Postgres/MinIO/Redis connection vars, the Gemini
      cluster above, `OTEL_*`, `WORKER_CONCURRENCY`/`WORKER_JOB_TIMEOUT`) —
      no undocumented variables found in `.env` beyond what
      `.env.example` already lists.
- [x] `.env`/`.env.example` kept in sync for the `GEMINI_MAX_OUTPUT_TOKENS`
      change this pass.

## Authentication

- [x] Confirmed still dev-bearer only (`DevBearerIdentityProvider`, token
      literally `"dev"`) — matches `docs/deployment/README.md`'s own
      documented scope; no production `IdentityProvider` (OIDC/JWKS) exists
      yet. Not attempted this pass (explicitly out of scope — "do not invent
      backend functionality").

## RBAC

- [x] Re-audited `src/mil/kernel/security.py`'s `ROLE_PERMISSIONS` against
      the frontend's `READ_ONLY_ROLES` (`app/auth/authProvider.ts`) — a
      Phase-12 audit flagged `RISK_ANALYST` appearing in both the frontend's
      read-only list and `FindingActions.tsx`'s escalation-target list as a
      possible bug; re-verified directly against the backend's real
      permission grants and confirmed **not a bug** — `RISK_ANALYST` is
      correctly read-only server-side (no `VERIFY_FINDING`/`OVERRIDE_FINDING`/
      `ESCALATE_FINDING` permission), so hiding those controls for that role
      matches backend truth exactly. No change made.

## Testing

- [x] Frontend: 254/254 Vitest tests pass; `tsc -b --noEmit` (the project's
      actual `npm run typecheck`/`npm run build` command) is clean for the
      first time this project's real config was actually exercised — see
      the "known tooling gap" note below.
- [x] Backend: 1822/1823 unit + provider-conformance tests pass (the one
      failure, `test_placeholder_secret_key_fails_in_production`, is
      pre-existing and unrelated to this pass's changes — flagged above).
- [x] **Known tooling gap, fixed this pass**: `npx tsc --noEmit` (no
      `--project`/`-b` flag) run against this repo's solution-style root
      `tsconfig.json` (`{ "files": [], "references": [...] }`) is a silent
      no-op — it always reports zero errors regardless of real state. Every
      prior "tsc clean" claim across this project's phases was checking
      nothing. The actual, correct command
      (`npm run typecheck` = `tsc -b --noEmit`, and `npm run build`'s first
      step) surfaced 15 real, pre-existing `exactOptionalPropertyTypes` /
      stale-typing errors — all fixed this pass (see commit history / diff
      for the full list; summary: 9 `exactOptionalPropertyTypes` mismatches
      fixed by widening optional-field types or conditional-spreading,
      2 react-hook-form template-literal-path inference issues fixed with a
      type assertion, 1 generic `Tabs` component / region-callback mismatch
      fixed with an inline cast matching an existing precedent in the same
      file, 1 genuinely stale type on `EntityQueryOptions.staleTime` that
      silently accepted a function value it didn't declare support for).
      **Recommendation: always run `npm run typecheck` (not a bare
      `tsc --noEmit`) locally before relying on "typecheck passed."**
- [ ] CI (`.github/workflows/ci.yml`) already runs the correct
      `npm run typecheck` — confirm CI has actually been green recently; if
      these 15 errors were long-standing, either CI wasn't running on this
      branch, or was failing and not being watched.
- [ ] E2E (Playwright) tests exist (`npm run test:e2e` in CI) but were not
      re-run in this pass (this pass's live verification was manual,
      against the real backend, not the Playwright suite) — worth running
      before a real release.

## Accessibility

- [x] No accessibility regressions found in this pass's live walkthrough
      (dashboard, queue, evidence, documents list/viewer, findings, policy,
      timeline, both light and dark themes) — matches Phase 10's dedicated
      accessibility audit, which found the codebase already disciplined here
      (focus-visible treatment, aria-label coverage, Storybook a11y gate).
- [ ] Storybook's `test:storybook` a11y gate (CI) was not re-run this pass —
      no changes were made to any design-system component's accessibility
      surface, so this should be unaffected, but worth confirming in CI.

## Performance

- [x] Production build confirmed clean and unchanged in size from Phase 11
      (main `applications.$applicationId` route chunk ~84KB, `PdfRenderer`
      lazily split at ~426KB, no chunk-size warnings).
- [x] No new performance regressions introduced by this pass's fixes (all
      backend fixes are error-path-only; frontend fixes are type-level only
      except the intentional density/consistency changes already covered in
      the Phase 12 pass).

## Documentation

- [x] This checklist and the accompanying Roadmap (`docs/ROADMAP.md`)
      added this pass.
- [x] `.env` / `.env.example` comments updated to explain the
      `GEMINI_MAX_OUTPUT_TOKENS` change and why.
- [x] New `scripts/seed_demo_dataset.py` — a reusable, realistic 8-scenario
      demo dataset generator (happy path, missing documents, OCR failure,
      income mismatch, identity mismatch, escalation required, manual
      override, clean approval), driven entirely through the real HTTP API
      with real synthetic PDFs (a self-contained minimal PDF writer, no
      OS-specific tool or third-party library dependency). One scenario
      (`missing_documents`, the only one needing zero Gemini calls) was run
      live this pass to confirm the script's mechanics; the remaining 7 need
      a fresh Gemini quota window to run (see the quota note above) — plan to
      run `python scripts/seed_demo_dataset.py --scenario <name>` for the
      rest once quota resets, or `--scenario ocr_failure`/no argument for a
      full run when a paid tier or a fresh day's quota is available.
