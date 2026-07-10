/**
 * CommandPalette (spec 003 T032) — the keyboard-first, fuzzy-search command
 * shell referenced by plan.md's Component Architecture and wired to actual
 * commands in a later phase (tasks.md T080: global-search and
 * jump-to-application commands). This task defines only the shell:
 * fuzzy-matching input, result list, and empty state — deliberately empty of
 * registered commands for now.
 *
 * Built on `cmdk` (the standard companion library shadcn/ui's own Command
 * component uses) composed with `@radix-ui/react-dialog` via `CommandDialog`
 * — focus trap, keyboard dismiss, and return-focus-on-close are inherited
 * from the same Radix Dialog primitive `Dialog`/`Drawer` use (FR-053).
 * Fuzzy matching, arrow-key navigation, and `Enter`-to-activate are cmdk's
 * built-in keyboard model (FR-069's composite-component keyboard
 * requirement), not reimplemented here.
 *
 * `CommandResults` renders registered `children` (`<CommandGroup>`/
 * `<CommandItem>`) unconditionally rather than gating them on cmdk's
 * `filtered.count` — an earlier version of this component gated
 * rendering on that count, which is a chicken-and-egg bug: cmdk items only
 * register themselves (and thus update `filtered.count`) via a mount
 * effect, so if they are never placed in the tree because the count
 * starts at 0, they can never mount to update it, and the palette is
 * permanently stuck showing "No results found." even with real commands
 * registered (caught when this shell was first given real commands to
 * host, UX audit §5 — production never actually populated `children`
 * before that, so the bug had no way to surface until then).
 *
 * When `children` is provided, cmdk's own `<CommandEmpty>` (which
 * self-toggles on `filtered.count === 0` without gating anything else's
 * mount) renders the "no results" text for an unmatched search, sitting
 * alongside the always-rendered items. When `children` is undefined (the
 * literal no-commands-registered-anywhere shell, still the production
 * default in some future context), a static, non-interactive `role="option"`
 * placeholder is used instead — `<CommandList>` (always `role="listbox"`)
 * would otherwise contain only `<CommandEmpty>` (`role="presentation"`),
 * violating the WCAG `aria-required-children` rule (a `listbox` must
 * contain `option`/`group` descendants) — caught for real by this
 * component's own Storybook `a11y` gate.
 */

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from 'cmdk';
import { Search } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';

export interface CommandPaletteProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly placeholder?: string;
  /** Registered `<CommandGroup>`/`<CommandItem>` children — none by default. */
  readonly children?: ReactNode;
  /**
   * Controlled input text (Product Experience phase, Phase 1's Global
   * Search) — lets the host react to what's typed (e.g. to run a live
   * application search) instead of cmdk's default uncontrolled input.
   * Omit both to keep the input uncontrolled, as it was before Phase 1.
   */
  readonly value?: string;
  readonly onValueChange?: (value: string) => void;
}

function CommandResults({ children }: { children?: ReactNode }) {
  return (
    <CommandList className="max-h-80 overflow-y-auto p-2">
      {children === undefined ? (
        <div
          role="option"
          aria-disabled="true"
          aria-selected="false"
          className="text-body px-3 py-6 text-center text-text-tertiary"
        >
          No results found.
        </div>
      ) : (
        <>
          <CommandEmpty className="text-body px-3 py-6 text-center text-text-tertiary">
            No results found.
          </CommandEmpty>
          {children}
        </>
      )}
    </CommandList>
  );
}

export function CommandPalette({
  open,
  onOpenChange,
  placeholder = 'Type a command or search…',
  children,
  value,
  onValueChange,
}: CommandPaletteProps) {
  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command palette"
      className={cn(
        'bg-surface-overlay border-border-default fixed top-[20%] left-1/2 z-50 w-full max-w-lg',
        '-translate-x-1/2 rounded-container border shadow-overlay',
      )}
    >
      <div className="border-border-subtle flex items-center gap-2 border-b px-4">
        <Search className="size-4 text-text-tertiary" aria-hidden="true" />
        <CommandInput
          placeholder={placeholder}
          {...(value !== undefined ? { value } : {})}
          {...(onValueChange !== undefined ? { onValueChange } : {})}
          className={cn(
            'text-body h-12 flex-1 bg-transparent text-text-primary outline-none',
            'placeholder:text-text-tertiary',
          )}
        />
      </div>
      <CommandResults>{children}</CommandResults>
    </CommandDialog>
  );
}

export { CommandGroup, CommandItem };
