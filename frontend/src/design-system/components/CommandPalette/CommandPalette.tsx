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
 * `CommandResults` deliberately does NOT use cmdk's built-in `<CommandEmpty>`:
 * it renders `role="presentation"`, and when it is `<CommandList>`'s (always
 * `role="listbox"`) only child (the "no commands registered yet" state this
 * component ships in today), that combination violates the WCAG
 * `aria-required-children` rule (a `listbox` must contain `option`/`group`
 * descendants) — caught for real by this task's own Storybook `a11y` gate.
 * Instead, the empty message renders as a single, non-interactive
 * `role="option"` (`aria-disabled`) inside the always-mounted
 * `<CommandList>` — satisfying the required-children rule structurally,
 * while also keeping `<CommandList>`'s id stable so `CommandInput`'s
 * `aria-controls` reference never dangles (unmounting `<CommandList>`
 * entirely was the first fix attempted here and broke that reference —
 * left as a note for the next person tempted to try it again).
 */

import {
  CommandDialog,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  useCommandState,
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
}

function CommandResults({ children }: { children?: ReactNode }) {
  const resultCount = useCommandState((state) => state.filtered.count);

  return (
    <CommandList className="max-h-80 overflow-y-auto p-2">
      {resultCount === 0 ? (
        <div
          role="option"
          aria-disabled="true"
          aria-selected="false"
          className="text-body px-3 py-6 text-center text-text-tertiary"
        >
          No results found.
        </div>
      ) : (
        children
      )}
    </CommandList>
  );
}

export function CommandPalette({
  open,
  onOpenChange,
  placeholder = 'Type a command or search…',
  children,
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
