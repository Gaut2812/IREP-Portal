import os
import sys
from pathlib import Path

# Ensure root repository is in sys.path
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.core.config import settings
from apps.api.routers import auth, student, trainer, college, parent, live

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Industry-Ready Engineer Program (IREP) Full-Stack Training Portal API"
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
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
