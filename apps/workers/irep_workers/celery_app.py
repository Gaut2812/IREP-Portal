"""Celery application: broker is Valkey (Redis protocol), beat drains the outbox.

Run (pilot / production, with OUTBOX_RUNNER=celery on the API):
    celery -A irep_workers.celery_app worker --beat --loglevel=info

Teams meeting creation and attendance pull run via irep.teams.queue_due_work. Later:
broadcast fan-out in chunks of 500 (S14) and backups. Nightly readiness (S7) runs at 01:30 IST.
"""
import irep_workers  # noqa: F401  (puts apps/api on sys.path)

from celery import Celery
from celery.schedules import crontab

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
        "readiness-nightly": {"task": "irep.readiness.nightly", "schedule": crontab(hour=1, minute=30)},
        "labs-meter": {"task": "irep.labs.meter", "schedule": 300.0},
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


@app.task(name="irep.readiness.nightly", ignore_result=True)
def readiness_nightly() -> dict:
    """01:30 IST: readiness v1 for every college (attendance, score, delta, at-risk flags)."""
    from sqlalchemy import select

    from core.database import SessionLocal
    from core.security import PLATFORM_TENANT
    from models.schema import College
    from services.readiness import run_nightly

    out = {}
    with SessionLocal() as db:
        ids = [c for c in db.execute(select(College.id)).scalars() if c != PLATFORM_TENANT]
    for college_id in ids:
        with SessionLocal() as db:
            out[college_id] = run_nightly(db, college_id)
            db.commit()
    return out


@app.task(name="irep.labs.meter", ignore_result=True)
def labs_meter() -> dict:
    """Every 5 min: cAdvisor sample for server labs (CPU, memory, activity). Off when LAB_METER_URL is empty."""
    from core.database import SessionLocal
    from services.lab_metering import meter

    with SessionLocal() as db:
        out = meter(db)
        db.commit()
        return out
