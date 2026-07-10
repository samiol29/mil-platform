import { expect, test } from '@playwright/test';

// A minimal, real smoke test for the current state of the application shell.
// This is deliberately not a placeholder for a future feature — it verifies the
// one thing that genuinely exists at this point in the build: the dev server
// serves the app, and the app renders. Feature-level E2E scenarios (per
// tasks.md's per-user-story E2E tasks, e.g. T072) are added alongside their
// corresponding feature work, not here.
//
// The original assertion here checked for a literal "MIL — Underwriter
// Workspace" heading — the pre-Phase-1 placeholder title. The Home Dashboard
// (Phase 1) replaced the bootstrap redirect with a real landing page whose
// H1 is a time-of-day greeting ("Good morning/afternoon/evening, {name}"),
// so this asserts the stable parts instead: the "MIL" wordmark in the
// banner, and that a real greeting heading rendered.
test('the application shell loads and renders', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('banner').getByText('MIL', { exact: true })).toBeVisible();
  await expect(
    page.getByRole('heading', { level: 1, name: /^Good (morning|afternoon|evening)/ }),
  ).toBeVisible();
});
