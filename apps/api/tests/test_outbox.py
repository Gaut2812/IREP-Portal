"""Transactional outbox: side effects follow commits, never rollbacks."""
import datetime
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.security import TokenPayload
from models.schema import Notification, OutboxEvent
from services import outbox
from services.audit import record_audit
from services.notifications import FakeNotificationAdapter, notify_user

RAMESH = "usr_ramesh_01"


def _drain():
    return outbox.dispatch_pending(SessionLocal, limit=100_000)


def _sent_to(title):
    return [s for s in FakeNotificationAdapter.sent if s["title"] == title]


def test_rollback_sends_nothing_and_leaves_no_event():
    title = "rollback-" + uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        rows = notify_user(db, RAMESH, title, "body", channels=("in_app", "sms"))
        sms_id = next(n.id for n in rows if n.channel == "sms")
        db.flush()
        db.rollback()
    finally:
        db.close()
    _drain()
    assert _sent_to(title) == []
    db = SessionLocal()
    try:
        assert db.get(Notification, sms_id) is None
        assert db.execute(select(OutboxEvent).filter_by(entity_id=sms_id)).first() is None
    finally:
        db.close()


def test_sms_is_queued_in_the_transaction_and_sent_once_after_commit():
    title = "commit-" + uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        rows = notify_user(db, RAMESH, title, "body", channels=("in_app", "sms"))
        statuses = {n.channel: n.delivery_status for n in rows}
        sms_id = next(n.id for n in rows if n.channel == "sms")
        db.commit()
    finally:
        db.close()
    assert statuses == {"in_app": "delivered", "sms": "queued"}
    assert _sent_to(title) == []          # nothing leaves before the worker runs

    _drain()
    _drain()                              # a second pass must not resend
    assert len(_sent_to(title)) == 1
    db = SessionLocal()
    try:
        assert db.get(Notification, sms_id).delivery_status == "delivered"
        ev = db.execute(select(OutboxEvent).filter_by(entity_id=sms_id)).scalar_one()
        assert ev.event_type == "notification.deliver" and ev.status == "done" and ev.attempts == 1
    finally:
        db.close()


def test_failing_handler_backs_off_then_parks_as_failed(monkeypatch):
    calls = {"n": 0}
    etype = "test.boom." + uuid.uuid4().hex[:6]

    @outbox.handler(etype)
    def boom(db, ev):
        calls["n"] += 1
        raise RuntimeError("gateway down")

    monkeypatch.setattr(settings, "OUTBOX_MAX_ATTEMPTS", 3)
    db = SessionLocal()
    try:
        ev_id = outbox.emit(db, etype, {"x": 1}, college_id="col_demo_001").id
        db.commit()
    finally:
        db.close()

    def state():
        s = SessionLocal()
        try:
            e = s.get(OutboxEvent, ev_id)
            return e.status, e.attempts, e.available_at, e.last_error
        finally:
            s.close()

    _drain()
    status, attempts, available_at, err = state()
    assert (status, attempts) == ("pending", 1) and "gateway down" in err
    assert available_at > datetime.datetime.utcnow()      # backed off, not hot-looping
    _drain()
    assert calls["n"] == 1                                 # not due yet

    for expected in (2, 3):
        s = SessionLocal()
        try:
            s.get(OutboxEvent, ev_id).available_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
            s.commit()
        finally:
            s.close()
        _drain()
        assert state()[1] == expected
    assert state()[0] == "failed" and calls["n"] == 3
    outbox._HANDLERS.pop(etype, None)


def test_every_audited_change_is_an_outbox_event_in_the_same_transaction():
    action = "test.audited_" + uuid.uuid4().hex[:6]
    user = TokenPayload(sub="usr_arun_01", role="trainer", college_id="col_demo_001")
    db = SessionLocal()
    try:
        record_audit(db, user, action, "thing", "t1", {"k": 1})
        db.rollback()
        assert db.execute(select(OutboxEvent).filter_by(event_type="audit." + action)).first() is None
        entry = record_audit(db, user, action, "thing", "t1", {"k": 1})
        db.commit()
        ev = db.execute(select(OutboxEvent).filter_by(event_type="audit." + action)).scalar_one()
        assert ev.payload["audit_id"] == entry.id and ev.entity_id == "t1" and ev.college_id == "col_demo_001"
    finally:
        db.close()
    _drain()
    db = SessionLocal()
    try:
        # no subscriber yet: recorded and closed, not retried forever
        assert db.execute(select(OutboxEvent).filter_by(event_type="audit." + action)).scalar_one().status == "done"
    finally:
        db.close()


def test_handlers_cannot_be_registered_twice_for_one_event_type():
    with pytest.raises(ValueError):
        outbox.handler("notification.deliver")(lambda db, ev: None)
