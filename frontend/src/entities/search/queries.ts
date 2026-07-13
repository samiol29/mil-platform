/**
 * Universal Search query hook (spec 005-enterprise-platform §7, Wave 2).
 */

import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { searchResponseSchema } from './types';

export interface UseUniversalSearchOptions {
  readonly query: string;
  readonly kinds?: readonly ('application' | 'document')[];
  readonly enabled?: boolean;
}

export function useUniversalSearch({ query, kinds, enabled = true }: UseUniversalSearchOptions) {
  const params = new URLSearchParams({ q: query });
  if (kinds !== undefined) {
    params.set('kinds', kinds.join(','));
  }
  return useEntityQuery({
    queryKey: ['search', query, kinds?.join(',') ?? null],
    url: `/search?${params.toString()}`,
    schema: searchResponseSchema,
    staleTime: STALE_TIME.informational,
    enabled,
  });
}
