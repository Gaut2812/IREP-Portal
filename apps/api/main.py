from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from routers import auth, student, trainer, college, parent, live

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce production Judge0 requirements (Condition 1)
    if settings.ENVIRONMENT.lower() == "production":
        if settings.JUDGE0_ADAPTER != "judge0" or not settings.JUDGE0_URL or not settings.JUDGE0_AUTH_TOKEN:
            raise RuntimeError(
                "Production environment requires a live Judge0 execution cluster. "
                "JUDGE0_ADAPTER must be 'judge0' with valid JUDGE0_URL and JUDGE0_AUTH_TOKEN."
            )
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Industry-Ready Engineer Program (IREP) Full-Stack Training Portal API",
    lifespan=lifespan
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to settings.PUBLIC_BASE_URL
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

