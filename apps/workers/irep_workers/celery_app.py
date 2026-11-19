"""Celery application: broker is Valkey (Redis protocol), beat drains the outbox.

Run (pilot / production, with OUTBOX_RUNNER=celery on the API):
    celery -A irep_workers.celery_app worker --beat --loglevel=info

Teams meeting creation and attendance pull run via irep.teams.queue_due_work. Later:
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
        "teams-due-work": {"task": "irep.teams.queue_due_work", "schedule": 900.0},
    },
)


@app.task(name="irep.outbox.dispatch", ignore_result=True)
def dispatch_outbox(limit: int = 500) -> dict:
    from core.database import SessionLocal
    from services.outbox import dispatch_pending

    return dispatch_pending(SessionLocal, limit=limit)


@app.task(name="irep.teams.queue_due_work", ignore_result=True)
def teams_queue_due_work() -> dict:
    """Every 15 min: create Teams events for upcoming sessions, pull attendance for ended ones."""
    if settings.LIVE_CLASS_ADAPTER.lower() != "teams":
        return {"skipped": True}
    from core.database import SessionLocal
    from services.teams import queue_due_work

    with SessionLocal() as db:
        out = queue_due_work(db)
        db.commit()
        return out
