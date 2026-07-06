/**
 * snake_case → camelCase response key transform (plan.md Server State & API
 * Integration Strategy; data-model.md's Naming Rule).
 *
 * The backend returns snake_case JSON (standard FastAPI/Pydantic
 * convention — see any `*Response` schema in `src/mil/api/v1/schemas.py`);
 * `data-model.md` specifies every frontend entity field in camelCase. Without
 * this transform, no entity Zod schema could ever parse a real API response
 * — applied once, centrally, in `httpClient`'s response interceptor, so
 * every entity module can declare its schema in the camelCase data-model.md
 * actually documents.
 */

function toCamelCase(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_match, char: string) => char.toUpperCase());
}

export function camelCaseKeysDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(camelCaseKeysDeep);
  }
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, v]) => [
        toCamelCase(key),
        camelCaseKeysDeep(v),
      ]),
    );
  }
  return value;
}
