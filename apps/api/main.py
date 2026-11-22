import logging
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from routers import auth, student, trainer, college, parent, live, notifications, admin_jobs, media, projects, interviews, discussions, messages_hub, admin_colleges, audit_consent, college_structure, college_settings, trainer_batches, schedule, attendance, leave_approvals, content_library, events, monthly_cards, support, assessments, labs, study_buddy, certificates, usage, college_messages, surveys

class _RedactSecrets(logging.Filter):
    """Access logs never show bearer tokens or link signatures (WebSockets pass ?token=, media links ?sig=)."""
    _q = re.compile(r"((?:token|sig|signature|code|otp)=)[^&\s\"]+", re.I)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(self._q.sub(r"\1[redacted]", a) if isinstance(a, str) else a for a in record.args)
        return True


logging.getLogger("uvicorn.access").addFilter(_RedactSecrets())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production refuses fakes and unsafe defaults (core/production.py; pilot: ALLOW_DEMO_ADAPTERS)
    if settings.ENVIRONMENT.lower() == "production":
        from core.production import allowed_demo, problems
        found = problems(settings)
        if found:
            raise RuntimeError("Production configuration is not safe to start:\n- " + "\n- ".join(found))
        if allowed_demo(settings):
            import logging
            logging.getLogger("irep").warning("Demo adapters kept for features outside the pilot: %s", ", ".join(sorted(allowed_demo(settings))))
    # Development: keep the local SQLite schema in sync with the models.
    if settings.ENVIRONMENT.lower() != "production":
        from core.database import engine
        from core.db_init import ensure_schema
        ensure_schema(engine)
    from services.realtime import register_event_loop
    register_event_loop()
    # Outbox: drain in-process unless a Celery worker (apps/workers) owns it
    from services import outbox
    if settings.OUTBOX_RUNNER == "thread":
        from core.database import SessionLocal
        outbox.start_background_dispatcher(SessionLocal)
    yield
    outbox.stop_background_dispatcher()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Industry-Ready Engineer Program (IREP) Full-Stack Training Portal API",
    lifespan=lifespan
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    # development: any origin; production: only the portal itself
    allow_origins=[settings.PUBLIC_BASE_URL] if settings.ENVIRONMENT.lower() == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api/v1
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(student.router, prefix=settings.API_V1_PREFIX)
app.include_router(trainer.router, prefix=settings.API_V1_PREFIX)
app.include_router(college.router, prefix=settings.API_V1_PREFIX)
app.include_router(parent.router, prefix=settings.API_V1_PREFIX)
app.include_router(live.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(media.router)
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(interviews.router, prefix=settings.API_V1_PREFIX)
app.include_router(discussions.router, prefix=settings.API_V1_PREFIX)
app.include_router(messages_hub.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_colleges.router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_consent.router, prefix=settings.API_V1_PREFIX)
app.include_router(college_structure.router, prefix=settings.API_V1_PREFIX)
app.include_router(college_settings.router, prefix=settings.API_V1_PREFIX)
app.include_router(trainer_batches.router, prefix=settings.API_V1_PREFIX)
app.include_router(schedule.router, prefix=settings.API_V1_PREFIX)
app.include_router(attendance.router, prefix=settings.API_V1_PREFIX)
app.include_router(leave_approvals.router, prefix=settings.API_V1_PREFIX)
app.include_router(content_library.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.router, prefix=settings.API_V1_PREFIX)
app.include_router(monthly_cards.router, prefix=settings.API_V1_PREFIX)
app.include_router(support.router, prefix=settings.API_V1_PREFIX)
app.include_router(assessments.router, prefix=settings.API_V1_PREFIX)
app.include_router(labs.router, prefix=settings.API_V1_PREFIX)
app.include_router(study_buddy.router, prefix=settings.API_V1_PREFIX)
app.include_router(certificates.router, prefix=settings.API_V1_PREFIX)
app.include_router(usage.router, prefix=settings.API_V1_PREFIX)
app.include_router(college_messages.router, prefix=settings.API_V1_PREFIX)
app.include_router(surveys.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    return {
        "portal": "IREP Training Portal API",
        "version": settings.VERSION,
        "docs": "/docs",
        "tenant": settings.DEFAULT_COLLEGE_NAME
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

