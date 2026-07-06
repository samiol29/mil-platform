/**
 * Shared entity-layer query convention (spec 002 tasks.md T043; plan.md
 * Server State & API Integration Strategy).
 *
 * Every `entities/<name>/queries.ts` module builds its query hooks from
 * `fetchEntity`/`useEntityQuery` rather than calling `httpClient` or
 * `useQuery` directly — this is what makes "a backend contract change
 * fails loudly, at the API boundary" (plan.md) true in practice: the Zod
 * `schema.parse()` call is not optional or bolted on per-hook, it is the
 * only way this helper returns data at all.
 */

import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import type { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';

/** Builds a `queryFn` that fetches `url` and parses the response through `schema`. */
export function fetchEntity<TSchema extends z.ZodType>(
  schema: TSchema,
  url: string,
): () => Promise<z.infer<TSchema>> {
  return async () => {
    const response = await httpClient.get<unknown>(url);
    return schema.parse(response.data);
  };
}

export interface EntityQueryOptions<TSchema extends z.ZodType> {
  readonly queryKey: readonly unknown[];
  readonly url: string;
  readonly schema: TSchema;
  readonly staleTime: number;
  readonly enabled?: boolean;
}

/** The standard entity-layer read hook: fetch `url`, parse through `schema`, cache under `queryKey`. */
export function useEntityQuery<TSchema extends z.ZodType>({
  queryKey,
  url,
  schema,
  staleTime,
  enabled,
}: EntityQueryOptions<TSchema>): UseQueryResult<z.infer<TSchema>> {
  return useQuery({
    queryKey,
    queryFn: fetchEntity(schema, url),
    staleTime,
    ...(enabled !== undefined ? { enabled } : {}),
  });
}
