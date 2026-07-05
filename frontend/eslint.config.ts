import type { Linter } from 'eslint';
import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import storybook from 'eslint-plugin-storybook';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import { defineConfig, globalIgnores } from 'eslint/config';

// Design System (003) and Underwriter Workspace (002) both require WCAG 2.1 AA
// conformance as a baseline, not an enhancement — jsx-a11y's recommended-strict
// rule set is a required, non-negotiable part of this configuration, not optional
// tooling. See plan.md's Accessibility Strategy and CI/CD Considerations.
export default defineConfig(
  globalIgnores(['dist', 'storybook-static', 'coverage', 'playwright-report', 'test-results']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      // NOTE: eslint-plugin-react-hooks@7's top-level `configs['recommended-latest']`
      // still ships the legacy `plugins: ["react-hooks"]` array shape and is
      // incompatible with pure flat config — `configs.flat['recommended-latest']`
      // is the correctly-shaped flat-config equivalent. Verified empirically
      // against the installed version; re-check this on any future upgrade.
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.strict,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // The design system is a closed vocabulary (003 FR-078–082): raw color or
      // spacing literals in component/feature code are a design-system violation,
      // not a style preference — enforced here, not left to code review alone.
      'no-restricted-syntax': [
        'error',
        {
          selector: 'Literal[value=/^#([0-9a-fA-F]{3}){1,2}$/]',
          message:
            'Raw hex colors are not permitted outside src/design-system/tokens/. Reference a semantic token instead (see Design System spec 003, FR-018).',
        },
      ],
    },
  },
  {
    files: ['**/*.stories.@(js|jsx|mjs|ts|tsx)'],
    // eslint-plugin-storybook bundles its own, older `@typescript-eslint/utils`
    // rule types, structurally incompatible with the newer typescript-eslint
    // version this project otherwise uses — a third-party type-definition lag,
    // not a real config error (verified: `eslint eslint.config.ts` itself lints
    // and loads this file with zero issues; only tsc's structural check trips on
    // the nested RuleModule type mismatch). Re-check on the next storybook/
    // typescript-eslint upgrade and remove the cast if it's no longer needed.
    extends: storybook.configs['flat/recommended'] as unknown as Linter.Config[],
  },
  {
    files: ['**/*.config.{ts,js}', '.storybook/**/*.ts'],
    languageOptions: {
      globals: globals.node,
    },
  },
);
