"""Screens 05 (trainer schedule) and 06 (college timetable): link L11.
Spec: docs/screens/05-06-schedule-and-timetable.md"""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import AuditLog, Batch, LiveMeeting, OutboxEvent, ScheduleChangeRequest, SessionItem

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


ARUN, KAVITHA, PRIYA = _h("usr_arun_01", "trainer"), _h("usr_kavitha_01", "college_admin"), _h("usr_priya_01", "student")
OTHER_ADMIN = _h("usr_kavitha_01", "college_admin", "col_other_999")
AIDS = "bat_aids_s5_aids"


def _slot(hour=6, minutes=60, days=1):
    start = (datetime.datetime.now() + datetime.timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return start, start + datetime.timedelta(minutes=minutes)


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        before = set(db.execute(select(SessionItem.id)).scalars())
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        new_sessions = set(db.execute(select(SessionItem.id)).scalars()) - before
        db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id.in_(new_sessions or {"_"})))
        db.execute(delete(LiveMeeting).where(LiveMeeting.session_id.in_(new_sessions or {"_"})))
        db.execute(delete(ScheduleChangeRequest).where(ScheduleChangeRequest.college_id == "col_demo_001"))
        db.execute(delete(SessionItem).where(SessionItem.id.in_(new_sessions or {"_"})))
        db.commit()
    finally:
        db.close()


def _propose(**body):
    return client.post("/api/v1/trainer/schedule/requests", json={"reason": "Lab practice before the mock drive", **body}, headers=ARUN)


def _new_session(title="RAG lab drill", hour=6, room="Lab 3", batch=AIDS):
    start, end = _slot(hour)
    rid = _propose(kind="new", batch_id=batch, title=title, start=start.isoformat(), end=end.isoformat(), room=room).json()["id"]
    return client.post(f"/api/v1/college/schedule-requests/{rid}/approve", headers=KAVITHA).json()["session_id"]


def test_trainer_week_shows_only_mapped_batches():
    d = client.get("/api/v1/trainer/schedule", headers=ARUN).json()
    mine = {b["id"] for b in d["my_batches"]}
    assert AIDS in mine and all(s["batch_id"] in mine for s in d["sessions"])
    assert client.get("/api/v1/trainer/schedule", headers=PRIYA).status_code == 403


def test_proposals_are_validated():
    start, end = _slot()
    assert _propose(kind="new", batch_id=AIDS, title="X", start=end.isoformat(), end=start.isoformat()).status_code == 422
    assert _propose(kind="new", batch_id=AIDS, title="X", start=start.isoformat(),
                    end=(start + datetime.timedelta(minutes=300)).isoformat()).status_code == 422
    past = datetime.datetime.now() - datetime.timedelta(days=1)
    assert _propose(kind="new", batch_id=AIDS, title="X", start=past.isoformat(), end=(past + datetime.timedelta(hours=1)).isoformat()).status_code == 422
    db = SessionLocal()
    try:
        not_mine = db.execute(select(Batch.id).where(Batch.college_id == "col_demo_001", Batch.id.not_in(
            [b["id"] for b in client.get("/api/v1/trainer/schedule", headers=ARUN).json()["my_batches"]]))).scalars().first()
    finally:
        db.close()
    assert _propose(kind="new", batch_id=not_mine, title="X", start=start.isoformat(), end=end.isoformat()).status_code == 404


@pytest.mark.link("L11")
def test_new_session_approved_reaches_the_students_week():
    sid = _new_session()
    db = SessionLocal()
    try:
        s = db.get(SessionItem, sid)
        assert (s.batch_id, s.room, s.status, s.duration_min) == (AIDS, "Lab 3", "Scheduled", 60)
    finally:
        db.close()
    start, _ = _slot()
    if start.isocalendar()[1] == datetime.date.today().isocalendar()[1]:          # 08 shows the current week
        week = client.get("/api/v1/student/live", headers=PRIYA).json()["week_sessions"]
        assert any(w["id"] == sid for w in week)
    trainer_week = client.get(f"/api/v1/trainer/schedule?week={start.date().isoformat()}", headers=ARUN).json()["sessions"]
    assert any(w["id"] == sid for w in trainer_week)


