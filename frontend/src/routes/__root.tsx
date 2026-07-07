/**
 * Root route (spec 002 tasks.md T037) — the persistent application chrome
 * every route renders inside of: the top bar carrying a product identity
 * mark, data-driven primary nav (`navConfig.ts`, Product Experience phase
 * Phase 0), the currently-open application's lifecycle status (when a
 * `/applications/$applicationId` route is active — UX audit §5, Blend/
 * nCino/Vercel Dashboard benchmark), and the UserMenu (FR-007); plus the
 * route outlet, wrapped in the route-level error boundary (plan.md Error
 * Boundaries, tier 2) so a failure loading one route's content never takes
 * down this persistent chrome.
 *
 * The status read here shares the same TanStack Query cache entry
 * `ApplicationWorkspace` populates via `useApplication` — this is a cache
 * read, not a second network request, and resolves to `undefined` (nothing
 * rendered) until that data has loaded or when no application route is
 * active.
 *
 * Also mounts `CommandPaletteHost` (UX audit §5), `ToastHost` (Phase 0), and
 * `IntakeWizard` (Phase 2) — the single global places the previously-unwired
 * Command Palette/Toast shells and the application-intake Drawer are given
 * real state, reachable identically from the Dashboard, the Queue, or the
 * Command Palette.
 *
 * Session-expiry (Phase 0): when `useAuthUser()` is `null` (post
 * `authProvider.signOut()`), the outlet is replaced with an honest
 * "session ended" screen instead of letting every subsequent request
 * silently 401 through the panel error boundaries — see
 * `authProvider.ts`'s docstring for why a fuller login flow stays out of
 * scope until a production `IdentityProvider` exists.
 */

import type { QueryClient } from '@tanstack/react-query';
import {
  Outlet,
  createRootRouteWithContext,
  useLocation,
  useNavigate,
  useParams,
} from '@tanstack/react-router';
import { LogIn, Search } from 'lucide-react';

import { CommandPaletteHost } from '@app/CommandPaletteHost';
import { NAV_SECTIONS } from '@app/navigation/navConfig';
import { ToastHost } from '@app/ToastHost';
import { UserMenu } from '@app/UserMenu';
import { useAuthUser } from '@app/auth/authProvider';
import { useUiStore } from '@app/uiStore';
import { Breadcrumb } from '@design-system/components/Breadcrumb';
import { Button } from '@design-system/components/Button';
import { EmptyState } from '@design-system/components/EmptyState';
import { cn } from '@design-system/lib/cn';
import { useApplication } from '@entities/application/queries';
import {
  APPLICATION_STATUS_CLASS_NAME,
  APPLICATION_STATUS_LABEL,
} from '@entities/application/statusLabel';
import { IntakeWizard } from '@features/application-intake/IntakeWizard';
import { RouteErrorBoundary } from '@shared/errors/RouteErrorBoundary';

export interface RouterContext {
  readonly queryClient: QueryClient;
}

function RootLayout() {
  const openCommandPalette = useUiStore((state) => state.openCommandPalette);
  const user = useAuthUser();

  return (
    <div className="bg-surface-background min-h-screen">
      <header className="border-border-subtle bg-surface-raised flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-4">
          <span className="text-label text-text-primary font-medium">MIL</span>
          <PrimaryNav />
          <PrimaryBreadcrumb />
          <ActiveApplicationStatus />
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={openCommandPalette}
            aria-label="Open command palette and search"
          >
            <Search className="size-3.5" aria-hidden="true" />
            <span className="text-text-tertiary">⌘K</span>
          </Button>
          <UserMenu />
        </div>
      </header>
      <main>
        <RouteErrorBoundary>{user === null ? <SessionEndedScreen /> : <Outlet />}</RouteErrorBoundary>
      </main>
      <CommandPaletteHost />
      <ToastHost />
      <IntakeWizard />
    </div>
  );
}

function PrimaryNav() {
  const navigate = useNavigate();

  return (
    <nav aria-label="Primary" className="flex items-center gap-1">
      {NAV_SECTIONS.map((section) => {
        const Icon = section.icon;
        return (
          <button
            key={section.id}
            type="button"
            onClick={() => {
              // `section.path` is a plain string (config-driven, per navConfig.ts's
              // docstring) rather than one of the router's generated route-id
              // literals, so `to`'s strict union type doesn't apply here directly.
              void navigate({ to: section.path as unknown as '/' });
            }}
            className={cn(
              'text-label text-text-secondary hover:text-text-primary hover:bg-surface-disabled',
              'flex items-center gap-1.5 rounded-interactive px-2 py-1 font-medium',
              'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
            )}
          >
            <Icon className="size-3.5" aria-hidden="true" />
            {section.label}
          </button>
        );
      })}
    </nav>
  );
}

function SessionEndedScreen() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <EmptyState
        icon={LogIn}
        title="Session ended"
        description="You've been signed out. Sign back in to continue where you left off."
        action={
          <Button
            variant="primary"
            onClick={() => {
              window.location.reload();
            }}
          >
            Sign back in
          </Button>
        }
      />
    </div>
  );
}

/**
 * Route-aware breadcrumb (Phase 0/1): Dashboard → Queue → Application. Each
 * segment beyond the current page is a real, clickable step back up the
 * hierarchy — this is what makes "return to queue" one click instead of
 * relying on browser-back.
 */
function PrimaryBreadcrumb() {
  const pathname = useLocation({ select: (location) => location.pathname });
  const { applicationId } = useParams({ strict: false });
  const navigate = useNavigate();

  const items = [
    {
      label: 'Dashboard',
      onClick: () => {
        void navigate({ to: '/' });
      },
    },
  ];

  if (pathname === '/') {
    return <Breadcrumb items={[{ label: 'Dashboard' }]} className="hidden md:flex" />;
  }

  if (applicationId === undefined) {
    return (
      <Breadcrumb
        items={[...items, { label: 'Application Queue' }]}
        className="hidden md:flex"
      />
    );
  }

  return (
    <Breadcrumb
      items={[
        ...items,
        {
          label: 'Queue',
          onClick: () => {
            void navigate({ to: '/applications' });
          },
        },
        { label: <ActiveApplicationBreadcrumbLabel applicationId={applicationId} /> },
      ]}
      className="hidden md:flex"
    />
  );
}

function ActiveApplicationBreadcrumbLabel({ applicationId }: { readonly applicationId: string }) {
  const applicationQuery = useApplication(applicationId);
  const app = applicationQuery.data;
  if (app === undefined) return 'Application';
  return app.loanNumber ?? app.losReference ?? 'Application';
}

function ActiveApplicationStatus() {
  const { applicationId } = useParams({ strict: false });

  if (applicationId === undefined) {
    return null;
  }

  return <ActiveApplicationStatusLabel applicationId={applicationId} />;
}

function ActiveApplicationStatusLabel({ applicationId }: { applicationId: string }) {
  const applicationQuery = useApplication(applicationId);

  if (applicationQuery.data === undefined) {
    return null;
  }

  const status = applicationQuery.data.status;

  return (
    <span
      className={cn(
        'text-caption border-border-subtle rounded-chip border px-2 py-0.5 font-medium',
        APPLICATION_STATUS_CLASS_NAME[status],
      )}
    >
      {APPLICATION_STATUS_LABEL[status]}
    </span>
  );
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
});
