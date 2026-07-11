/**
 * Enterprise Administration entities (spec 005-enterprise-platform §15).
 *
 * Matches `src/mil/api/v1/schemas.py`'s `UserResponse`/`RoleAssignmentResponse`/
 * `TenantConfigurationResponse`/`ApiKeyResponse` shapes exactly — no field is
 * added here that the backend doesn't actually return (same discipline as
 * `entities/application/types.ts`).
 */

import { z } from 'zod';

export const adminUserSchema = z.object({
  id: z.uuid(),
  tenantId: z.uuid(),
  displayName: z.string(),
  isActive: z.boolean(),
  roles: z.array(z.string()),
  createdAt: z.iso.datetime(),
});

export type AdminUser = z.infer<typeof adminUserSchema>;

export const roleAssignmentSchema = z.object({
  id: z.uuid(),
  userId: z.uuid(),
  roleId: z.uuid(),
  roleName: z.string(),
  assignedBy: z.uuid(),
  assignedAt: z.iso.datetime(),
  revokedAt: z.iso.datetime().nullable(),
});

export type RoleAssignment = z.infer<typeof roleAssignmentSchema>;

export const apiKeySchema = z.object({
  id: z.uuid(),
  tenantId: z.uuid(),
  name: z.string(),
  scopes: z.array(z.string()),
  expiresAt: z.iso.datetime(),
  revokedAt: z.iso.datetime().nullable(),
  createdByUserId: z.uuid(),
  createdAt: z.iso.datetime(),
});

export type ApiKey = z.infer<typeof apiKeySchema>;

export const apiKeyCreatedSchema = apiKeySchema.extend({
  rawKey: z.string(),
});

export type ApiKeyCreated = z.infer<typeof apiKeyCreatedSchema>;
