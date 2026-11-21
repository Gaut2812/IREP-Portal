"""Screen 09 · Attendance (trainer) + student check-in. Spec: docs/screens/09-trainer-attendance.md"""
import datetime
import sys
import time
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
from models.schema import AuditLog, JoinEvent, LiveMeeting, SessionAttendance, SessionItem
from routers.attendance import _code, _window
from services.live_class import finalize_session

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


ARUN, PRIYA, KAVITHA = _h("usr_arun_01", "trainer", ), _h("usr_priya_01", "student"), _h("usr_kavitha_01", "college_admin")
AIDS = "bat_aids_s5_aids"


@pytest.fixture
def session_factory():
    made = []

    def make(start_offset_min: int, minutes: int = 60, batch: str = AIDS, stype: str = "In-lab / Hybrid"):
        sid = f"sess_att_{uuid.uuid4().hex[:10]}"
        start = datetime.datetime.now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=start_offset_min)
        db = SessionLocal()
        try:
            db.add(SessionItem(id=sid, college_id="col_demo_001", title="Attendance IT", track="AI & DS", trainer_name="Arun Kumar",
                               scheduled_start=start, scheduled_end=start + datetime.timedelta(minutes=minutes), duration_min=minutes,
                               session_type=stype, status="Scheduled", batch_id=batch))
            db.commit()
        finally:
            db.close()
        made.append(sid)
        return sid, start
    yield make
    db = SessionLocal()
    try:
        for model in (JoinEvent, SessionAttendance, LiveMeeting):
            db.execute(delete(model).where(model.session_id.in_(made or ["_"])))
        db.execute(delete(SessionItem).where(SessionItem.id.in_(made or ["_"])))
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L06")
def test_class_ended_on_07_shows_75_percent_rule_on_09(session_factory):
    sid, start = session_factory(start_offset_min=-60)
    assert client.post(f"/api/v1/sessions/{sid}/join", headers=ARUN).status_code == 200       # 07: trainer opens the room
    db = SessionLocal()
    try:   # Priya was in class 0-30 and 35-55 (50 of 60 minutes); nobody else joined
        for ev, m in (("joined", 0), ("left", 30), ("joined", 35), ("left", 55)):
            db.add(JoinEvent(id=f"je_{uuid.uuid4().hex[:16]}", college_id="col_demo_001", session_id=sid, user_id="usr_priya_01",
                             event=ev, at=start + datetime.timedelta(minutes=m), source="portal"))
        db.commit()
    finally:
        db.close()
    end = client.post(f"/api/v1/sessions/{sid}/end", headers=ARUN).json()                   # 07: class ends -> 75% rule
    assert end["attendance"]["present"] == 1
    roster = client.get(f"/api/v1/trainer/attendance/{sid}", headers=ARUN).json()
    priya = next(r for r in roster["roster"] if r["student_id"] == "std_priya_01")
    assert (priya["status"], priya["minutes_present"], priya["source"]) == ("Present", 50, "auto")
    assert roster["session"]["present"] == 1 and roster["session"]["absent"] == roster["session"]["students"] - 1
    listed = client.get("/api/v1/trainer/attendance/sessions", headers=ARUN).json()["sessions"]
    assert any(s["id"] == sid and s["past"] for s in listed)


