# IREP Portal

Multi-tenant training portal (students, trainers, parents, colleges, IREP admin), 49 screens.
Plans: `IREP Portal — Master Plan.pdf` (stages, stack, sprints) and `IREP Portal — 26 + 9 Screen Map, Links and Visual Flows.docx`.
Link source of truth: `docs/INTERCONNECT.md`.

## Layout

- `apps/api`: FastAPI and SQLAlchemy 2.
  - `routers/`: endpoints
  - `services/`: rules and adapters
  - `models/schema.py`: models
  - `alembic/`: migrations
  - `seed/`: demo data
  - `tests/`: pytest
- `apps/web`: Next.js 16 App Router, `src/locales/{en,ta}.json`, Playwright in `e2e/`.
  - Read `apps/web/AGENTS.md` first: this Next.js differs from older versions.
- `apps/workers`: Celery app (Valkey broker) that drains the outbox. It imports `apps/api`.
- `docs/INTERCONNECT.md`: links L01–L39, per-screen links, notification and audit events.
- `scripts/link_gate.py`: CI gate. Every `active` link needs a passing test tagged with its ID.

## Commands (Windows dev; the API venv is at `apps/api/venv`)

```bash
# API
cd apps/api
venv/Scripts/python -m alembic upgrade head        # schema (production: migrations only)
venv/Scripts/python seed/run_seed.py               # idempotent; re-anchors demo dates to today
venv/Scripts/python -m uvicorn main:app --port 8000
venv/Scripts/python -m pytest tests -q             # full suite
LINK_REPORT=links.json venv/Scripts/python -m pytest tests -q && python ../../scripts/link_gate.py --pytest links.json

# Migrations
venv/Scripts/python -m alembic revision --autogenerate -m "what changed"   # then read and trim it
venv/Scripts/python -m alembic check               # models and migrations must agree

# Workers
venv/Scripts/python -m pytest ../workers/tests -q
cd ../workers && ../api/venv/Scripts/python -m irep_workers.run_outbox --loop   # no broker needed

# Keycloak (dev): realm "irep" on :8081, then demo users from the DB
docker compose -f ../../infra/keycloak/docker-compose.yml up -d
venv/Scripts/python seed/sync_keycloak.py
KEYCLOAK_IT=1 venv/Scripts/python -m pytest tests/test_keycloak_live.py -q
AUTH_PROVIDER=keycloak venv/Scripts/python -m uvicorn main:app --port 8000

# Web
cd apps/web
pnpm install --frozen-lockfile   # apps/web/pnpm-lock.yaml is the lockfile CI uses
pnpm exec tsc --noEmit
pnpm build
pnpm exec playwright test        # starts API and web unless already running; re-seed first
pnpm exec playwright test -c playwright.keycloak.config.ts   # Keycloak sign-in; stop other APIs on :8000 first
```

Demo logins: `priya.r@demo.edu`, `arun.k@demo.edu`, `admin@demo.edu` (password `password123`). Parents sign in with mobile 9876543210 or 9876543214 plus the OTP that development returns.

## Architecture rules (do not break)

1. **Tenancy.** Every table has `college_id` (`TenantModel`).
   - Every query filters by the `college_id` from the verified token.
   - Resolve the caller's profile with `core/tenant.py`. Never trust ids from the client without checking the tenant.
   - A row from another tenant, or a child not linked to the caller, returns 404, not 403.
2. **Ids.** `students.id` is not `users.id`. Student-owned rows (`student_id`) take `students.id`. Resolve it from `current_user.sub`.
3. **Outbox for every state change.**
   - Side effects (SMS, email, push, fan-out, Graph calls) are written as outbox events with `services/outbox.emit()` in the same transaction as the change.
   - They are delivered after commit by the dispatcher: the API thread in development, `apps/workers` in production.
   - Never call an external gateway inside a request transaction.
   - Handlers must be idempotent.
   - One exception: the parent sign-in OTP is sent directly (`routers/auth.py`), because an outbox payload would store the OTP in plain text.
4. **Audit.** Every approval, release, removal and sensitive read calls `services/audit.record_audit()` in the same transaction. It also emits an `audit.<action>` outbox event.
5. **Notifications.** Use `services/notifications.notify_user()`.
   - In-app rows are immediate. SMS and email are queued through the outbox.
   - Respect quiet hours and the user's language.
