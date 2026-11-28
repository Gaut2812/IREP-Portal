"""Practice test (screen 23): a lost connection pauses the clock, measured by the server and capped; tab switches
are counted on the server and shown to the trainer."""
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
from models.schema import AttemptAnswer, PracticeQuestion, PracticeTest, ProctorEvent, TestAttempt, TopicScore, Notification
from routers.student import MAX_PAUSE_SEC, PAUSE_SLACK_SEC

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN, RAMESH = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_ramesh_01", "parent")
OTHER_STUDENT = _h("usr_cse_2_001_6c05", "student")          # a seeded student of another batch


@pytest.fixture
def attempt():
    """A fresh 30-minute test published to Priya's batch, and her attempt on it."""
    title = f"Pause test {uuid.uuid4().hex[:6]}"
    made = client.post("/api/v1/trainer/assessments/tests", headers=ARUN, json={
        "title": title, "duration_min": 30,
        "questions": [{"question_text": "What is 2 + 2?", "option_a": "3", "option_b": "4", "option_c": "5", "option_d": "6", "correct_option": "B"}]})
    tid = made.json()["id"]
    batches = [b["id"] for b in client.get("/api/v1/trainer/assessments", headers=ARUN).json()["batches"]]
    assert client.post(f"/api/v1/trainer/assessments/test/{tid}/publish", headers=ARUN, json={"batch_ids": batches}).status_code == 200
    start = client.post(f"/api/v1/student/tests/{tid}/attempts", headers=PRIYA).json()
    yield tid, start
    with SessionLocal() as db:
        ids = [a for a in db.execute(select(TestAttempt.id).where(TestAttempt.test_id == tid)).scalars()]
        db.execute(delete(ProctorEvent).where(ProctorEvent.attempt_id.in_(ids or ["_"])))
        db.execute(delete(AttemptAnswer).where(AttemptAnswer.attempt_id.in_(ids or ["_"])))
        db.execute(delete(TopicScore).where(TopicScore.attempt_id.in_(ids or ["_"])))
        db.execute(delete(TestAttempt).where(TestAttempt.test_id == tid))
        db.execute(delete(PracticeQuestion).where(PracticeQuestion.test_id == tid))
        db.execute(delete(PracticeTest).where(PracticeTest.id == tid))
        db.execute(delete(Notification).where(Notification.title_en.like(f"%{title}%")))     # the publish notified the batch
        db.commit()


def _set(att_id, **values):
    with SessionLocal() as db:
        a = db.get(TestAttempt, att_id)
        for k, v in values.items():
            setattr(a, k, v)
        db.commit()


def _get(att_id) -> TestAttempt:
    with SessionLocal() as db:
        a = db.get(TestAttempt, att_id)
        db.expunge(a)
        return a


def test_start_tells_the_page_the_rules(attempt):
    _, start = attempt
    assert start["heartbeat_sec"] == 15 and start["max_pause_sec"] == MAX_PAUSE_SEC
    assert start["max_tab_switches"] == 3 and start["tab_switches"] == 0 and start["paused_seconds"] == 0


def test_a_lost_connection_is_given_back_on_the_next_heartbeat(attempt):
    _, start = attempt
    aid, now = start["attempt_id"], datetime.datetime.utcnow()
    before = _get(aid).ends_at
    _set(aid, last_seen_at=now - datetime.timedelta(seconds=200))          # 200 s without a heartbeat
    r = client.post(f"/api/v1/student/tests/attempts/{aid}/heartbeat", headers=PRIYA).json()
    assert 200 - PAUSE_SLACK_SEC - 2 <= r["credited_sec"] <= 200 - PAUSE_SLACK_SEC
    after = _get(aid)
    assert (after.ends_at - before).total_seconds() == r["credited_sec"] and after.paused_seconds == r["credited_sec"]
    with SessionLocal() as db:                                               # the trainer can see it happened
        assert db.execute(select(ProctorEvent).where(ProctorEvent.attempt_id == aid, ProctorEvent.event_type == "connection_paused")).first()
    again = client.post(f"/api/v1/student/tests/attempts/{aid}/heartbeat", headers=PRIYA).json()
    assert again["credited_sec"] == 0                                        # an on-time heartbeat adds nothing


def test_normal_heartbeat_jitter_is_not_a_pause(attempt):
    _, start = attempt
    aid = start["attempt_id"]
    _set(aid, last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=PAUSE_SLACK_SEC - 5))
    assert client.post(f"/api/v1/student/tests/attempts/{aid}/heartbeat", headers=PRIYA).json()["credited_sec"] == 0


def test_pause_is_capped_per_attempt(attempt):
    _, start = attempt
    aid = start["attempt_id"]
    _set(aid, last_seen_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=900), paused_seconds=MAX_PAUSE_SEC - 20)
    r = client.post(f"/api/v1/student/tests/attempts/{aid}/heartbeat", headers=PRIYA).json()
    assert r["credited_sec"] == 20 and r["paused_seconds"] == MAX_PAUSE_SEC


def test_reopening_after_the_old_end_resumes_the_same_attempt_with_its_answers(attempt):
    tid, start = attempt
    aid, now = start["attempt_id"], datetime.datetime.utcnow()
    assert client.put(f"/api/v1/student/tests/attempts/{aid}/answers", headers=PRIYA, json={"answers": {"1": "B"}, "marked_for_review": []}).status_code == 200
    # offline from 4 minutes before the end until 1 minute after it: the 4 minutes before the end come back
    _set(aid, ends_at=now - datetime.timedelta(minutes=1), last_seen_at=now - datetime.timedelta(minutes=5))
    again = client.post(f"/api/v1/student/tests/{tid}/attempts", headers=PRIYA).json()
    assert again["attempt_id"] == aid and again["resumed"] is True             # it used to start a new attempt
    assert again["saved_answers"] == {"1": "B"} and again["time_remaining_sec"] > 60


def test_tab_switches_are_counted_on_the_server_and_shown_to_the_trainer(attempt):
    tid, start = attempt
    aid = start["attempt_id"]
    for n in (1, 2):
        r = client.post(f"/api/v1/student/tests/attempts/{aid}/proctor-events", headers=PRIYA, json={"event_type": "tab_switch", "details": "left"}).json()
        assert r["tab_switches"] == n and r["max_tab_switches"] == 3
    assert client.post(f"/api/v1/student/tests/{tid}/attempts", headers=PRIYA).json()["tab_switches"] == 2   # survives a reload
    client.post(f"/api/v1/student/tests/attempts/{aid}/submit", headers=PRIYA, json={"answers": {"1": "B"}, "marked_for_review": []})
    rows = client.get(f"/api/v1/trainer/assessments/test/{tid}/results", headers=ARUN).json()["students"]
    priya = next(r for r in rows if r["student_id"] == "std_priya_01")
    assert priya["tab_switches"] == 2 and priya["paused_min"] == 0


def test_heartbeat_guards(attempt):
    _, start = attempt
    aid = start["attempt_id"]
    assert client.post(f"/api/v1/student/tests/attempts/{aid}/heartbeat", headers=RAMESH).status_code == 403
    assert client.post(f"/api/v1/student/tests/attempts/{aid}/heartbeat", headers=OTHER_STUDENT).status_code == 404   # not theirs
    assert client.post(f"/api/v1/student/tests/attempts/{aid}/heartbeat", headers=_h("usr_priya_01", "student", "col_other_999")).status_code == 404
