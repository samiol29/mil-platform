/**
 * `/` entry point (Product Experience phase, Phase 1) — the Home Dashboard.
 *
 * This replaces the previous bootstrap redirect (a stopgap that jumped
 * straight to whichever application the API happened to return first,
 * because no queue or dashboard existed yet). The Dashboard now answers
 * "what needs my attention today"; the Application Queue (`/applications`)
 * is the detailed operational view for browsing/searching everything.
 */
import { HomeDashboard } from '@features/home-dashboard/HomeDashboard';

export function Root() {
  return <HomeDashboard />;
}