6. **Release rules** (`docs/INTERCONNECT.md` §5.1). Monthly cards, Cyber Range access, leave and external certificates change state only after trainer approval.
7. **Messaging.** Who may message whom is decided only in `services/chat_policy.can_message`. There is no student-to-student private chat.
8. **Visibility** (§5.4). The college sees aggregates only: never trainer notes or chats.
9. **i18n.** Every user-facing string goes in both `en.json` and `ta.json` (`tests/test_locale_parity.py` enforces matching keys). API payloads carry `_ta` variants where the UI shows server text.
10. **External engines sit behind adapters.** The fake adapter is the default; production refuses fakes (`ENVIRONMENT=production`).
    - Judge0 and labs are untrusted code: never on the database host.
    - Live classes move to Microsoft Teams via Graph **calendar events** (not standalone online meetings), per the Master Plan.
11. **Schema.**
    - Change `models/schema.py` and add an Alembic revision in the same PR. `alembic check` must pass on SQLite and PostgreSQL.
    - `core/db_init.ensure_schema` is a development convenience only.
12. **Seeds** are deterministic and idempotent.
    - No `uuid4()` or `random` without a fixed seed in generated ids.
    - Dates are relative to today.
    - A re-run restores demo state.

13. **Identity.** `AUTH_PROVIDER=local` (dev default) or `keycloak` (required in production).
    - In Keycloak mode the API verifies RS256 tokens (`core/keycloak.py`). It maps realm role, `irep_user_id` and `college_id` claims to `TokenPayload`.
    - Only admins can edit `irep_user_id` and `college_id` (realm user profile), so users cannot change tenant.
    - Parents keep the API's mobile OTP until Keycloak has SMS OTP (MSG91, pilot). In Keycloak mode a local token is accepted only for the parent role, and `/auth/login` returns 410.
    - Never commit a realm export with users or secrets. `infra/keycloak/realm-irep.json` is a dev realm template.

## Definition of done (per screen or PR)

- The screen's links from `docs/INTERCONNECT.md` §4 are wired. When both ends exist, the link is `active` and has a tagged test:
  - pytest: `@pytest.mark.link("Lxx")`
  - Playwright: `{ tag: "@Lxx" }`
- Notification and audit events from §5.3 are written through the outbox.
- API tests cover:
  - the happy path
  - a wrong-role guard (403)
  - a cross-college check (404)
  - Tamil output where the screen shows server text
- A Playwright spec covers the happy path, the Tamil toggle and the role guard.
- `pytest`, `tsc --noEmit`, `pnpm build`, Playwright, `alembic check` and the link gate are all green.
- README screen table and `openapi.json` are updated when routes change.

## Needs a person's review

Changes to auth, messaging policy, Microsoft Graph, labs, Judge0, migrations that drop data, or `infra/`. Never commit secrets (`.env`, realm exports, Judge0 config).

## Current state (keep this short and true)

- Built: 01, 02, 03, 07, 08, 12, 13, 15, 18, 19, 23, 24, 29, 30, 31, 32, 33, 34, 35, 36, 44, 45, 48 (IREP staff: `staff@irep.demo`, role `irep_admin`, web role `admin`).
- Done in S1: outbox, workers, migrations baseline, link gate, Keycloak (realm, roles, tenancy claims, web PKCE sign-in).
- Consent gate: parent-facing overview (15) needs a granted `parent_data_processing` consent (`services/consent.py`); seed grants it for demo pairs. Files go through `services/storage.py` (local dir in dev).
- Roles: `placement_officer` uses the college UI (sign-in card "College"). Deactivated accounts cannot sign in; tokens already issued stay valid until expiry (known gap, see docs/screens/02).
- `packages/api-client`: generated types; after any route or model change run `cd packages/api-client && npm run generate` (CI fails if stale). Web imports them type-only: `import type { RequestBody } from "@irep/api-client"`.
- Not built yet (S1 plan): Keycloak SMS OTP for parents (pilot). Specs: `docs/screens/NN-*.md` before building a screen.
- Live classes: `LIVE_CLASS_ADAPTER=teams` (`services/teams.py`, Graph mocked in tests) creates calendar events, opens "Join in Teams" and imports attendance (email, then "IREP-<register no> Name", else trainer confirms). Not yet exercised against a real tenant: needs the M365 licence and Graph consent decisions.
