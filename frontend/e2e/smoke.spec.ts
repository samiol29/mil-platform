import { expect, test } from '@playwright/test';

// A minimal, real smoke test for the current state of the application shell.
// This is deliberately not a placeholder for a future feature — it verifies the
// one thing that genuinely exists at this point in the build (Phase 1 Setup):
// the dev server serves the app, and the app renders. Feature-level E2E
// scenarios (per tasks.md's per-user-story E2E tasks, e.g. T072) are added
// alongside their corresponding feature work, not here.
test('the application shell loads and renders', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'MIL — Underwriter Workspace' })).toBeVisible();
});
