"""Live sessions, Phase 2: a class's status comes from the clock, the meeting and attendance (a class the trainer
ended early is over, and cannot be joined); the trainer's live classroom hub lists live, upcoming and past classes."""
import datetime
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import LiveMeeting, SessionItem
from services.live_sessions import session_status

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


ARUN, PRIYA = _h("usr_arun_01", "trainer"), _h("usr_priya_01", "student")
NOW = datetime.datetime(2026, 11, 28, 11, 0)


def _s(start_h, end_h, status="Scheduled"):
    return SimpleNamespace(status=status, scheduled_start=NOW.replace(hour=start_h), scheduled_end=NOW.replace(hour=end_h))


def test_status_comes_from_the_clock_meeting_and_attendance():
    att = lambda st: SimpleNamespace(status=st)
    assert session_status(_s(10, 12), None, NOW) == "Live"
    assert session_status(_s(10, 12), None, NOW, meeting_ended=True) == "Completed"        # ended early: over
    assert session_status(_s(10, 12), att("Present"), NOW, meeting_ended=True) == "Attended"
    assert session_status(_s(8, 9), att("Excused"), NOW) == "Excused"
    assert session_status(_s(8, 9), att("Absent"), NOW) == "Missed"
    assert session_status(_s(8, 9, "Upcoming"), None, NOW) == "Completed"                    # a stale stored value is ignored
    assert session_status(_s(14, 15, "Cancelled"), None, NOW) == "Cancelled"


@pytest.fixture
def classes():
    """One class live now (started), one ended early, one later today, for Priya's batch."""
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    ids = {k: f"sess_t_{k}_{uuid.uuid4().hex[:6]}" for k in ("live", "ended", "later")}
    with SessionLocal() as db:
        for k, (a, b) in {"live": (-20, 40), "ended": (-30, 30), "later": (120, 180)}.items():
            db.add(SessionItem(id=ids[k], college_id="col_demo_001", title=f"Hub test {k}", batch_id="bat_aids_s5_aids", trainer_name="Arun Kumar",
                               scheduled_start=now + datetime.timedelta(minutes=a), scheduled_end=now + datetime.timedelta(minutes=b),
                               duration_min=b - a, session_type="Live", status="Scheduled"))
        db.flush()
        db.add(LiveMeeting(id=f"lm_{ids['live']}", college_id="col_demo_001", session_id=ids["live"], started_at=now - datetime.timedelta(minutes=15)))
        db.add(LiveMeeting(id=f"lm_{ids['ended']}", college_id="col_demo_001", session_id=ids["ended"],
                           started_at=now - datetime.timedelta(minutes=30), ended_at=now - datetime.timedelta(minutes=5)))
        db.commit()
    yield ids
    with SessionLocal() as db:
        db.execute(delete(LiveMeeting).where(LiveMeeting.session_id.in_(list(ids.values()))))
        db.execute(delete(SessionItem).where(SessionItem.id.in_(list(ids.values()))))
        db.commit()


def test_trainer_hub_lists_live_upcoming_and_past(classes):
    hub = client.get("/api/v1/trainer/live/sessions", headers=ARUN).json()
    assert classes["live"] in [r["id"] for r in hub["live"]]
    assert classes["later"] in [r["id"] for r in hub["upcoming"]]
    ended = next(r for r in hub["past"] if r["id"] == classes["ended"])
    assert ended["state"] == "ended"
    assert client.get("/api/v1/trainer/live/sessions", headers=PRIYA).status_code == 403
    other = client.get("/api/v1/trainer/live/sessions", headers=_h("usr_arun_01", "trainer", "col_other_999"))
    assert other.status_code in (404, 200) and (other.status_code == 404 or not other.json()["live"])


def test_a_class_ended_early_is_over_for_students(classes):
    week = client.get("/api/v1/student/live", headers=PRIYA)
    assert week.status_code == 200
    rows = {r["id"]: r for r in week.json()["week_sessions"]}
    if classes["ended"] not in rows:
        pytest.skip("the test classes fall outside the week shown")
    assert rows[classes["ended"]]["status"] in ("Completed", "Attended", "Missed")
    assert rows[classes["ended"]]["join_enabled"] is False and rows[classes["ended"]]["action"] != "join"
    assert rows[classes["live"]]["status"] == "Live" and rows[classes["live"]]["action"] == "join"
