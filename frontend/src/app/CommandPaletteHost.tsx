/**
 * CommandPaletteHost (UX audit §5 — "wire a minimal real command set,
 * nothing invented") — mounts the previously-unwired `CommandPalette` shell
 * (spec 003 T032) globally and registers only commands backed by
 * functionality that already exists elsewhere in the app:
 *
 * 1. Jump to a Workspace region — reuses the same `navigate` call
 *    `routes/applications.$applicationId.tsx`'s tab clicks already make.
 * 2. Verify/Override/Escalate a finding — only listed for findings not
 *    already decided, only when the current user is not read-only (mirrors
 *    `FindingActions`' own `alreadyDecided` guard and the route's
 *    `isReadOnlyUser` check exactly). Choosing one does not call a mutation
 *    directly: it sets `requestedFindingAction` in `useUiStore`, which the
 *    matching `FindingActions` instance consumes to open the exact same
 *    confirm-dialog its own button opens (FR-078's mandatory second
 *    confirmation step applies identically either way).
 * 3. Toggle light/dark theme — reuses `useTheme().toggleTheme`.
 * 4. Global Search (Product Experience phase, Phase 1) — typing 2+
 *    characters queries the same `search`-enabled `GET /v1/applications`
 *    the Application Queue uses (`useApplicationSearch`), listing matching
 *    applications by loan number/LOS reference/ID; selecting one navigates
 *    straight into its Workspace. One query, two entry points (palette and
 *    Queue), no separate search infrastructure.
 * 5. Create application (Product Experience phase, Phase 2) — now a
 *    legitimate command since the feature it opens (`IntakeWizard`) exists;
 *    just calls `openIntakeWizard()`, the same trigger the Dashboard and
 *    Queue header use.
 */

import { useNavigate, useParams, useSearch } from '@tanstack/react-router';
import { useEffect } from 'react';

import { isReadOnlyUser, useAuthUser } from '@app/auth/authProvider';
import { useUiStore } from '@app/uiStore';
import {
  CommandGroup,
  CommandItem,
  CommandPalette,
} from '@design-system/components/CommandPalette';
import { useTheme } from '@design-system/theme/useTheme';
import { useApplicationSearch } from '@entities/application/queries';
import { useFindingsForApplication } from '@entities/finding/queries';
import {
  REGION_LABEL,
  WORKSPACE_REGIONS,
  type WorkspaceRegion,
} from '@features/application-workspace/regions';

const MIN_SEARCH_LENGTH = 2;

export function CommandPaletteHost() {
  const open = useUiStore((state) => state.commandPaletteOpen);
  const openPalette = useUiStore((state) => state.openCommandPalette);
  const closePalette = useUiStore((state) => state.closeCommandPalette);
  const requestFindingAction = useUiStore((state) => state.requestFindingAction);
  const query = useUiStore((state) => state.commandPaletteQuery);
  const setQuery = useUiStore((state) => state.setCommandPaletteQuery);
  const openIntakeWizard = useUiStore((state) => state.openIntakeWizard);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        openPalette();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [openPalette]);

  const { applicationId } = useParams({ strict: false });
  const { region } = useSearch({ strict: false });
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const user = useAuthUser();
  const readOnly = user !== null && isReadOnlyUser(user.roles);

  const findingsQuery = useFindingsForApplication(applicationId ?? '', applicationId !== undefined);
  const findings = applicationId !== undefined ? (findingsQuery.data ?? []) : [];

  const searchEnabled = query.trim().length >= MIN_SEARCH_LENGTH;
  const searchQuery = useApplicationSearch({ search: query.trim(), enabled: searchEnabled });
  const searchResults = searchEnabled ? (searchQuery.data?.items ?? []) : [];

  function goToApplication(id: string) {
    void navigate({
      to: '/applications/$applicationId',
      params: { applicationId: id },
      search: { region: 'overview' },
    });
    closePalette();
  }

  function goToRegion(nextRegion: WorkspaceRegion) {
    if (applicationId === undefined) return;
    void navigate({
      to: '/applications/$applicationId',
      params: { applicationId },
      search: { region: nextRegion },
    });
    closePalette();
  }

  return (
    <CommandPalette
      open={open}
      onOpenChange={closePalette}
      value={query}
      onValueChange={setQuery}
      placeholder="Search by loan #, LOS reference, or application ID…"
    >
      {searchEnabled && searchResults.length > 0 && (
        <CommandGroup heading="Applications">
          {searchResults.map((app) => (
            <CommandItem
              key={app.id}
              onSelect={() => {
                goToApplication(app.id);
              }}
            >
              {app.loanNumber ?? app.losReference ?? app.id}
            </CommandItem>
          ))}
        </CommandGroup>
      )}

      {applicationId !== undefined && (
        <CommandGroup heading="Go to">
          {WORKSPACE_REGIONS.filter((candidate) => candidate !== region).map((candidate) => (
            <CommandItem
              key={candidate}
              onSelect={() => {
                goToRegion(candidate);
              }}
            >
              {REGION_LABEL[candidate]}
            </CommandItem>
          ))}
        </CommandGroup>
      )}

      {applicationId !== undefined && !readOnly && findings.length > 0 && (
        <CommandGroup heading="Findings">
          {findings
            .filter((finding) => finding.state === 'unreviewed' || finding.state === 'escalated')
            .flatMap((finding) => [
              <CommandItem
                key={`${finding.id}-verify`}
                onSelect={() => {
                  requestFindingAction({ findingId: finding.id, action: 'verify' });
                  goToRegion('findings');
                }}
              >
                Verify: {finding.what}
              </CommandItem>,
              <CommandItem
                key={`${finding.id}-override`}
                onSelect={() => {
                  requestFindingAction({ findingId: finding.id, action: 'override' });
                  goToRegion('findings');
                }}
              >
                Override: {finding.what}
              </CommandItem>,
              <CommandItem
                key={`${finding.id}-escalate`}
                onSelect={() => {
                  requestFindingAction({ findingId: finding.id, action: 'escalate' });
                  goToRegion('findings');
                }}
              >
                Escalate: {finding.what}
              </CommandItem>,
            ])}
        </CommandGroup>
      )}

      <CommandGroup heading="Actions">
        <CommandItem
          onSelect={() => {
            openIntakeWizard();
            closePalette();
          }}
        >
          Create application
        </CommandItem>
      </CommandGroup>

      <CommandGroup heading="Preferences">
        <CommandItem
          onSelect={() => {
            toggleTheme();
            closePalette();
          }}
        >
          Switch to {theme === 'light' ? 'dark' : 'light'} theme
        </CommandItem>
      </CommandGroup>
    </CommandPalette>
  );
}
