# RC2 Product Hardening & Stabilization Report

**Date**: 2026-07-12
**Scope**: quality/reliability hardening pass over the completed 17-module Enterprise
Platform (`specs/005-enterprise-platform/spec.md`, Waves 1–4). No new product modules,
no scope expansion, no workflow redesign — per this sprint's own explicit constraints.

## How this pass was run

Given the size of the platform (17 modules, ~160 backend source files, ~330 test files,
frontend with 29+ test files and 22+ Storybook stories), this pass prioritized **real,
verifiable findings over exhaustive manual review of every screen**. Concretely: every
CI-equivalent tool was run end-to-end across the *entire* codebase (not just recently-added
code, which is what every prior wave's own verification pass had checked) to surface actual
drift, plus targeted checks in the areas most likely to have accumulated debt (test-file lint
debt, formatter drift, dead code, live boundary checks). Findings below are what that process
actually surfaced — nothing here is speculative.

---

## 1. Reliability / CI hygiene (highest-value finding this pass)

**Both of this project's CI format/lint gates were silently broken platform-wide** —
not from any single wave's work, but from dependency drift accumulated over the life of
the project:

- `ruff check src tests`: 35 real findings across pre-existing test files (unused
  unpacked variables, imports that should be under `TYPE_CHECKING`, one unused import,
  two blind `pytest.raises(Exception)` assertions that should name the real exception).
  None of these were introduced by Wave 1–4 work — they were pre-existing debt in test
  files from `assignment`, `identity`, `integration`, `notification`, `policy`, `review`
  that had simply never been caught, because this project's `ruff>=0.8.0` pin means each
  `pip install` can resolve a newer ruff with slightly different lint-rule behavior, and
  no one had re-run the full-tree check recently. **Fixed**: all 35 resolved (renamed to
  `_`-prefixed dummy vars, moved value-only-as-annotation imports under
  `TYPE_CHECKING`, named the real exception type).
- `ruff format --check src tests`: **40 files** would have failed formatting —
  again, none from this session's own new code, all pre-existing. Root cause: ruff's own
  documentation states the *formatter* (unlike the linter) is not covered by its semver
  stability guarantee — a minor version bump can silently reformat working code
  differently. This project's unbounded `ruff>=0.8.0` pin meant CI was resolving whatever
  the latest ruff happened to be on each run. **Fixed**: reformatted all 40 files (pure
  formatting diffs, verified zero logic change via `ruff format --diff` before applying
  broadly), and added an upper bound (`ruff>=0.8.0,<0.16.0`) to `pyproject.toml` so this
  doesn't silently recur — a deliberate version bump is now required to accept a new
  formatter's output, rather than an unpinned `pip install` doing it invisibly.
- `npm run format:check` (Prettier): **20 frontend files** had the same drift.
  **Fixed**: reformatted (`prettier --write .`), reverified `typecheck`/`lint`/`test`/
  `build` all still pass after.

**Why this matters more than it might first appear**: this project's own CI workflow
(`.github/workflows/ci.yml`) runs exactly these checks on every push/PR. If they were
failing before this pass, **CI was red** — meaning either this had gone unnoticed, or
every recent PR had been merged without a fully green run. This is a genuine production-
readiness gap fixed, not a cosmetic one.

## 2. Real bugs found and fixed

- **`CrossApplicationIntelligenceWorkspace.get_signals`** (Wave 3, `mil/api/deps.py`)
  referenced `Document.filename`, which does not exist on the `Document` model — the real
  field is `original_filename`. This was masked because the only test exercising this
  method mocked the entire workspace class (never touching the real composition logic
  inside it) — a real test-coverage gap, not just a typo. Caught by running `mypy src`
  across the whole tree (162 files) for the first time this session, not by any existing
  test. **Fixed** — one-line correction, `mypy src` now clean with zero errors.
- **`AuthenticationError` had no dedicated FastAPI exception handler** — it fell through to
  the generic `MILError` catch-all and returned a misleading `500` instead of `401`. This
  had gone unnoticed because every prior call site (`get_current_user`) manually caught and
  converted it; the Wave 4 Customer Portal activation endpoint was the first code path to
  raise it as a raw domain exception. **Fixed** — added a proper 401 handler in
  `mil/api/errors.py`, verified live (`curl` against a running server: wrong activation
  token now correctly returns 401, not 500).
- **Production-safety validator gap** (found during Wave 4, re-confirmed and generalized
  here): the checked-in `.env`'s own placeholder value
  (`changeme-use-openssl-rand-hex-32-in-production`) was not in the exact-match
  `_insecure_markers` set the validator checked against, meaning a real deployment that
  forgot to override `MIL_SECRET_KEY` in production would have silently passed the safety
  check. Fixed to a substring match (`"changeme" in value.lower()`), which also happened to
  fix a previously-failing, seemingly-unrelated test
  (`TestProductionSafetyValidator::test_placeholder_secret_key_fails_in_production`) that
  every prior wave's report had listed as "1 pre-existing unrelated failure" — it wasn't
  unrelated at all, it was this exact bug.

## 3. Verification results (full, not partial)

Every one of these was run across the **entire** codebase, not a subset:

| Check | Result |
|---|---|
| `ruff check src tests` | **Clean** (0 findings, was 35) |
| `ruff format --check src tests` | **Clean** (0 files need reformatting, was 40) |
| `mypy src` | **Clean**, 162 source files, 0 errors |
| `pytest tests/` (unit + integration + provider) | **2109 passed, 1 skipped, 0 failed** |
| `npm run typecheck` (`tsc -b`) | **Clean** |
| `npm run lint` (ESLint) | **Clean** (1 pre-existing, unrelated React Compiler advisory warning on `Table.tsx`, not an error) |
| `npm run format:check` (Prettier) | **Clean** (0 files, was 20) |
| `npm run test` (Vitest unit) | **198 passed** |
| `npm run test:storybook` (a11y hard gate) | **74 passed**, 22 story files |
| `npm run build-storybook` | Succeeds |
| `npm run build` (production Vite build) | Succeeds |
| Playwright E2E (chromium) | **11 passed, 1 skipped** |
| OpenAPI generation | Succeeds, 77 routes, single consistent schema |
| Alembic migration chain | Linear, single head (`0021`), no branching, applies cleanly from `<base>` |
| Live verification against a real running server + Postgres + Redis | Confirmed: health/ready probes, job-queue-health counters, retention-policy CRUD, the DB-level constitutional constraint (422), and cross-realm auth rejection (401) all behave correctly against real infrastructure |

This is the first point in this project's lifetime (across all four implementation waves)
where every one of these checks has been run, and passed, across the *entire* tree in one
sitting — prior waves' "all green" reports were scoped to each wave's own new/touched files.

## 4. What was deliberately *not* done, and why

Per this sprint's own explicit constraints ("do not redesign completed workflows," "do
not invent backend functionality," "only improve what already exists"), the following were
consciously scoped out rather than attempted shallowly across 17 modules:

- **A full manual UI audit of every screen** (spacing/typography/iconography/density) —
  Phases 10–12 of the original Product Experience plan already ran exactly this kind of
  audit and fixed what it found; re-running an equally deep pass over the *entire* platform
  (including the newer Wave 2–4 screens, which already followed the established Phase 11
  design tokens/patterns when built) was judged lower-value than the concrete, verifiable
  CI/correctness fixes above, given the effort available. The newer screens (Borrower
  Profile, Operational Dashboard, Business Analytics, Customer Portal, Compliance panel)
  were spot-checked for the specific anti-patterns Phase 11 called out (raw borders instead
  of `shadow-raised`, missing `focus-visible` treatment on custom interactive elements,
  missing empty/loading states) and found already consistent — they were built against the
  same design tokens from the start, not retrofitted.
- **Accessibility**: the existing Storybook a11y hard gate (axe-core, enforced globally via
  `.storybook/preview.tsx`) already covers every design-system component and passed cleanly
  (74/74). A full manual screen-reader/keyboard-navigation walkthrough of all 17 modules'
  pages was not performed — that is real, valuable future work, but is a multi-day audit in
  its own right, not a "spot fix" this pass's budget could honestly claim to complete.
- **Performance**: no N+1 query pattern, missing memoization, or bundle-size regression was
  found in the areas inspected (Wave 3/4 composition classes, which are the newest and least
  reviewed code). The production build's one bundle-size advisory (`pdfjs-dist` chunk) was
  already identified and addressed via lazy-loading in an earlier phase (Phase 10) and
  remains addressed. No new performance work was done this pass because no new bottleneck
  was found — inventing tuning work with no measured problem would violate this sprint's own
  "every improvement must have a measurable benefit" rule.
- **Rewriting `docs/ROADMAP.md`**: this document describes the original MVP scope and predates
  the Enterprise Platform expansion. Rather than rewrite it (a documentation *redesign*, which
  this sprint's own rules caution against for product surfaces and which applies here too — the
  document is a historical record of real reasoning that stays useful as-is), a short note was
  added at the top pointing to the spec's own implementation-correction notes and this report.

## 5. Final assessment of production readiness

**Unchanged from the Wave 4 report's own honest assessment**: the platform is feature-
complete across all 17 spec-005 modules and is now genuinely **CI-green end-to-end** for
the first time — a real, newly-verified reliability improvement this pass produced, not
merely reconfirmed. It remains **Ready for Demo, not yet Ready for Production**, for the
same architectural reason previously disclosed and not re-litigated here: `EventBus`
has no broker-backed implementation (only `InProcessEventBus`, unconditionally registered),
which is why `build_container` refuses to start any non-development process today. No
amount of hardening within this pass's scope ("improve what already exists," "do not invent
backend functionality") changes that — implementing a broker-backed `EventBus` is new
infrastructure work, explicitly out of scope for a quality-hardening sprint.

**Remaining honest limitations** (unchanged, not newly discovered, listed for completeness
per this sprint's own "identify remaining technical debt honestly" requirement):
no secrets-manager/OpenTelemetry-tracing integration exists; no disaster-recovery drill has
actually been run (the runbook is documented, untested); a full manual accessibility
walkthrough beyond the automated axe-core gate has not been performed; `docs/ROADMAP.md`'s
body still describes only the original MVP scope (noted, not rewritten, per §4 above).
