"""The Celery task and the broker-less runner drive the same outbox dispatch."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import irep_workers  # noqa: E402,F401
from core.database import SessionLocal  # noqa: E402
from models.schema import OutboxEvent  # noqa: E402
from services import outbox  # noqa: E402


def _pending_event():
    db = SessionLocal()
    try:
        ev_id = outbox.emit(db, "test.worker." + uuid.uuid4().hex[:6], {}, college_id="col_demo_001").id
        db.commit()
        return ev_id
    finally:
        db.close()


def _status(ev_id):
    db = SessionLocal()
    try:
        return db.get(OutboxEvent, ev_id).status
    finally:
        db.close()


def test_celery_task_is_registered_and_beat_drains_the_outbox():
    from irep_workers.celery_app import app, dispatch_outbox

    assert "irep.outbox.dispatch" in app.tasks
    assert app.conf.beat_schedule["drain-outbox"]["task"] == "irep.outbox.dispatch"
    ev_id = _pending_event()
    dispatch_outbox.run(limit=100_000)      # the task body, without a broker
    assert _status(ev_id) == "done"


def test_brokerless_runner_one_pass(monkeypatch):
    from irep_workers import run_outbox

    ev_id = _pending_event()
    monkeypatch.setattr(sys, "argv", ["run_outbox", "--limit", "100000"])
    run_outbox.main()
    assert _status(ev_id) == "done"


def test_nightly_readiness_is_scheduled_and_its_handler_is_loaded():
    from irep_workers.celery_app import app

    nightly = app.conf.beat_schedule["readiness-nightly"]
    assert nightly["task"] == "irep.readiness.nightly" and "irep.readiness.nightly" in app.tasks
    assert nightly["schedule"].hour == {1} and nightly["schedule"].minute == {30}     # 01:30 Asia/Kolkata
    outbox._load_handlers()
    assert "at_risk.parent_call" in outbox._HANDLERS                                  # held parent calls reach a worker
