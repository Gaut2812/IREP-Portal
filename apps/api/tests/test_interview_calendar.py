"""Mock interview booking calendar (screen 36), Phase 2: all open slots of the next weeks, and a slot you cannot
book says why (one upcoming round of each type)."""
import datetime
import sys
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
from models.schema import Interview, InterviewBooking, InterviewSlot, Notification
from services.interviews import SLOT_WINDOW_DAYS

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer")


@pytest.fixture
def slots():
    """Two technical slots 20 and 21 days out (past the seeded ones), and one 50 days out (beyond the window)."""
    base = datetime.datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)
    started = datetime.datetime.utcnow()
    made = []
    for days in (20, 21, SLOT_WINDOW_DAYS + 15):
        r = client.post("/api/v1/trainer/interview-slots", headers=ARUN, json={
            "starts_at": (base + datetime.timedelta(days=days)).isoformat(), "round_type": "technical", "duration_min": 30, "batch_id": "bat_aids_s5_aids"})
        made.append(r.json()["slot_id"])
    yield made
    with SessionLocal() as db:
        # booking -> interview -> slot (each points at the next)
        db.execute(delete(InterviewBooking).where(InterviewBooking.slot_id.in_(made)))
        db.execute(delete(Interview).where(Interview.slot_id.in_(made)))
        db.execute(delete(InterviewSlot).where(InterviewSlot.id.in_(made)))
        # only the notifications this test's booking sent (to Priya and to Arun)
        db.execute(delete(Notification).where(Notification.created_at >= started, Notification.user_id.in_(["usr_priya_01", "usr_arun_01"]),
                                              (Notification.title_en == "Mock interview booked") | Notification.title_en.like("Interview booked by %")))
        db.commit()


def _available():
    return {s["id"]: s for s in client.get("/api/v1/student/interviews", headers=PRIYA).json()["available_slots"]}


def test_the_calendar_lists_every_open_slot_in_the_window(slots):
    near, nearer, far = slots
    avail = _available()
    assert near in avail and nearer in avail and far not in avail
    assert avail[near]["duration_min"] == 30 and avail[near]["starts_at"]


def test_after_booking_a_technical_round_other_technical_slots_say_why_not(slots):
    near, nearer, _ = slots
    with SessionLocal() as db:   # Priya must not already hold an upcoming technical booking for this test
        held = db.execute(select(InterviewBooking.id).join(InterviewSlot, InterviewSlot.id == InterviewBooking.slot_id)
                          .where(InterviewBooking.student_id == "std_priya_01", InterviewSlot.round_type == "technical",
                                 InterviewSlot.starts_at > datetime.datetime.now())).first()
    if held:
        pytest.skip("demo state: Priya already holds a technical booking")
    assert _available()[nearer]["blocked_reason"] is None
    assert client.post(f"/api/v1/student/interview-slots/{near}/book", headers=PRIYA).status_code == 200
    avail = _available()
    assert near not in avail                                                     # booked: gone from the calendar
    assert "already have an upcoming Technical" in avail[nearer]["blocked_reason"]
    r = client.post(f"/api/v1/student/interview-slots/{nearer}/book", headers=PRIYA)
    assert r.status_code == 409 and "already have an upcoming round" in r.json()["detail"]
    ta = {s["id"]: s for s in client.get("/api/v1/student/interviews?lang=ta", headers=PRIYA).json()["available_slots"]}
    assert "பதிவு செய்துள்ளீர்கள்" in ta[nearer]["blocked_reason"]
