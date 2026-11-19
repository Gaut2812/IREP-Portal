"""Screen 07 Live Classroom: 75% rule incl. rejoin gaps, join/leave, poll uniqueness,
trainer-only controls, signed BBB webhook, finalize attendance, tenant/role guards."""
import datetime
import json
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import (
    LiveMeeting, JoinEvent, LivePollVote, LivePoll, QaQuestion, QaUpvote, SessionItem, SessionAttendance, User, Student,
)
from services.live_class import presence_intervals, covered_minutes, webhook_signature, BBBAdapter

client = TestClient(app)
T0 = datetime.datetime(2026, 11, 19, 11, 0)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Priya R"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


PRIYA = _token("usr_priya_01", "student")
ARUN = _token("usr_arun_01", "trainer", name="Arun Kumar")
SESSION = "sess_thu_rag"


def m(minutes: float) -> datetime.datetime:
    return T0 + datetime.timedelta(minutes=minutes)


# ---- 75% rule ------------------------------------------------------------

def test_presence_single_stay():
    iv = presence_intervals([("joined", m(0)), ("left", m(50))], until=m(60))
    assert covered_minutes(iv, m(0), m(60)) == pytest.approx(50)


def test_presence_rejoin_gaps_add_up():
    events = [("joined", m(-2)), ("left", m(20)), ("joined", m(25)), ("left", m(40)), ("joined", m(42))]
    iv = presence_intervals(events, until=m(60))
    # clipped to the window: 20 + 15 + 18 = 53 minutes
    assert covered_minutes(iv, m(0), m(60)) == pytest.approx(53)
    assert covered_minutes(iv, m(0), m(60)) >= 45


def test_presence_just_below_threshold():
    events = [("joined", m(0)), ("left", m(30)), ("joined", m(40)), ("left", m(54))]
    assert covered_minutes(presence_intervals(events, m(60)), m(0), m(60)) == pytest.approx(44)


def test_duplicate_joins_and_orphan_leaves_are_not_double_counted():
    events = [("left", m(-5)), ("joined", m(0)), ("joined", m(10)), ("left", m(30)), ("left", m(31))]
    iv = presence_intervals(events, until=m(60))
    assert covered_minutes(iv, m(0), m(60)) == pytest.approx(30)


def test_overlapping_intervals_union():
    iv = [(m(0), m(30)), (m(20), m(50))]
    assert covered_minutes(iv, m(0), m(60)) == pytest.approx(50)


# ---- room flow -----------------------------------------------------------

@pytest.fixture
def fresh_room():
    db = SessionLocal()
    try:
        db.execute(delete(JoinEvent).where(JoinEvent.session_id == SESSION))
        meeting = db.execute(select(LiveMeeting).filter_by(session_id=SESSION)).scalar_one()
        meeting.started_at = None
        meeting.ended_at = None
        meeting.finalized = False
        poll = db.execute(select(LivePoll).filter_by(id="poll_rag_notes")).scalar_one()
        poll.is_open = True
        db.execute(delete(LivePoll).where(LivePoll.session_id == SESSION, LivePoll.id != "poll_rag_notes"))
        db.execute(delete(LivePollVote).where(LivePollVote.user_id == "usr_priya_01"))
        s = db.execute(select(SessionItem).filter_by(id=SESSION)).scalar_one()
        original = (s.scheduled_start, s.scheduled_end)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.execute(delete(JoinEvent).where(JoinEvent.session_id == SESSION))
        meeting = db.execute(select(LiveMeeting).filter_by(session_id=SESSION)).scalar_one()
        meeting.started_at = None
        meeting.ended_at = None
        meeting.finalized = False
        db.execute(delete(SessionAttendance).where(SessionAttendance.session_id == SESSION))
        seeded = ["qa_topk", "qa_college_notes", "qa_chunk_size"]
        extra = db.execute(select(QaQuestion.id).where(QaQuestion.session_id == SESSION, QaQuestion.id.notin_(seeded))).scalars().all()
        db.execute(delete(QaUpvote).where(QaUpvote.question_id.in_(extra or ["_"])))
        db.execute(delete(QaQuestion).where(QaQuestion.id.in_(extra or ["_"])))
        db.execute(delete(LivePollVote).where(LivePollVote.poll_id == "poll_rag_notes", LivePollVote.user_id.in_(["usr_priya_01", "usr_arun_01"])))
        s = db.execute(select(SessionItem).filter_by(id=SESSION)).scalar_one()
        s.scheduled_start, s.scheduled_end = original
        db.commit()
    finally:
        db.close()


