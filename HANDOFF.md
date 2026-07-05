# MIL Frontend Implementation — Handoff

**Date**: 2026-07-06
**Branch**: `002-underwriter-workspace`
**Governing artifacts**: `specs/002-underwriter-workspace/{spec.md,plan.md,tasks.md,research.md,data-model.md,contracts/}`, `specs/003-design-system/spec.md`, `specs/004-evidence-based-product-research/spec.md`

**Nothing has been committed, pushed, or merged.** All work described below is uncommitted in the working tree, per explicit instruction — a human must review before any commit happens.

---

## 1. Current State in One Sentence

Phase 1 (Setup) and the Design Tokens + Closed Base Component Set portion of Phase 2 (Foundational) — `tasks.md` T001–T033 — are complete and fully validated; **T034 onward (app shell & cross-cutting infrastructure) has deliberately not been started**, per explicit instruction to stop after T033 for review.

---

## 2. Completed Work

### Phase 1: Setup — T001–T010, T126 (complete)

Legacy scaffold removal, TypeScript/ESLint/Prettier/Vite/Vitest/Storybook/Playwright/CI setup (T001–T010); `scripts/seed_large_dataset.py`, a deterministic 100,000+-row seed script for User Story 2 (T126). See prior session history / git diff for full detail.

Also resolved in the prior session: **loan_number** was added as a real, additive `core.applications` column (migration `0011`, model/service/API/contract/tests updated) — backend work, unrelated to this session's frontend focus.

### Phase 2 (partial): Design System foundation — T011–T033 (complete, this session)

**Styling mechanism** (previously an open decision, now fixed as the project standard): **Tailwind CSS v4** + **CSS custom properties** for tokens + **shadcn/ui's underlying primitives** (Radix UI, `cva`, `clsx`/`tailwind-merge`, `cmdk`, `lucide-react`) customized to spec 003 — not shadcn's own visual defaults.

