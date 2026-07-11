/**
 * Customer Portal session store (spec 005-enterprise-platform §12, Wave 4).
 *
 * Deliberately separate from `authProvider.ts` (internal staff auth) — a
 * genuinely distinct trust boundary, not a shared token store. The portal
 * session token is opaque to the frontend; it is issued by
 * `POST /v1/portal/auth/activate` and verified server-side against
 * `Settings.mil_portal_secret_key`, never the internal `IdentityProvider`.
 */

const STORAGE_KEY = 'mil_portal_session_token';

export const portalAuthStore = {
  getSessionToken(): string | null {
    return localStorage.getItem(STORAGE_KEY);
  },
  setSessionToken(token: string): void {
    localStorage.setItem(STORAGE_KEY, token);
  },
  clearSession(): void {
    localStorage.removeItem(STORAGE_KEY);
  },
  isAuthenticated(): boolean {
    return this.getSessionToken() !== null;
  },
};
