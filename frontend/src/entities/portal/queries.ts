/**
 * Customer Portal query/mutation hooks (spec 005-enterprise-platform §12,
 * Wave 4).
 *
 * Built directly on `portalHttpClient`/`useQuery`/`useMutation` rather than
 * the shared `createEntityQuery` helper, which is hardwired to the
 * internal `httpClient` instance — a deliberate, disclosed choice, not an
 * oversight: the portal's separate auth realm needs a separate client, and
 * duplicating `createEntityQuery` for one small entity module was judged
 * not worth the abstraction. Every response is still parsed through a Zod
 * schema, preserving the same "a contract change fails loudly" guarantee.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { portalAuthStore } from '@app/auth/portalAuthStore';
import { portalHttpClient } from '@app/auth/portalHttpClient';

import { checklistItemSchema, portalSessionSchema, portalStatusSchema } from './types';

export function usePortalChecklist() {
  return useQuery({
    queryKey: ['portal', 'checklist'],
    queryFn: async () => {
      const response = await portalHttpClient.get<unknown>('/checklist');
      return z.object({ items: z.array(checklistItemSchema) }).parse(response.data).items;
    },
    enabled: portalAuthStore.isAuthenticated(),
  });
}

export function usePortalStatus() {
  return useQuery({
    queryKey: ['portal', 'status'],
    queryFn: async () => {
      const response = await portalHttpClient.get<unknown>('/status');
      return portalStatusSchema.parse(response.data);
    },
    enabled: portalAuthStore.isAuthenticated(),
  });
}

export interface ActivateInput {
  readonly partyId: string;
  readonly token: string;
}

export function useActivatePortalAccount() {
  return useMutation({
    mutationFn: async (input: ActivateInput): Promise<string> => {
      const response = await portalHttpClient.post<unknown>('/auth/activate', {
        party_id: input.partyId,
        token: input.token,
      });
      return portalSessionSchema.parse(response.data).sessionToken;
    },
    onSuccess: (sessionToken) => {
      portalAuthStore.setSessionToken(sessionToken);
    },
  });
}

export interface UploadForChecklistItemInput {
  readonly itemId: string;
  readonly file: File;
  readonly documentType: string;
}

export function useUploadForChecklistItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: UploadForChecklistItemInput) => {
      const formData = new FormData();
      formData.append('file', input.file);
      formData.append('document_type', input.documentType);
      const response = await portalHttpClient.post<unknown>(
        `/checklist/${input.itemId}/upload`,
        formData,
      );
      return checklistItemSchema.parse(response.data);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['portal', 'checklist'] });
    },
  });
}
