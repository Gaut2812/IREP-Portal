# API, Celery worker and Celery beat share this image (apps/workers imports apps/api).
# Build context: the repository root.   docker compose -f infra/prod/docker-compose.yml build
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=8

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 irep

WORKDIR /app
COPY apps/api/requirements.txt apps/api/constraints.txt apps/api/
COPY apps/workers/requirements.txt apps/workers/
RUN pip install -r apps/workers/requirements.txt -c apps/api/constraints.txt

COPY apps/api apps/api
COPY apps/workers apps/workers
# Never ship development leftovers: local SQLite, venv, uploads, .env
RUN rm -rf apps/api/venv apps/api/.env apps/api/irep.db apps/api/var apps/api/static/reports apps/api/static/cards \
 && find /app -name "__pycache__" -type d -prune -exec rm -rf {} + \
 && mkdir -p /data/uploads && chown -R irep:irep /data /app

USER irep
WORKDIR /app/apps/api
ENV STORAGE_DIR=/data/uploads
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD curl -fsS http://127.0.0.1:8000/health || exit 1
# Production: no reload; proxy headers come from Caddy only (same Docker network).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
