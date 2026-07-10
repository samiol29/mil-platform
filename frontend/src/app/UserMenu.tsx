/**
 * UserMenu (spec 002 tasks.md T127, FR-007) — persistently indicates the
 * identity and role of the authenticated user, and makes signing out a
 * single, always-reachable action, mounted in the persistent chrome
 * (`routes/__root.tsx`) so it is visible from every screen.
 *
 * Deliberately composed only from the closed component set (`Button`) —
 * FR-007 requires a single-action sign-out, not a menu of options, so no
 * new dropdown/menu primitive is needed or introduced (plan.md Component
 * Architecture: feature code may compose design-system components, never
 * invent a new visual primitive).
 */

import { authProvider, useAuthUser } from '@app/auth/authProvider';
import { Button } from '@design-system/components/Button';

export function UserMenu() {
  const user = useAuthUser();

  if (user === null) {
    return <span className="text-caption text-text-tertiary">Signed out</span>;
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-label text-text-primary">
        {user.displayName}
        <span className="text-text-tertiary"> · {user.roles.join(', ')}</span>
      </span>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => {
          authProvider.signOut();
        }}
      >
        Sign out
      </Button>
    </div>
  );
}