def test_student_cannot_enter_before_trainer_or_window(fresh_room):
    state = client.get(f"/api/v1/live/{SESSION}", headers=PRIYA).json()
    if not state["schedule"]["join_window_open"]:
        assert state["meeting"]["state"] == "not_started" and state["can_join"] is False
        assert client.post(f"/api/v1/sessions/{SESSION}/join", headers=PRIYA).status_code == 409


@pytest.mark.link("L04")
def test_full_class_flow(fresh_room):
    # trainer opens the room
    r = client.post(f"/api/v1/sessions/{SESSION}/join", headers=ARUN)
    assert r.status_code == 200 and r.json()["meeting_state"] == "live" and r.json()["join_url"] is None
    # student joins, sees the stage, poll and Q&A
    assert client.post(f"/api/v1/sessions/{SESSION}/join", headers=PRIYA).status_code == 200
    st = client.get(f"/api/v1/live/{SESSION}", headers=PRIYA).json()
    assert st["meeting"]["state"] == "live" and st["meeting"]["is_recording"] is True
    assert st["stage"]["file"] == "rag_demo.ipynb" and len(st["stage"]["flow_steps"]) == 4
    assert {p["name"] for p in st["participants"]} >= {"Arun Kumar", "Priya R"}
    assert st["poll"]["total_votes"] == 30 and st["poll"]["my_vote"] is None
    assert st["qa"][0]["text"] == "How do we choose top_k?" and st["qa"][0]["answered_at"] == "31:40"
    assert st["attendance"]["threshold_minutes"] == 45 and st["attendance"]["is_in_room"] is True

    # poll: one vote per user
    assert client.post(f"/api/v1/live/{SESSION}/poll/vote", json={"option": "b"}, headers=PRIYA).status_code == 200
    assert client.post(f"/api/v1/live/{SESSION}/poll/vote", json={"option": "a"}, headers=PRIYA).status_code == 409
    assert client.post(f"/api/v1/live/{SESSION}/poll/vote", json={"option": "z"}, headers=ARUN).status_code == 422
    st = client.get(f"/api/v1/live/{SESSION}", headers=PRIYA).json()
    assert st["poll"]["total_votes"] == 31 and st["poll"]["my_vote"] == "b"
    assert [o["pct"] for o in st["poll"]["options"]] == [6, 87, 6]

    # Q&A: ask, upvote toggle, trainer-only answered
    q = client.post(f"/api/v1/live/{SESSION}/qa", json={"text": "Does temperature change grounding?"}, headers=PRIYA).json()["question_id"]
    assert client.post(f"/api/v1/live/{SESSION}/qa/{q}/upvote", headers=ARUN).json()["upvotes"] == 1
    assert client.post(f"/api/v1/live/{SESSION}/qa/{q}/upvote", headers=ARUN).json()["upvotes"] == 0
    assert client.post(f"/api/v1/live/{SESSION}/qa/{q}/answered", headers=PRIYA).status_code == 403
    assert client.post(f"/api/v1/live/{SESSION}/qa/{q}/answered", headers=ARUN).status_code == 200
    assert client.post(f"/api/v1/live/{SESSION}/qa", json={"text": "you are stupid"}, headers=PRIYA).status_code == 422

    # trainer-only: new poll and end
    assert client.post(f"/api/v1/live/{SESSION}/polls", json={"question": "Ready?", "options": ["Yes", "No"]}, headers=PRIYA).status_code == 403
    assert client.post(f"/api/v1/sessions/{SESSION}/end", headers=PRIYA).status_code == 403

    # leave + end: attendance finalized for the whole batch
    assert client.post(f"/api/v1/sessions/{SESSION}/leave", headers=PRIYA).status_code == 200
    end = client.post(f"/api/v1/sessions/{SESSION}/end", headers=ARUN)
    assert end.status_code == 200
    summary = end.json()["attendance"]
    db = SessionLocal()
    try:
        batch_size = db.execute(select(Student).filter_by(batch_id="bat_aids_s5_aids")).scalars().all()
        assert summary["present"] + summary["absent"] == len(batch_size)
        priya_row = db.execute(select(SessionAttendance).filter_by(session_id=SESSION, student_id="std_priya_01")).scalar_one()
        assert priya_row.source == "auto" and priya_row.status == "Absent"   # only seconds in the room
    finally:
        db.close()
    assert client.post(f"/api/v1/sessions/{SESSION}/join", headers=PRIYA).status_code == 409


