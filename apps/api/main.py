from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from routers import auth, student, trainer, college, parent, live, notifications, admin_jobs, media, projects, interviews, discussions, messages_hub, admin_colleges, audit_consent, college_structure, college_settings, trainer_batches, schedule, attendance, leave_approvals, content_library, events, monthly_cards, support, assessments, labs, study_buddy

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce production Judge0 requirements (Condition 1)
    if settings.ENVIRONMENT.lower() == "production":
        if settings.JUDGE0_ADAPTER != "judge0" or not settings.JUDGE0_URL or not settings.JUDGE0_AUTH_TOKEN:
            raise RuntimeError(
                "Production environment requires a live Judge0 execution cluster. "
                "JUDGE0_ADAPTER must be 'judge0' with valid JUDGE0_URL and JUDGE0_AUTH_TOKEN."
            )
        if settings.LAB_ADAPTER.lower() != "jupyterhub" or not settings.JUPYTERHUB_URL or not settings.JUPYTERHUB_API_TOKEN:
            raise RuntimeError("Production requires LAB_ADAPTER=jupyterhub with JUPYTERHUB_URL and JUPYTERHUB_API_TOKEN (no fake or local docker labs).")
        if settings.STUDY_BUDDY_ADAPTER.lower() != "anthropic":
            raise RuntimeError("Production requires STUDY_BUDDY_ADAPTER=anthropic (a paid LLM API with no-training terms; no fake tutor).")
        if settings.AUTH_PROVIDER.lower() != "keycloak":
            raise RuntimeError("Production requires AUTH_PROVIDER=keycloak (Master Plan: Keycloak at every stage).")
        if settings.LIVE_CLASS_ADAPTER.lower() == "teams" and not (settings.GRAPH_TENANT_ID and settings.GRAPH_CLIENT_ID and settings.GRAPH_CLIENT_SECRET):
            raise RuntimeError("LIVE_CLASS_ADAPTER=teams needs GRAPH_TENANT_ID, GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET.")
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

