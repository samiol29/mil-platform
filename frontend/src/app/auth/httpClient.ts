/**
 * HTTP client (spec 002 tasks.md T034; plan.md Authentication Flow, Server
 * State & API Integration Strategy).
 *
 * The single Axios instance every entity-layer query/mutation hook uses -
 * no feature or entity module constructs its own client or calls
 * fetch/axios directly. A request interceptor attaches the current bearer
 * token from authProvider; no caller manages the Authorization header
 * itself. Same-origin (baseURL: '/v1') per plan.md's Deployment Strategy -
 * the dev proxy (vite.config.ts) forwards this to the API in development,
 * and same-origin deployment in production removes CORS entirely.
 *
 * A response interceptor converts every response body's keys from the
 * backend's snake_case (standard FastAPI/Pydantic convention) to the
 * camelCase data-model.md specifies for every entity field - applied once,
 * centrally, here, so every entity Zod schema (entities/*\/types.ts) can be
 * declared in the vocabulary data-model.md actually documents.
 */

import axios from 'axios';

import { authProvider } from '@app/auth/authProvider';
import { camelCaseKeysDeep } from '@shared/api/caseTransform';

export const httpClient = axios.create({
  baseURL: '/v1',
});

httpClient.interceptors.request.use((config) => {
  const token = authProvider.getAccessToken();
  if (token !== null) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

httpClient.interceptors.response.use((response) => {
  // Binary responses (PdfRenderer's `responseType: 'arraybuffer'` document
  // fetch) have no snake_case keys to convert — `camelCaseKeysDeep` would
  // treat an `ArrayBuffer`/`Blob` as a plain object (its own enumerable
  // properties are empty) and silently replace it with `{}`, corrupting
  // the payload. Skip the transform entirely for these.
  if (response.data instanceof ArrayBuffer || response.data instanceof Blob) {
    return response;
  }
  response.data = camelCaseKeysDeep(response.data);
  return response;
});
