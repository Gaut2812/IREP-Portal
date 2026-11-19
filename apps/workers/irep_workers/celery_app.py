"""Celery application: broker is Valkey (Redis protocol), beat drains the outbox.

Run (pilot / production, with OUTBOX_RUNNER=celery on the API):
    celery -A irep_workers.celery_app worker --beat --loglevel=info

Later sprints add tasks here: Teams meeting creation and attendance pull (S4),
broadcast fan-out in chunks of 500 (S14), nightly readiness and backups.
"""
import irep_workers  # noqa: F401  (puts apps/api on sys.path)

from celery import Celery

from core.config import settings

app = Celery("irep", broker=settings.CELERY_BROKER_URL)
app.conf.update(
    task_acks_late=True,               # a crashed worker's task is redelivered
    worker_prefetch_multiplier=1,
    task_default_queue="irep",
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        "drain-outbox": {"task": "irep.outbox.dispatch", "schedule": settings.OUTBOX_POLL_SECONDS},
    },
)


@app.task(name="irep.outbox.dispatch", ignore_result=True)
def dispatch_outbox(limit: int = 500) -> dict:
    from core.database import SessionLocal
    from services.outbox import dispatch_pending

    return dispatch_pending(SessionLocal, limit=limit)