def test_override_needs_a_reason_is_audited_and_survives_refinalising(session_factory):
    sid, start = session_factory(start_offset_min=-90)
    db = SessionLocal()
    try:
        finalize_session(db, db.get(SessionItem, sid), None, datetime.datetime.now())
        db.commit()
    finally:
        db.close()
    assert client.post(f"/api/v1/trainer/attendance/{sid}/override", json={"student_id": "std_priya_01", "status": "Present", "reason": "ok"},
                       headers=ARUN).status_code == 422
    r = client.post(f"/api/v1/trainer/attendance/{sid}/override", json={"student_id": "std_priya_01", "status": "Present",
                                                                        "reason": "Was in the lab; laptop could not join"}, headers=ARUN)
    assert r.json() == {"student_id": "std_priya_01", "status": "Present", "source": "manual"}
    db = SessionLocal()
    try:
        finalize_session(db, db.get(SessionItem, sid), None, datetime.datetime.now())       # an automatic re-run
        db.commit()
        row = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == sid, SessionAttendance.student_id == "std_priya_01")).scalar_one()
        assert (row.status, row.source, row.overridden_by) == ("Present", "manual", "trn_arun_01")
        audit = db.execute(select(AuditLog).where(AuditLog.entity_id == sid, AuditLog.action == "attendance.overridden")).scalar_one()
        assert audit.detail["from"] == "Absent" and audit.detail["to"] == "Present"
    finally:
        db.close()
    assert client.post(f"/api/v1/trainer/attendance/{sid}/override", json={"student_id": "std_cse_x", "status": "Absent",
                                                                          "reason": "Not in this batch"}, headers=ARUN).status_code == 404


def test_checkin_code_only_in_window_and_own_batch(session_factory):
    live, _ = session_factory(start_offset_min=-10)
    later, _ = session_factory(start_offset_min=180)
    code = client.get(f"/api/v1/trainer/attendance/{live}/checkin-code", headers=ARUN).json()["code"]
    assert len(code) == 6
    assert client.get(f"/api/v1/trainer/attendance/{later}/checkin-code", headers=ARUN).status_code == 409
    assert client.post("/api/v1/student/attendance/checkin", json={"code": "ZZZZZZ"}, headers=PRIYA).status_code == 422
    ok = client.post("/api/v1/student/attendance/checkin", json={"code": code.lower()}, headers=PRIYA).json()
    assert ok["checked_in"] is True and ok["session_id"] == live
    assert client.post("/api/v1/student/attendance/checkin", json={"code": code}, headers=PRIYA).json()["already"] is True
    # a student of another batch cannot use this class's code
    other = _h("usr_cse_5_001_x", "student")
    db = SessionLocal()
    try:
        from models.schema import Student
        outsider = db.execute(select(Student).where(Student.college_id == "col_demo_001", Student.batch_id != AIDS)).scalars().first()
        other = _h(outsider.user_id, "student")
    finally:
        db.close()
    assert client.post("/api/v1/student/attendance/checkin", json={"code": code}, headers=other).status_code == 422
    # last minute's code is still accepted; an old one is not
    assert _code(live, _window() - 5) != code


def test_checkin_never_overrides_a_manual_absent(session_factory):
    live, _ = session_factory(start_offset_min=-5)
    client.post(f"/api/v1/trainer/attendance/{live}/override", json={"student_id": "std_priya_01", "status": "Absent",
                                                                     "reason": "Left after roll call"}, headers=ARUN)
    code = client.get(f"/api/v1/trainer/attendance/{live}/checkin-code", headers=ARUN).json()["code"]
    r = client.post("/api/v1/student/attendance/checkin", json={"code": code}, headers=PRIYA).json()
    assert r["checked_in"] is False and r["status"] == "Absent"


def test_roles_and_other_trainers(session_factory):
    sid, _ = session_factory(start_offset_min=-30)
    for h in (PRIYA, KAVITHA):
        assert client.get(f"/api/v1/trainer/attendance/{sid}", headers=h).status_code == 403
    assert client.post("/api/v1/student/attendance/checkin", json={"code": "ABCDEF"}, headers=ARUN).status_code == 403
    db = SessionLocal()
    try:
        from models.schema import Trainer
        other = db.execute(select(Trainer).where(Trainer.college_id == "col_demo_001", Trainer.id != "trn_arun_01")).scalars().first()
        # make sure that trainer is not mapped to AI&DS
        from models.schema import BatchTrainer
        mapped = db.execute(select(BatchTrainer).where(BatchTrainer.trainer_id == other.id, BatchTrainer.batch_id == AIDS)).first()
        other_h = _h(other.user_id, "trainer")
    finally:
        db.close()
    if not mapped:
        assert client.get(f"/api/v1/trainer/attendance/{sid}", headers=other_h).status_code == 404
