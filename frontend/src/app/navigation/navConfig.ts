/**
 * Navigation config (Product Experience phase, Phase 0).
 *
 * The persistent shell (`routes/__root.tsx`) renders its primary nav from
 * this ordered list rather than hardcoded JSX links — this is what lets a
 * future Administration section (Users, Roles, Policy Packs, LOS
 * Integrations, Worker Monitoring, System Health, API Keys, Developer
 * Tools — all explicit roadmap items, none implemented) be added later as
 * a new entry in this array instead of a shell/layout rewrite.
 *
 * `NAV_SECTIONS` intentionally lists only what exists today. Do not add an
 * "Administration" entry yet — the structure not precluding it is the
 * requirement, not a placeholder link that goes nowhere.
 */

import type { LucideIcon } from 'lucide-react';
import { FolderKanban, LayoutDashboard } from 'lucide-react';

export interface NavSection {
  readonly id: string;
  readonly label: string;
  readonly icon: LucideIcon;
  /** A registered route path, e.g. `/`. Resolved with `useNavigate()` at the call site, not `Link`, to keep this config decoupled from the generated route tree's strict typing. */
  readonly path: string;
  /** Roles permitted to see this entry. Omit to show to every authenticated user. */
  readonly roles?: readonly string[];
}

export const NAV_SECTIONS: readonly NavSection[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { id: 'queue', label: 'Queue', icon: FolderKanban, path: '/applications' },
];
