/**
 * Breadcrumb (Product Experience phase, Phase 0) — orientation and a
 * one-click path back up the hierarchy (Dashboard → Queue → Application →
 * region), which is what makes "return to queue" a real affordance instead
 * of only browser-back.
 *
 * Props-driven, like `CommandPalette`/`Toast` — this component doesn't know
 * about the route tree. Each non-last item supplies `onClick`, which the
 * caller wires to its own `useNavigate()` (typed correctly at the call
 * site, where the concrete route is known — TanStack Router's `Link`
 * generic typing doesn't extend cleanly to a shared, route-agnostic
 * component). The last item is always the current page: rendered as plain
 * text with `aria-current="page"`, never a link.
 */

import { ChevronRight } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@design-system/lib/cn';

export interface BreadcrumbItem {
  readonly label: ReactNode;
  /** Omit for the current (last) item. */
  readonly onClick?: () => void;
}

export interface BreadcrumbProps {
  readonly items: readonly BreadcrumbItem[];
  readonly className?: string;
}

export function Breadcrumb({ items, className }: BreadcrumbProps) {
  if (items.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-1.5', className)}>
      <ol className="flex items-center gap-1.5">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={index} className="flex items-center gap-1.5">
              {index > 0 && (
                <ChevronRight className="text-text-tertiary size-3.5" aria-hidden="true" />
              )}
              {isLast ? (
                <span aria-current="page" className="text-label text-text-primary font-medium">
                  {item.label}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={item.onClick}
                  className={cn(
                    'text-label text-text-secondary hover:text-text-primary font-medium',
                    'outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2',
                    'rounded-interactive',
                  )}
                >
                  {item.label}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
