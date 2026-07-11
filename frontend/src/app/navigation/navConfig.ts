/**
 * Navigation config (Product Experience phase, Phase 0; Administration
 * entry added in spec 005-enterprise-platform Wave 1, §15).
 *
 * The persistent shell (`routes/__root.tsx`) renders its primary nav from
 * this ordered list rather than hardcoded JSX links — this is what let the
 * Administration section (Users/Roles today; Policy Packs, LOS
 * Integrations, Worker Monitoring, System Health, API Keys, Developer
 * Tools as later roadmap items) get added as a new entry here instead of a
 * shell/layout rewrite, exactly as this module's docstring anticipated.
 *
 * `roles` is enforced by `__root.tsx`'s `PrimaryNav` (filters
 * `NAV_SECTIONS` against the authenticated user's roles) — declaring it
 * here without that enforcement would be a silent no-op, so this entry and
 * that filter shipped together, not sequentially.
 */

import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  BarChart3,
  Briefcase,
  FolderKanban,
  Gavel,
  LayoutDashboard,
  ShieldCheck,
} from 'lucide-react';

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
  {
    id: 'banker-workspace',
    label: 'My Portfolio',
    icon: Briefcase,
    path: '/banker-workspace',
    roles: ['RELATIONSHIP_MANAGER', 'ADMIN'],
  },
  {
    id: 'administration',
    label: 'Administration',
    icon: ShieldCheck,
    path: '/administration',
    roles: ['ADMIN', 'COMPLIANCE_OFFICER', 'AUDIT_TEAM'],
  },
  {
    id: 'policy-administration',
    label: 'Policy',
    icon: Gavel,
    path: '/policy-administration',
    roles: ['POLICY_ADMINISTRATOR', 'COMPLIANCE_OFFICER', 'ADMIN'],
  },
  {
    id: 'operational-dashboard',
    label: 'Operations',
    icon: Activity,
    path: '/operational-dashboard',
    roles: ['OPERATIONS_MANAGER', 'ADMIN'],
  },
  {
    id: 'business-analytics',
    label: 'Analytics',
    icon: BarChart3,
    path: '/business-analytics',
    roles: ['OPERATIONS_MANAGER', 'COMPLIANCE_OFFICER', 'ADMIN'],
  },
];