def test_bbb_webhook_signed_events_mark_present(fresh_room):
    db = SessionLocal()
    try:
        s = db.execute(select(SessionItem).filter_by(id=SESSION)).scalar_one()
        start = s.scheduled_start
    finally:
        db.close()

    def post(event: dict):
        body = json.dumps(event).encode()
        return client.post("/api/v1/webhooks/bbb", content=body, headers={"X-BBB-Signature": webhook_signature(body), "Content-Type": "application/json"})

    bad = json.dumps({"event": "user-joined", "meeting_id": f"irep-{SESSION}", "user_id": "usr_priya_01"}).encode()
    assert client.post("/api/v1/webhooks/bbb", content=bad, headers={"X-BBB-Signature": "nope"}).status_code == 401

    at = lambda mins: (start + datetime.timedelta(minutes=mins)).isoformat()
    assert post({"event": "user-joined", "meeting_id": f"irep-{SESSION}", "user_id": "usr_priya_01", "at": at(0)}).status_code == 200
    post({"event": "user-left", "meeting_id": f"irep-{SESSION}", "user_id": "usr_priya_01", "at": at(30)})
    post({"event": "user-joined", "meeting_id": f"irep-{SESSION}", "user_id": "usr_priya_01", "at": at(33)})
    post({"event": "user-left", "meeting_id": f"irep-{SESSION}", "user_id": "usr_priya_01", "at": at(55)})
    assert post({"event": "meeting-ended", "meeting_id": f"irep-{SESSION}", "at": at(60)}).status_code == 200
    db = SessionLocal()
    try:
        row = db.execute(select(SessionAttendance).filter_by(session_id=SESSION, student_id="std_priya_01")).scalar_one()
        assert row.status == "Present" and row.minutes_present == 52
    finally:
        db.close()


def test_bbb_join_url_is_signed():
    url = BBBAdapter("https://bbb.example/bigbluebutton", "s3cret").join_url("irep-x", "u1", "Priya R", "student")
    assert url.startswith("https://bbb.example/bigbluebutton/api/join?") and "checksum=" in url and "role=VIEWER" in url


def test_guards():
    db = SessionLocal()
    try:
        karthik = db.execute(select(User).filter_by(name="Karthik S")).scalars().first()
    finally:
        db.close()
    assert client.get(f"/api/v1/live/{SESSION}", headers=_token(karthik.id, "student", name="Karthik S")).status_code == 404
    assert client.get(f"/api/v1/live/{SESSION}", headers=_token("usr_meena_01", "trainer", name="Meena S")).status_code == 404
    assert client.get(f"/api/v1/live/{SESSION}", headers=_token("usr_ramesh_01", "parent")).status_code == 403
    assert client.get(f"/api/v1/live/{SESSION}", headers=_token("usr_priya_01", "student", college_id="col_other_999")).status_code == 404