def test_clashes_are_warnings_the_college_can_override():
    first = _new_session(hour=6, room="Lab 3")
    start, end = _slot(hour=6, minutes=90)
    r = _propose(kind="new", batch_id=AIDS, title="Overlapping", start=start.isoformat(), end=end.isoformat(), room="lab 3").json()
    kinds = {c["kind"] for c in r["clashes"] if c["session_id"] == first}
    assert kinds == {"batch", "room"}
    blocked = client.post(f"/api/v1/college/schedule-requests/{r['id']}/approve", headers=KAVITHA)
    assert blocked.status_code == 409 and blocked.json()["detail"]["clashes"]
    ok = client.post(f"/api/v1/college/schedule-requests/{r['id']}/approve?override=true", headers=KAVITHA).json()
    assert ok["override"] is True
    db = SessionLocal()
    try:
        audit = db.execute(select(AuditLog).where(AuditLog.entity_id == r["id"], AuditLog.action == "schedule.change_approved")).scalar_one()
        assert audit.detail["override"] is True and audit.detail["clashes"]
    finally:
        db.close()


def test_trainer_clash_across_batches():
    first = _new_session(hour=6, room=None)
    cse_a = next(b["id"] for b in client.get("/api/v1/trainer/schedule", headers=ARUN).json()["my_batches"] if b["short_name"] == "CSE-A")
    start, end = _slot(hour=6)
    clashes = _propose(kind="new", batch_id=cse_a, title="CSE-A extra", start=start.isoformat(), end=end.isoformat()).json()["clashes"]
    assert any(c["kind"] == "trainer" and c["session_id"] == first for c in clashes)


def test_reschedule_moves_the_session_and_the_teams_event(monkeypatch):
    sid = _new_session(hour=6)
    db = SessionLocal()
    try:
        db.add(LiveMeeting(id=f"lm_{sid}"[:64], college_id="col_demo_001", session_id=sid, provider="teams", external_meeting_id=f"irep-{sid}",
                           flow_steps=[], unmatched_attendees=[], join_url="https://teams.example/j", organizer_upn="arun@irep.example",
                           graph_event_id="evt-x"))
        db.commit()
    finally:
        db.close()
    start, end = _slot(hour=7)
    rid = _propose(kind="reschedule", session_id=sid, start=start.isoformat(), end=end.isoformat()).json()["id"]
    assert client.post(f"/api/v1/college/schedule-requests/{rid}/approve", headers=KAVITHA).status_code == 200
    db = SessionLocal()
    try:
        assert db.get(SessionItem, sid).scheduled_start == start
        assert db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == sid, OutboxEvent.event_type == "teams.update_event")).first()
    finally:
        db.close()
    rid2 = _propose(kind="cancel", session_id=sid).json()["id"]
    client.post(f"/api/v1/college/schedule-requests/{rid2}/approve", headers=KAVITHA)
    db = SessionLocal()
    try:
        assert db.get(SessionItem, sid).status == "Cancelled"
        assert db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == sid, OutboxEvent.event_type == "teams.cancel_event")).first()
    finally:
        db.close()
    assert _propose(kind="cancel", session_id=sid).status_code == 409


def test_reject_needs_a_reason_and_tenancy():
    start, end = _slot(hour=6)
    rid = _propose(kind="new", batch_id=AIDS, title="Maybe", start=start.isoformat(), end=end.isoformat()).json()["id"]
    assert client.post(f"/api/v1/college/schedule-requests/{rid}/reject", json={"reason": ""}, headers=KAVITHA).status_code == 422
    assert client.post(f"/api/v1/college/schedule-requests/{rid}/approve", headers=OTHER_ADMIN).status_code == 404
    assert client.post(f"/api/v1/college/schedule-requests/{rid}/reject", json={"reason": "Lab 3 is under maintenance"}, headers=KAVITHA).json()["status"] == "rejected"
    assert client.get("/api/v1/college/timetable", headers=ARUN).status_code == 403
    tt = client.get("/api/v1/college/timetable", headers=KAVITHA).json()
    assert any(r["id"] == rid and r["status"] == "rejected" for r in tt["requests"])
