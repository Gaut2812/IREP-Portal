# IREP Training Portal

**Industry-Ready Engineer Program (IREP) · B.Tech Semesters 2 to 7**

Full-Stack Training Portal built with Next.js (App Router), FastAPI, and PostgreSQL/SQLite, covering all 14 illustrated screens across Students, Trainers, Colleges, and Parents.

## Project Structure

```
d:\IREP Portal\
├── apps/
│   ├── api/             # FastAPI backend with SQLAlchemy 2.0 & SQLite database
│   │   ├── core/        # Settings, database connection, JWT security
│   │   ├── models/      # Multi-tenant SQLAlchemy models
│   │   ├── routers/     # API endpoints for auth, student, trainer, college, parent, live
│   │   ├── seed/        # Seed script matching the PDF mockups
│   │   ├── tests/       # Backend tests
│   │   └── main.py      # FastAPI entrypoint
│   └── web/             # Next.js 16 App Router frontend
│       ├── src/
│       │   ├── app/     # App Router pages for all 14 screens
│       │   ├── components/ # AppShell, navigation, headers
│       │   ├── lib/     # AuthContext, LanguageContext (i18n), API client
│       │   └── locales/ # en.json & ta.json (Tamil bilingual support)
```

## Quick Start

### 1. Backend Setup & Run
```bash
cd apps/api
& "venv\Scripts\python.exe" -m apps.api.main
```
Backend runs at `http://localhost:8000`. Interactive OpenAPI documentation at `http://localhost:8000/docs`.

### 2. Frontend Setup & Run
```bash
cd apps/web
pnpm dev
```
Frontend runs at `http://localhost:3000`.

## Seed Accounts
- **Student**: `priya.r@demo.edu` / `password123` → lands on `/student`
- **Trainer**: `arun.k@demo.edu` / `password123` → lands on `/trainer`
- **College Admin**: `admin@demo.edu` / `password123` → lands on `/college`
- **Parent**: Mobile `9876543210` / Demo OTP `123456` → lands on `/parent`
- Use the **"View as"** role switcher pill in the top navigation bar to jump between views instantly.
