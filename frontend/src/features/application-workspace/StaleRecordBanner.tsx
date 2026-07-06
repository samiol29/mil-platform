/**
 * StaleRecordBanner (spec 002 tasks.md T068, FR-036).
 *
 * Surfaces when the currently-displayed record was fetched more than a
 * threshold ago, with a single one-action refresh — 002 FR-036 requires an
 * audit-critical record's staleness be checked explicitly before a
 * verification/override write is submitted, never silently assumed fresh.
 * This banner is that explicit check made visible, not merely an internal
 * `staleTime` policy the user can't see or act on.
 */

import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

const STALE_AFTER_MS = 2 * 60 * 1000;
const RECHECK_INTERVAL_MS = 15_000;

export interface StaleRecordBannerProps {
  readonly queryKey: readonly unknown[];
  readonly dataUpdatedAt: number;
}

export function StaleRecordBanner({ queryKey, dataUpdatedAt }: StaleRecordBannerProps) {
  const queryClient = useQueryClient();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => {
      setNow(Date.now());
    }, RECHECK_INTERVAL_MS);
    return () => {
      clearInterval(interval);
    };
  }, []);

  const isStale = now - dataUpdatedAt > STALE_AFTER_MS;
  if (!isStale) return null;

  return (
    <div
      role="status"
      className="bg-feedback-warning-bg text-feedback-warning-fg rounded-container flex items-center justify-between gap-3 px-4 py-2"
    >
      <span className="text-body">
        This record may be out of date. Refresh before verifying or overriding a finding.
      </span>
      <button
        type="button"
        className="text-label font-medium underline"
        onClick={() => {
          void queryClient.invalidateQueries({ queryKey });
        }}
      >
        Refresh
      </button>
    </div>
  );
}