| Area | Files |
|---|---|
| Tailwind v4 wiring | `frontend/vite.config.ts` (`@tailwindcss/vite` plugin), `frontend/.storybook/main.ts` (`viteFinal` adds the same plugin to Storybook's own Vite instance) |
| Token source of truth | `frontend/src/design-system/tokens/tokens.css` — every literal color/typography/radius/motion value in the product lives here, and only here (spec 003 FR-018) |
| Tailwind ↔ token binding | `frontend/src/design-system/theme/globals.css` — `@theme inline` maps every semantic CSS variable into Tailwind's theme namespaces; `@custom-variant dark` makes `dark:` utilities key off `data-theme`, not just OS preference |
| Typed token modules (T011–T019) | `frontend/src/design-system/tokens/{color.primitives,color.semantic,color.status,color.confidence,color.ai,typography,spacing,elevation,motion}.ts` |
| Theme switching (T020) | `frontend/src/design-system/theme/{ThemeContext.ts,ThemeProvider.tsx,useTheme.ts}` — persists to `localStorage`, defaults to OS `prefers-color-scheme`, no reload on switch |
| Closed base components (T021–T032) | `frontend/src/design-system/components/{Button,LoadingState,EmptyState,ErrorState,StatusBadge,ConfidenceIndicator,AiSignalBadge,EvidenceChip,Drawer,Dialog,Table,CommandPalette}/` |
| Storybook stories + a11y (T033) | A `*.stories.tsx` file per component covering every defined state; `.storybook/preview.tsx` wraps every story in `ThemeProvider` with a light/dark toolbar toggle |
| Shared utility | `frontend/src/design-system/lib/cn.ts` — `tailwind-merge` extended with this project's custom token class groups (see Real Issues below — this was not optional boilerplate) |
| App wiring | `frontend/src/main.tsx` imports `globals.css` and mounts `ThemeProvider` around the existing minimal `Root` (router/query/auth wiring is explicitly T034+, not done) |

### Real issues found and fixed during this phase (future maintainers should know these)

1. **`tailwind-merge` silently dropped classes** — our custom `text-<type-scale-step>` (font-size, e.g. `text-caption`) and `text-<semantic-color>` (color, e.g. `text-text-on-brand`) utilities both share the bare `text-` prefix, which `tailwind-merge`'s default heuristics cannot tell apart from Tailwind's own built-in classes. Left unconfigured, it treated every `text-*` class as one conflicting group and kept only the last one — concretely, `Button`'s `size="sm"` variant was silently deleting the `primary` variant's `text-text-on-brand` color class. **This was caught for real by the Storybook `a11y` gate** (a genuine color-contrast violation, not a hypothetical one), not discovered by inspection. Fixed in `cn.ts` via `extendTailwindMerge`. **Any new component that introduces a new `text-*`-prefixed semantic token must add it to `cn.ts`'s `classGroups` config**, or risk the same silent-drop failure mode.
2. **`cmdk`'s `<CommandList>` (`role="listbox"`) + built-in `<CommandEmpty>` (`role="presentation"`) violates `aria-required-children`** when `CommandEmpty` is the list's only child — a known upstream cmdk/axe friction point, also caught by the `a11y` gate. Fixed in `CommandPalette.tsx` by rendering the empty message as a non-interactive `role="option"` inside the always-mounted `<CommandList>` instead of using `<CommandEmpty>` — keeps `aria-controls` references intact (an initial fix attempt that unmounted `<CommandList>` entirely broke that reference; documented in the component's own comment so it isn't tried again).
3. `ConfidenceIndicator`'s `role="meter"` needs an explicit `aria-label` in addition to `aria-valuetext` — axe's `aria-meter-name` rule.
4. Two color-contrast token misses (`ErrorState`'s `<summary>`/`<pre>` at `text-tertiary` on the error-tinted background; measured 3.89:1, needs 4.5:1) — changed to `text-secondary`.
5. `.storybook/preview.tsx` importing app-source modules (for the `ThemeProvider` decorator) needed `tsconfig.node.json` widened (path aliases, `DOM` lib, `vite/client` types, and `src/design-system/**` added to its `include`) — TypeScript's composite-project mode requires every file a project reaches via import to be a declared member of that project or a formally referenced one; `tsconfig.app.json` can't be a formal reference target because it has `noEmit: true`.

### Validation performed (this session)

```
npx tsc -b --noEmit          # clean
npx eslint .                 # 0 errors (1 informational React-Compiler note on Table.tsx, expected/harmless)
npx prettier --check .       # clean
npx vitest run --project unit        # 1/1 passed
npm run build                        # succeeds (CSS: 38.9KB, JS: 191KB)
npx storybook build                  # succeeds
npx vitest run --project storybook   # 47/47 passed, light theme (default) — zero a11y violations
npx vitest run --project storybook   # 47/47 passed, dark theme (manually flipped initialGlobals, then reverted to light) — zero a11y violations
npx playwright test --config=e2e/playwright.config.ts   # 3/3 passed (chromium, firefox, webkit)
```

Both themes independently pass the automated `a11y` gate with zero violations, per plan.md's Accessibility Strategy requirement that a theme's contrast conformance is never inferred from the other theme's result.

**Design decisions made without a explicit spec value** (spec 003 deliberately leaves literal values unspecified — see its Assumptions section): the actual color hex values, the 8-step type scale's exact sizes, the spacing/radius/motion literal values, and the specific icon choices (`lucide-react`, matching shadcn/ui's own convention) were all invented in this session per 003's *structural* rules (two-tier token architecture, 3 structurally distinct color families, 8 type-scale steps, WCAG AA contrast, etc.). These are production values now, not placeholders, but are the kind of decision 003 explicitly defers to implementation — flagging this so a designer reviewing this work knows where to focus.

---

## 3. Exact Next Step

**Stop here for review, per explicit instruction.** Do not begin T034 until told to proceed.

Once approved, the next unit of work is **T034–T044 + T127** (app shell & cross-cutting infrastructure): HTTP client, auth abstraction, TanStack Query client, TanStack Router root route tree (composing Theme+Query+Router), Zustand UI store, three-tier error boundaries, telemetry module, the shared entity-query-hook convention, MSW handlers, and the persistent user-identity/sign-out control. This is the last Foundational work before any User Story (Phase 3+) can begin.

No other work is in flight. This document plus `specs/002-underwriter-workspace/tasks.md` (source of truth for task-level status) are sufficient to resume from a cold start.
