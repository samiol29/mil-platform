/**
 * Tabs (Product Experience phase, Phase 0) — a generic, controlled tab-nav
 * primitive replacing the hand-rolled `role="tab"` button row previously
 * duplicated in `ApplicationWorkspace.tsx`'s region nav. Reused by every
 * later region-switching surface in this phase (Policy Checks, Timeline
 * vs. Audit) so the keyboard model and styling are defined exactly once.
 *
 * Implements the WAI-ARIA "Tabs (Automatic Activation)" pattern with a
 * roving `tabIndex` — `ArrowLeft`/`ArrowRight`/`Home`/`End` move focus and
 * activate the tab in one step, matching the keyboard-first benchmark goal
 * (the previous hand-rolled version only supported click). No new
 * dependency: no Radix Tabs primitive is installed, and this surface is
 * simple enough not to need one.
 *
 * Selection is fully controlled by the caller (`value`/`onValueChange`) —
 * region state continues to be owned by the route (spec 002 tasks.md T069),
 * this component never holds its own selection state.
 */

import { createContext, useContext, useRef } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';

interface TabsContextValue {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(): TabsContextValue {
  const context = useContext(TabsContext);
  if (context === null) {
    throw new Error('Tabs.List/Tabs.Trigger must be rendered within <Tabs>.');
  }
  return context;
}

export interface TabsProps {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly children: ReactNode;
  readonly className?: string;
}

export function Tabs({ value, onValueChange, children, className }: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export interface TabsListProps {
  readonly children: ReactNode;
  readonly 'aria-label': string;
  readonly className?: string;
}

export function TabsList({ children, className, ...rest }: TabsListProps) {
  const listRef = useRef<HTMLDivElement>(null);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const list = listRef.current;
    if (list === null) return;
    const triggers = Array.from(list.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    const currentIndex = triggers.findIndex((el) => el === document.activeElement);
    if (currentIndex === -1) return;

    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % triggers.length;
    else if (event.key === 'ArrowLeft')
      nextIndex = (currentIndex - 1 + triggers.length) % triggers.length;
    else if (event.key === 'Home') nextIndex = 0;
    else if (event.key === 'End') nextIndex = triggers.length - 1;

    if (nextIndex !== null) {
      event.preventDefault();
      triggers[nextIndex]?.focus();
      triggers[nextIndex]?.click();
    }
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
      className={cn('border-border-subtle flex gap-1 border-b', className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface TabsTriggerProps {
  readonly value: string;
  readonly children: ReactNode;
  readonly className?: string;
}

export function TabsTrigger({ value, children, className }: TabsTriggerProps) {
  const { value: activeValue, onValueChange } = useTabsContext();
  const isActive = value === activeValue;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      tabIndex={isActive ? 0 : -1}
      onClick={() => {
        onValueChange(value);
      }}
      className={cn(
        'text-label -mb-px border-b-2 px-3 py-2 font-medium transition-colors duration-micro ease-standard',
        'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
        isActive
          ? 'border-interactive-primary-default text-text-primary'
          : 'text-text-secondary hover:text-text-primary border-transparent',
        className,
      )}
    >
      {children}
    </button>
  );
}

export interface TabsPanelProps {
  readonly value: string;
  readonly children: ReactNode;
  readonly className?: string;
}

/** Optional — only needed when Tabs itself owns the panel content (unlike the Workspace, which renders regions separately). */
export function TabsPanel({ value, children, className }: TabsPanelProps) {
  const { value: activeValue } = useTabsContext();
  if (value !== activeValue) return null;

  return (
    <div role="tabpanel" className={className}>
      {children}
    </div>
  );
}
