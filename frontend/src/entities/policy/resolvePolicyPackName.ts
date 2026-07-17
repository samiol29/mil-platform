/**
 * Resolves an `Application.activePolicyPackId` to its real pack name (final
 * design sprint — consistency pass). `GET /v1/policy-packs` is reachable by
 * every role that can view an Application Workspace at all (gated on
 * `READ_POLICY_RESULTS`, held by every such role) — this was previously
 * shown as a raw, unresolvable UUID in the Policy region specifically
 * (`ApplicationWorkspace.tsx`'s own docstring claimed "no policy-pack HTTP
 * route exists anywhere," true when written, false since that endpoint
 * shipped) while the Overview region's executive header already resolved
 * it correctly — the same real field showing two different things on two
 * tabs of the same page. One resolver, used by both.
 */

import type { PolicyPack } from './types';

export function resolvePolicyPackName(
  activePolicyPackId: string | null,
  packs: readonly PolicyPack[] | undefined,
): string {
  if (activePolicyPackId === null) return 'Not yet assigned';
  return packs?.find((pack) => pack.id === activePolicyPackId)?.name ?? activePolicyPackId.slice(0, 8);
}
