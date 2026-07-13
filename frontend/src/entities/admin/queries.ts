/**
 * Enterprise Administration query/mutation hooks (spec 005-enterprise-
 * platform §15). Follows the same `useEntityQuery`/`useMutation` +
 * `httpClient` + Zod-parse + `invalidateQueries` convention as every other
 * entity module (`entities/application/queries.ts` is the pattern).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { httpClient } from '@app/auth/httpClient';
import { STALE_TIME } from '@app/queryClient';
import { useEntityQuery } from '@shared/api/createEntityQuery';

import { adminUserSchema, apiKeyCreatedSchema, apiKeySchema, roleAssignmentSchema } from './types';
import type { AdminUser, ApiKey, ApiKeyCreated, RoleAssignment } from './types';

const userListResponseSchema = z.object({ items: z.array(adminUserSchema) });
const apiKeyListResponseSchema = z.object({ items: z.array(apiKeySchema) });

export function useAdminUsers() {
  return useEntityQuery({
    queryKey: ['admin', 'users'],
    url: '/admin/users',
    schema: userListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export interface CreateUserInput {
  readonly externalIdentityId: string;
  readonly email: string;
  readonly displayName: string;
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateUserInput): Promise<AdminUser> => {
      const response = await httpClient.post<unknown>('/admin/users', {
        external_identity_id: input.externalIdentityId,
        email: input.email,
        display_name: input.displayName,
      });
      return adminUserSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string): Promise<AdminUser> => {
      const response = await httpClient.patch<unknown>(`/admin/users/${userId}/deactivate`);
      return adminUserSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });
}

export interface AssignRoleInput {
  readonly userId: string;
  readonly roleName: string;
}

export function useAssignRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: AssignRoleInput): Promise<RoleAssignment> => {
      const response = await httpClient.post<unknown>(`/admin/users/${input.userId}/roles`, {
        role_name: input.roleName,
      });
      return roleAssignmentSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });
}

export interface RevokeRoleInput {
  readonly userId: string;
  readonly roleId: string;
}

export function useRevokeRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: RevokeRoleInput): Promise<RoleAssignment> => {
      const response = await httpClient.delete<unknown>(
        `/admin/users/${input.userId}/roles/${input.roleId}`,
      );
      return roleAssignmentSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });
}

export function useApiKeys() {
  return useEntityQuery({
    queryKey: ['admin', 'api-keys'],
    url: '/admin/api-keys',
    schema: apiKeyListResponseSchema,
    staleTime: STALE_TIME.informational,
  });
}

export interface CreateApiKeyInput {
  readonly name: string;
  readonly scopes?: readonly string[];
  readonly ttlDays?: number;
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateApiKeyInput): Promise<ApiKeyCreated> => {
      const response = await httpClient.post<unknown>('/admin/api-keys', {
        name: input.name,
        scopes: input.scopes ?? [],
        ttl_days: input.ttlDays ?? 90,
      });
      return apiKeyCreatedSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'api-keys'] });
    },
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (apiKeyId: string): Promise<ApiKey> => {
      const response = await httpClient.delete<unknown>(`/admin/api-keys/${apiKeyId}`);
      return apiKeySchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'api-keys'] });
    },
  });
}
