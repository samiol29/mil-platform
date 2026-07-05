# Existing Backend API Surface (as of this plan)

This is a factual inventory of what the backend already exposes, taken directly from `src/mil/api/v1/` at planning time. The frontend consumes these as-is; per the governing instruction ("frontend should consume existing APIs rather than changing backend contracts unless absolutely necessary"), none of these are proposed to change.

| Router | Endpoints |
|---|---|
| `auth.py` | `GET` current authenticated user |
| `applications.py` | create, list, get, submit, withdraw an application; add/remove/list parties |
| `documents.py` | upload a document, list documents for an application, get a document |
| `copilot.py` | submit a query, get a session, get session history, get latest session |
| `ops.py` | health, liveness, readiness, metrics |

Authentication today is `Authorization: Bearer <token>`, resolved by an `IdentityProvider` — in development, `DevBearerIdentityProvider` (accepts the literal token `dev` and a Base64URL JSON claims payload). **No signature-verifying (OIDC/JWKS) provider exists yet for non-development environments** — `build_container` deliberately fails fast rather than accept unsigned tokens outside development (see `src/mil/api/deps.py` / `_register_identity_provider`). This is a real, already-known, named backend dependency for production readiness, not something introduced by this plan.

No CORS middleware is currently configured. See `research.md` and the Deployment Strategy in `plan.md` for why this plan recommends a same-origin deployment (frontend and API behind one gateway) specifically to avoid needing one.
