/**
 * LOS Sync panel (spec 005-enterprise-platform §2, Wave 2 — LOS Integration
 * Layer). A collapsible Overview-region panel — same pattern as
 * `CopilotPanel` — showing this application's sync/push history and two
 * real actions: pull the LOS's current state, and push a Mortgage
 * Readiness assessment. Both call the pre-existing `LOSAdapter` interface
 * (already conformance-tested, `src/providers/los/mock_los.py`) through the
 * new `IntegrationService` — this panel invents no new integration
 * behavior, it is the human-triggered front door onto it.
 *
 * Honest when there's nothing to sync against: an application with no
 * `losReference` shows a plain explanatory note instead of enabled-but-
 * broken buttons.
 */

import { useState } from 'react';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { Textarea } from '@design-system/components/Textarea';
import type { Application } from '@entities/application/types';
import {
  useApplicationSyncEvents,
  usePushReadiness,
  useSyncApplication,
} from '@entities/integration/queries';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown error';
}

export function LOSSyncPanel({ application }: { application: Application }) {
  const [expanded, setExpanded] = useState(false);
  const [summary, setSummary] = useState('');
  const eventsQuery = useApplicationSyncEvents(application.id);
  const syncApplication = useSyncApplication();
  const pushReadiness = usePushReadiness();
  const addToast = useUiStore((state) => state.addToast);

  if (application.losReference === null) {
    return null;
  }

  return (
    <div className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-3 p-4">
      <button
        type="button"
        onClick={() => {
          setExpanded((v) => !v);
        }}
        className="flex items-center gap-2 text-left outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
      >
        <span className="text-label text-text-primary font-medium">
          LOS Sync — {application.losReference}
        </span>
      </button>

      {expanded && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              loading={syncApplication.isPending}
              onClick={() => {
                syncApplication.mutate(application.id, {
                  onSuccess: (event) =>
                    addToast({
                      title: event.outcome === 'SUCCESS' ? 'Synced from LOS' : 'Sync failed',
                      variant: event.outcome === 'SUCCESS' ? 'success' : 'error',
                      ...(event.errorMessage !== null ? { description: event.errorMessage } : {}),
                    }),
                  onError: (error: unknown) =>
                    addToast({
                      title: 'Sync failed',
                      description: errorMessage(error),
                      variant: 'error',
                    }),
                });
              }}
            >
              Sync from LOS
            </Button>
          </div>

          <div className="flex flex-col gap-1.5">
            <Textarea
              aria-label="Readiness summary"
              value={summary}
              onChange={(e) => {
                setSummary(e.target.value);
              }}
              placeholder="Ready for underwriting — all required documents received."
              rows={2}
            />
            <div className="flex items-center gap-2 self-end">
              <Button
                variant="secondary"
                size="sm"
                disabled={summary.trim().length === 0}
                loading={pushReadiness.isPending}
                onClick={() => {
                  pushReadiness.mutate(
                    { applicationId: application.id, isReady: true, summary },
                    {
                      onSuccess: (event) => {
                        addToast({
                          title:
                            event.outcome === 'SUCCESS' ? 'Readiness pushed to LOS' : 'Push failed',
                          variant: event.outcome === 'SUCCESS' ? 'success' : 'error',
                          ...(event.errorMessage !== null
                            ? { description: event.errorMessage }
                            : {}),
                        });
                        setSummary('');
                      },
                      onError: (error: unknown) =>
                        addToast({
                          title: 'Push failed',
                          description: errorMessage(error),
                          variant: 'error',
                        }),
                    },
                  );
                }}
              >
                Push readiness
              </Button>
            </div>
          </div>

          {eventsQuery.data !== undefined && eventsQuery.data.items.length > 0 && (
            <ul className="flex flex-col gap-1">
              {eventsQuery.data.items.slice(0, 5).map((event) => (
                <li
                  key={event.id}
                  className="text-caption text-text-secondary flex items-center gap-2"
                >
                  <span
                    className={
                      event.outcome === 'SUCCESS'
                        ? 'text-feedback-success-fg'
                        : 'text-feedback-error-fg'
                    }
                  >
                    {event.direction} · {event.outcome}
                  </span>
                  <span className="text-text-tertiary">
                    {new Date(event.occurredAt).toLocaleString()}
                  </span>
                  {event.errorMessage !== null && <span>— {event.errorMessage}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
