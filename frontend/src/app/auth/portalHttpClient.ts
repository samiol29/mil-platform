/**
 * Customer Portal HTTP client (spec 005-enterprise-platform §12, Wave 4).
 *
 * A separate Axios instance from `httpClient.ts` (internal staff) — attaches
 * the portal session token (`portalAuthStore`), never the internal bearer
 * token, so a portal frontend session can never accidentally call an
 * internal endpoint with staff credentials or vice versa. Same case-
 * transform convention as the internal client (backend snake_case ->
 * frontend camelCase).
 */

import axios from 'axios';

import { portalAuthStore } from '@app/auth/portalAuthStore';
import { camelCaseKeysDeep } from '@shared/api/caseTransform';

export const portalHttpClient = axios.create({
  baseURL: '/v1/portal',
});

portalHttpClient.interceptors.request.use((config) => {
  const token = portalAuthStore.getSessionToken();
  if (token !== null) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

portalHttpClient.interceptors.response.use((response) => {
  response.data = camelCaseKeysDeep(response.data);
  return response;
});
