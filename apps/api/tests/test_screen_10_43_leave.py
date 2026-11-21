"""Screens 10 (parent attendance) and 43 (approvals): links L07, L08, L09.
Spec: docs/screens/10-43-parent-attendance-and-approvals.md"""
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
from models.schema import AuditLog, LeaveRequest, Notification, SessionAttendance, SessionItem
from services.live_class import finalize_session

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


RAMESH, LAKSHMI, ARUN = _h("usr_ramesh_01", "parent"), _h("usr_lakshmi_01", "parent"), _h("usr_arun_01", "trainer")
PRIYA, KAVITHA = _h("usr_priya_01", "student"), _h("usr_kavitha_01", "college_admin")
AIDS = "bat_aids_s5_aids"
YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)


@pytest.fixture
def week():
    """Yesterday: Priya absent at 06:00, present at 07:00, and a class at 05:00 nobody marked."""
    made = []
    db = SessionLocal()
    try:
        # snapshot Priya's real (seeded) attendance in the leave range so the test leaves the demo as it was
        lo = datetime.datetime.combine(YESTERDAY, datetime.time.min)
        hi = datetime.datetime.combine(datetime.date.today() + datetime.timedelta(days=1), datetime.time.min)
        real = list(db.execute(select(SessionItem.id).where(SessionItem.batch_id == AIDS, SessionItem.scheduled_start >= lo,
                                                            SessionItem.scheduled_start < hi)).scalars())
        snapshot = {a.session_id: (a.status, a.source, a.minutes_present) for a in db.execute(
            select(SessionAttendance).where(SessionAttendance.student_id == "std_priya_01", SessionAttendance.session_id.in_(real or ["_"]))).scalars()}
        for hour, priya_status in ((6, "Absent"), (7, "Present"), (5, None)):
            sid = f"sess_lv_{uuid.uuid4().hex[:10]}"
            start = datetime.datetime.combine(YESTERDAY, datetime.time(hour, 0))
            db.add(SessionItem(id=sid, college_id="col_demo_001", title=f"Leave IT {hour}", track="AI & DS", trainer_name="Arun Kumar",
                               scheduled_start=start, scheduled_end=start + datetime.timedelta(minutes=50), duration_min=50,
                               session_type="Live", status="Scheduled", batch_id=AIDS))
            db.flush()
            if priya_status:
                db.add(SessionAttendance(id=f"att_{sid}_std_priya_01"[:64], college_id="col_demo_001", session_id=sid, student_id="std_priya_01",
                                         minutes_present=50 if priya_status == "Present" else 0, status=priya_status, source="auto"))
            made.append(sid)
        db.execute(delete(LeaveRequest).where(LeaveRequest.student_id == "std_priya_01"))
        db.commit()
    finally:
        db.close()
    yield {"absent": made[0], "present": made[1], "unmarked": made[2]}
    db = SessionLocal()
    try:
        db.execute(delete(SessionAttendance).where(SessionAttendance.session_id.in_(made)))
        db.execute(delete(SessionItem).where(SessionItem.id.in_(made)))
        for a in db.execute(select(SessionAttendance).where(SessionAttendance.student_id == "std_priya_01",
                                                            SessionAttendance.session_id.in_(real or ["_"]))).scalars():
            if a.session_id in snapshot:
                a.status, a.source, a.minutes_present = snapshot[a.session_id]
            else:
                db.delete(a)
        db.execute(delete(LeaveRequest).where(LeaveRequest.student_id == "std_priya_01"))
        db.commit()
    finally:
        db.close()


def _status(sid):
    db = SessionLocal()
    try:
        row = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == sid, SessionAttendance.student_id == "std_priya_01")).scalar_one_or_none()
        return (row.status, row.source) if row else None
    finally:
        db.close()


def _request(**over):
    body = {"start_date": YESTERDAY.isoformat(), "end_date": datetime.date.today().isoformat(), "reason": "Fever; doctor's note attached", **over}
    return client.post("/api/v1/parent/leave-requests", json=body, headers=RAMESH)


@pytest.mark.link("L09")
def test_leave_request_reaches_the_trainer_and_changes_nothing_until_approved(week):
    r = _request()
    assert r.status_code == 201 and r.json()["status"] == "pending"
    queue = client.get("/api/v1/trainer/approvals", headers=ARUN).json()["items"]
    item = next(i for i in queue if i["type"] == "leave" and i["id"] == r.json()["id"])
    assert item["student_name"] == "Priya R" and item["detail"]["requested_by"] == "Mr. Ramesh K"
    assert _status(week["absent"]) == ("Absent", "auto")                 # release rule: nothing yet
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_arun_01", Notification.link == "/trainer/approvals")).first()
    finally:
        db.close()


