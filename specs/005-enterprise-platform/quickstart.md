# Quickstart: Enterprise Platform — Wave 1

## Prerequisites
- Existing MIL dev environment running (`docs/deployment/` setup already in place).
- A dev database with the existing MVP schema migrated (`core`, `finding`, `evidence`, `audit`,
  etc.).

## 1. Verify migration state before writing routes (per research.md R1)
```bash
alembic current
alembic history | grep -iE "identity|policy|review|copilot"
```
If `identity.users`/`policy.policy_packs`/`review.review_comments` tables don't exist yet, the
first task in each module's implementation is writing/applying that migration — not assumed.

## 2. Enterprise Administration
```bash
alembic upgrade head   # after adding the identity migration
uvicorn main:app --reload
curl -X POST localhost:8000/v1/admin/users -H "Authorization: Bearer <admin-token>" \
  -d '{"email":"reviewer@example.com","roles":["UNDERWRITER"]}'
curl localhost:8000/v1/admin/users -H "Authorization: Bearer <admin-token>"
```
Expected: a created user is listed; a non-admin token against the same endpoints returns 403.

## 3. Policy Engine + Policy Administration
```bash
curl -X POST localhost:8000/v1/policy-packs -d '{"name":"US Standard v1","jurisdiction":"US"}' \
  -H "Authorization: Bearer <policy-admin-token>"
curl -X POST localhost:8000/v1/policy-packs/{id}/submit-for-approval -H "..."
curl -X POST localhost:8000/v1/policy-packs/{id}/approve -H "Authorization: Bearer <compliance-officer-token>"
curl -X POST localhost:8000/v1/policy-packs/{id}/activate -H "..."
```
Expected: the same user who drafted the pack cannot approve it (403); once activated, a new
finding-generation run for an application produces a `PolicyResult` row for every rule in the
active pack, not only the ones that triggered.

## 4. AI Case Copilot (frontend only — backend already live)
```bash
cd frontend && npm run dev
```
Open an application's Workspace, expand the new Copilot panel, ask a question referencing a real
Finding on that application. Expected: an answer with at least one clickable citation that jumps
to the source document/page, matching the existing evidence-chip jump behavior.

## 5. Collaboration
```bash
curl -X POST localhost:8000/v1/applications/{id}/comments \
  -d '{"body":"@compliance please review","mentionedUserIds":["<user-id>"]}' \
  -H "Authorization: Bearer <underwriter-token>"
```
Expected: comment appears in `GET /v1/applications/{id}/comments`; the mentioned user (if they
have access to the application) receives a notification event (Wave 3's Notification System isn't
built yet — for Wave 1, verify the event is recorded/loggable even if delivery is a stub/no-op).

## Full-suite verification (run after each module, per the chosen sequencing)
```bash
pytest tests/unit -k "identity or policy or review or copilot"
npm --prefix frontend run test
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run build
npx --prefix frontend playwright test
```
Do not proceed to the next module in the sequence until the current module's own tests, the full
existing test suite, and a real (non-mocked) manual walkthrough all pass — the MVP's own RC1 pass
established that unit-test-green does not substitute for a live walkthrough.
