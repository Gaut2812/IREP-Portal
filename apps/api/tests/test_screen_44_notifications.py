"""Screen 44 · Notification centre: list, filters, read state, delivery preferences."""
import datetime
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import Notification, NotificationPreference, OutboxEvent, User
from services import outbox
from services.notifications import FakeNotificationAdapter, notify_user, quiet_delay_seconds

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


RAMESH, PRIYA = _h("usr_ramesh_01", "parent"), _h("usr_priya_01", "student")


@pytest.fixture
def ramesh_prefs():
    """Restore Ramesh's preferences and language after the test."""
    db = SessionLocal()
    try:
        lang = db.get(User, "usr_ramesh_01").language_pref
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == "usr_ramesh_01"))
        db.get(User, "usr_ramesh_01").language_pref = lang
        db.commit()
    finally:
        db.close()


def _notify(title, channels=("in_app",), **kw):
    db = SessionLocal()
    try:
        rows = notify_user(db, "usr_ramesh_01", title, "body", title_ta=title + " (ta)", channels=channels, **kw)
        ids = {n.channel: n.id for n in rows}
        db.commit()
        return ids
    finally:
        db.close()


def test_filters_unread_and_cursor_paging():
    tag = uuid.uuid4().hex[:6]
    for i in range(5):
        _notify(f"page-{tag}-{i}", kind="report")
    first = client.get("/api/v1/notifications?kind=report&limit=3", headers=RAMESH).json()
    assert len(first["items"]) == 3 and first["next_before"] and "report" in first["kinds"]
    assert all(i["kind"] == "report" for i in first["items"])
    second = client.get(f"/api/v1/notifications?kind=report&limit=3&before={first['next_before']}", headers=RAMESH).json()
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})
    newest = first["items"][0]
    client.post(f"/api/v1/notifications/{newest['id']}/read", headers=RAMESH)
    unread = client.get("/api/v1/notifications?kind=report&unread_only=true&limit=100", headers=RAMESH).json()["items"]
    assert newest["id"] not in {i["id"] for i in unread}
    # another user's notification is not found
    assert client.post(f"/api/v1/notifications/{newest['id']}/read", headers=PRIYA).status_code == 404


def test_preferences_defaults_validation_and_language(ramesh_prefs):
    d = client.get("/api/v1/notifications/preferences", headers=RAMESH).json()
    assert d["in_app"] is True and d["sms_enabled"] is True and d["push_enabled"] is False and d["quiet_start_hour"] is None
    body = {"email_enabled": False, "sms_enabled": True, "push_enabled": False, "quiet_start_hour": 21, "quiet_end_hour": 7, "language": "en"}
    assert client.put("/api/v1/notifications/preferences", json={**body, "quiet_end_hour": None}, headers=RAMESH).status_code == 422
    assert client.put("/api/v1/notifications/preferences", json={**body, "quiet_start_hour": 24}, headers=RAMESH).status_code == 422
    r = client.put("/api/v1/notifications/preferences", json=body, headers=RAMESH).json()
    assert (r["email_enabled"], r["quiet_start_hour"], r["quiet_end_hour"], r["language"]) == (False, 21, 7, "en")
    assert client.get("/api/v1/auth/me", headers=RAMESH).json()["language_pref"] == "en"


def test_switched_off_channel_is_suppressed_not_sent(ramesh_prefs):
    client.put("/api/v1/notifications/preferences", json={"email_enabled": True, "sms_enabled": False, "push_enabled": False,
                                                          "quiet_start_hour": None, "quiet_end_hour": None, "language": "ta"}, headers=RAMESH)
    title = "sms-off-" + uuid.uuid4().hex[:6]
    ids = _notify(title, channels=("in_app", "sms"))
    db = SessionLocal()
    try:
        assert db.get(Notification, ids["sms"]).delivery_status == "suppressed"
        assert db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == ids["sms"])).first() is None
        assert db.get(Notification, ids["in_app"]).delivery_status == "delivered"
    finally:
        db.close()


def test_quiet_hours_delay_sms_and_language_is_respected(ramesh_prefs):
    now = datetime.datetime.now()
    start, end = (now.hour - 1) % 24, (now.hour + 2) % 24                 # quiet right now
    client.put("/api/v1/notifications/preferences", json={"email_enabled": True, "sms_enabled": True, "push_enabled": False,
                                                          "quiet_start_hour": start, "quiet_end_hour": end, "language": "ta"}, headers=RAMESH)
    title = "quiet-" + uuid.uuid4().hex[:6]
    ids = _notify(title, channels=("in_app", "sms"))
    db = SessionLocal()
    try:
        ev = db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == ids["sms"])).scalar_one()
        wait = (ev.available_at - datetime.datetime.utcnow()).total_seconds()
        assert 3600 < wait <= 3 * 3600                                     # held until quiet hours end
        ev.available_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    outbox.dispatch_pending(SessionLocal, limit=100_000)
    sent = [x for x in FakeNotificationAdapter.sent if x["title"].startswith(title)]
    assert sent and sent[-1]["title"] == title + " (ta)"                  # Tamil, as the parent prefers


def test_quiet_window_maths():
    class P:
        quiet_start_hour, quiet_end_hour = 21, 7
    at = lambda h, m=0: datetime.datetime(2026, 11, 20, h, m)
    assert quiet_delay_seconds(P(), at(22)) == 9 * 3600                    # wraps midnight
    assert quiet_delay_seconds(P(), at(6, 30)) == 1800
    assert quiet_delay_seconds(P(), at(12)) == 0
    assert quiet_delay_seconds(None, at(23)) == 0