@pytest.mark.link("L07")
def test_approval_excuses_absences_and_the_parent_sees_it(week):
    lid = _request().json()["id"]
    d = client.post(f"/api/v1/trainer/approvals/leave/{lid}", json={"decision": "approve"}, headers=ARUN).json()
    assert d["status"] == "approved" and d["excused"] >= 2 and d["kept"] >= 1     # plus any real class in the range
    assert _status(week["absent"]) == ("Excused", "leave")
    assert _status(week["unmarked"]) == ("Excused", "leave")
    assert _status(week["present"]) == ("Present", "auto")               # presence is never overwritten
    month = client.get(f"/api/v1/parent/attendance?month={YESTERDAY.strftime('%Y-%m')}", headers=RAMESH).json()
    mine = {s["session_id"]: s["status"] for s in month["sessions"]}
    assert mine[week["absent"]] == "Excused" and mine[week["present"]] == "Present"
    assert month["leave_requests"][0]["status"] == "approved"
    roster = client.get(f"/api/v1/trainer/attendance/{week['absent']}", headers=ARUN).json()["roster"]
    assert next(r for r in roster if r["student_id"] == "std_priya_01")["status"] == "Excused"     # 09 sees it too
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_ramesh_01", Notification.title_en.like("Leave approved%"))).first()
        assert db.execute(select(AuditLog).where(AuditLog.entity_id == lid, AuditLog.action == "leave.approved")).first()
    finally:
        db.close()


def test_a_class_finalized_later_in_the_leave_is_excused(week):
    lid = _request(start_date=datetime.date.today().isoformat()).json()["id"]
    client.post(f"/api/v1/trainer/approvals/leave/{lid}", json={"decision": "approve"}, headers=ARUN)
    db = SessionLocal()
    try:
        sid = f"sess_lv_{uuid.uuid4().hex[:10]}"
        start = datetime.datetime.now().replace(second=0, microsecond=0) - datetime.timedelta(minutes=70)
        if start.date() != datetime.date.today():
            pytest.skip("just after midnight")
        s = SessionItem(id=sid, college_id="col_demo_001", title="Later class", track="AI & DS", trainer_name="Arun Kumar",
                        scheduled_start=start, scheduled_end=start + datetime.timedelta(minutes=60), duration_min=60,
                        session_type="Live", status="Scheduled", batch_id=AIDS)
        db.add(s)
        db.flush()
        summary = finalize_session(db, s, None, datetime.datetime.now())
        db.commit()
        assert summary["excused"] == 1
        row = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == sid, SessionAttendance.student_id == "std_priya_01")).scalar_one()
        assert (row.status, row.source) == ("Excused", "leave")
    finally:
        db.execute(delete(SessionAttendance).where(SessionAttendance.session_id == sid))
        db.execute(delete(SessionItem).where(SessionItem.id == sid))
        db.commit()
        db.close()


def test_denial_needs_a_note_and_changes_nothing(week):
    lid = _request().json()["id"]
    assert client.post(f"/api/v1/trainer/approvals/leave/{lid}", json={"decision": "deny"}, headers=ARUN).status_code == 422
    d = client.post(f"/api/v1/trainer/approvals/leave/{lid}", json={"decision": "deny", "note": "Please send the medical note"}, headers=ARUN)
    assert d.json()["status"] == "denied"
    assert _status(week["absent"]) == ("Absent", "auto")
    assert client.post(f"/api/v1/trainer/approvals/leave/{lid}", json={"decision": "approve"}, headers=ARUN).status_code == 409


def test_request_rules(week):
    today = datetime.date.today()
    assert _request(end_date=(today - datetime.timedelta(days=3)).isoformat()).status_code == 422          # ends before it starts
    assert _request(start_date=(today - datetime.timedelta(days=20)).isoformat()).status_code == 422        # too far back
    assert _request(start_date=today.isoformat(), end_date=(today + datetime.timedelta(days=40)).isoformat()).status_code == 422
    assert _request().status_code == 201
    assert _request(start_date=today.isoformat()).status_code == 409                                          # overlaps
    assert client.post("/api/v1/parent/leave-requests", json={"child_id": "std_priya_01", "start_date": today.isoformat(),
                                                              "end_date": today.isoformat(), "reason": "Not my child"}, headers=LAKSHMI).status_code == 404


def test_cyber_range_requests_share_the_queue_and_roles_are_guarded():
    q = client.get("/api/v1/trainer/approvals?status=all", headers=ARUN).json()
    assert set(q["counts"]) == {"leave", "lab_access", "certificate"}   # certificate proofs joined in S11
    for h in (PRIYA, RAMESH, KAVITHA):
        assert client.get("/api/v1/trainer/approvals", headers=h).status_code == 403
    assert client.get("/api/v1/parent/attendance", headers=PRIYA).status_code == 403


def test_parent_attendance_needs_consent(week):
    client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "withdrawn"}, headers=RAMESH)
    try:
        assert client.get("/api/v1/parent/attendance", headers=RAMESH).json()["consent_required"] is True
    finally:
        client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "granted"}, headers=RAMESH)
