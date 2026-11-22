# IREP Training Portal

**Industry-Ready Engineer Program (IREP) · B.Tech Semesters 2 to 7**

A multi-tenant training portal for students, trainers, colleges and parents. The web app is Next.js 16 (App Router), the API is FastAPI with SQLAlchemy 2 (SQLite in development, PostgreSQL in production), and every screen is available in English and Tamil.

## Project structure

```
apps/
├── api/                  FastAPI backend
│   ├── alembic/          Database migrations (one revision per screen)
│   ├── core/             Settings, database, JWT security, tenant helpers
│   ├── models/           SQLAlchemy models (every table carries college_id)
│   ├── routers/          API endpoints
│   ├── services/         Business logic and external-engine adapters
│   ├── seed/             Deterministic demo seed (612-student cohort)
│   └── tests/            pytest suite
└── web/                  Next.js frontend
    ├── src/app/          Pages for all 14 mockup screens
    ├── src/components/   AppShell, RoleGuard, NotificationBell
    ├── src/lib/          API client, AuthContext, LanguageContext
    ├── src/locales/      en.json and ta.json
    └── e2e/              Playwright specs (one per screen)
```

## Quick start

### 1. API

```bash
cd apps/api
python -m venv venv && venv\Scripts\pip install -r requirements.txt
copy .env.example .env
venv\Scripts\python -m alembic upgrade head
venv\Scripts\python seed\run_seed.py
venv\Scripts\python -m uvicorn main:app --port 8000
```

The API runs at `http://localhost:8000`; interactive docs are at `/docs`. `openapi.json` in `apps/api` is the committed copy of the schema.

Re-running `seed\run_seed.py` is safe. It re-anchors the demo calendar to today and restores demo state (messages, reports, lockouts and OTP history created by tests or demos).

### 2. Web

```bash
cd apps/web
pnpm install
pnpm dev
```

The web app runs at `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` if the API is not on `http://localhost:8000/api/v1`.

## Demo accounts

| Role | Sign in | Lands on |
| --- | --- | --- |
| Student | `priya.r@demo.edu` / `password123` | `/student` |
| Trainer | `arun.k@demo.edu` / `password123` | `/trainer` |
| College admin | `admin@demo.edu` / `password123` | `/college` |
| Parent | Mobile `9876543210` (Ramesh K) or `9876543214` (Lakshmi S), then the OTP | `/parent` |

In development the API returns the OTP in its response and the sign-in card shows it as "Demo OTP". In production it is sent only by SMS. The **View as** switcher in the top bar signs in as each demo role.

Sign-in rules:
- Five wrong passwords lock an account for 15 minutes.
- Each phone can request at most 5 OTPs per 10 minutes, and each OTP allows 5 tries.

## Screens

| # | Screen | Route |
| --- | --- | --- |
| 01 | Sign-in | `/login` |
| 07 | Live classroom | `/live/{sessionId}` |
| 08 | Live sessions & recordings | `/student/live` |
| 12 | Student dashboard | `/student` |
| 13 | Trainer dashboard | `/trainer` |
| 15 | Parent view (mobile first) | `/parent` |
| 19 | College dashboard | `/college` |
| 23 | Practice test | `/student/tests/{id}` |
| 24 | Coding lab | `/student/coding/{problemId}` |
| 29 | Virtual labs | `/student/labs` |
| 30 | Sprint board | `/student/projects/{teamId}/board` |
| 34 | Discussion groups | `/student/discussions` |
| 35 | Trainer message hub | `/trainer/messages` (parents: `/parent/messages`) |
| 36 | Mock interviews | `/student/interviews` |

## External engines

Each external service sits behind an adapter. The default is a local fake, so the portal runs with no extra infrastructure; set the variable in `.env` to use the real service.

| Variable | Fake (default) | Real |
| --- | --- | --- |
| `JUDGE0_ADAPTER` | in-process runner | `judge0` (`JUDGE0_URL`) |
| `LIVE_CLASS_ADAPTER` | in-portal classroom | `bbb` (`BBB_URL`, `BBB_SECRET`) |
| `LAB_ADAPTER` | simulated lab sessions | `docker` |
| `TRANSLATE_ADAPTER` | seeded Tamil pairs + glossary, cached | `libretranslate` (`TRANSLATE_URL`) |
| `REALTIME_ADAPTER` | in-process WebSocket hub | `valkey` |
| `NOTIFY_ADAPTER` | records SMS/email in memory | `smtp` / `sms` |

`.env.example` lists every variable. With `ENVIRONMENT=production`, the development fallbacks are disabled: the `X-Demo-Role` header, the returned demo OTP and permissive CORS.

## Tests

```bash
# API (pytest)
cd apps/api
venv\Scripts\python -m pytest tests -q

# Web (Playwright). Global setup re-seeds the database first.
cd apps/web
pnpm build
pnpm exec playwright test
```

Every screen has a `tests/test_screen_NN_*.py` file and an `e2e/screenNN-*.spec.ts` file. Each covers the happy path, the Tamil toggle, a wrong-role guard and a cross-college (tenant) check.
