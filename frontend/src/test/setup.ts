import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';

import { server } from './msw/server';

/**
 * jsdom (this project's unit-test environment) does not implement
 * `DOMMatrix`, which `pdfjs-dist`'s bundle references at module-load time
 * (`src/display/canvas.js`) — importing `PdfRenderer.tsx` anywhere in a
 * unit test throws `ReferenceError: DOMMatrix is not defined` without
 * this. Component tests never invoke real canvas rendering (PDF.js
 * rendering itself is exercised in Storybook/Playwright's real-browser
 * environment, not here); this identity-only stand-in only needs to
 * satisfy module evaluation, not perform real 2D transforms.
 */
if (typeof globalThis.DOMMatrix === 'undefined') {
  class DOMMatrixPolyfill {
    a = 1;
    b = 0;
    c = 0;
    d = 1;
    e = 0;
    f = 0;
    multiply(): this {
      return this;
    }
    translate(): this {
      return this;
    }
    scale(): this {
      return this;
    }
  }
  // @ts-expect-error -- test-environment stand-in, not a spec-complete DOMMatrix.
  globalThis.DOMMatrix = DOMMatrixPolyfill;
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
