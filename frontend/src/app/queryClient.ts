/**
 * TanStack Query client (spec 002 tasks.md T036; plan.md Server State & API
 * Integration Strategy).
 *
 * `STALE_TIME` names the four caching tiers `data-model.md` defines per
 * entity — every entity query hook (`entities/*\/queries.ts`) picks one of
 * these explicitly rather than inventing its own number, so a reviewer can
 * answer "how fresh must this be?" by reading which constant a hook uses,
 * not by re-deriving a magic number:
 *
 * - `auditCritical` (0) — never trusted as fresh without an explicit check;
 *   used for Application/EvidenceItem/Finding once a review action is in
 *   flight against them (FR-036).
 * - `informational` (30s) — tolerant of brief staleness, background-refetch
 *   permitted (queue rows, in-progress document ingestion status).
 * - `longLived` (`Infinity`) — reference/rarely-changing data (a completed
 *   Document, an immutable Audit Trail Entry) cached aggressively.
 * - `preference` (`Infinity`, paired with optimistic mutations) — Saved
 *   Views, notification `readAt` — low-risk, trivially reversible.
 *
 * Mutations default to no automatic retry: a confirmed, attributed write
 * (a verification, an override) must never be silently retried by the
 * client without the caller's knowledge (Constitution Principle VIII).
 */

import { QueryClient } from '@tanstack/react-query';

export const STALE_TIME = {
  auditCritical: 0,
  informational: 30_000,
  longLived: Number.POSITIVE_INFINITY,
  preference: Number.POSITIVE_INFINITY,
} as const;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE_TIME.informational,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});
