/**
 * Auth abstraction (spec 002 tasks.md T035; plan.md Authentication Flow).
 *
 * Token acquisition and the current user's identity live behind this single
 * module — no feature code reads a token or decodes identity claims itself.
 * Today's implementation is the dev-bearer flow (the literal token `"dev"`,
 * matching `mil.identity.provider.DevBearerIdentityProvider` and the
 * built-in `DEV_USER_ID`/`DEV_TENANT_ID` principal every seeded row in this
 * codebase is attributed to). When the backend ships a production
 * (OIDC/JWKS) `IdentityProvider` plus the refresh-cookie/CSRF endpoints
 * (`contracts/api-gaps.md`'s Authentication Endpoints, tasks.md T130–T131),
 * only this module's internals change — every consumer of `authProvider`/
 * `useAuthUser` is unaffected.
 *
 * `signOut()` is a real, correct implementation of what "signing out" means
 * for *this* auth flow today: it clears the in-memory token and current
 * user, so every subsequent request is unauthenticated and the API
 * legitimately returns 401 — surfaced through the existing route/panel
 * error boundaries, not a fabricated "signed out" screen. A dedicated
 * signed-out/login landing experience is out of this task's scope (it is
 * gated on the production `IdentityProvider` this module already isolates
 * the eventual swap to).
 */

import { useSyncExternalStore } from 'react';

const DEV_BEARER_TOKEN = 'dev';

export interface AuthenticatedUser {
  readonly userId: string;
  readonly tenantId: string;
  readonly displayName: string;
  readonly roles: readonly string[];
}

const DEV_USER: AuthenticatedUser = {
  userId: '00000000-0000-0000-0000-000000000001',
  tenantId: '00000000-0000-0000-0000-000000000002',
  displayName: 'Dev Admin',
  roles: ['ADMIN'],
};

type Listener = () => void;

let currentToken: string | null = DEV_BEARER_TOKEN;
let currentUser: AuthenticatedUser | null = DEV_USER;
const listeners = new Set<Listener>();

function notify(): void {
  for (const listener of listeners) listener();
}

export interface AuthProvider {
  /** The current bearer token, or `null` if signed out. Read synchronously by `httpClient`. */
  getAccessToken: () => string | null;
  getCurrentUser: () => AuthenticatedUser | null;
  signOut: () => void;
  /** Registers a listener notified whenever the token/user changes; returns an unsubscribe function. */
  subscribe: (listener: Listener) => () => void;
}

export const authProvider: AuthProvider = {
  getAccessToken: () => currentToken,
  getCurrentUser: () => currentUser,
  signOut: () => {
    currentToken = null;
    currentUser = null;
    notify();
  },
  subscribe: (listener) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

/** Reactive access to the current user — re-renders on `signOut()`. */
export function useAuthUser(): AuthenticatedUser | null {
  return useSyncExternalStore(authProvider.subscribe, authProvider.getCurrentUser);
}
