"""Screen 48 · Audit and consent. Spec: docs/screens/48-audit-and-consent.md"""
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
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import AuditLog, ConsentRecord, DataRequest, Notification, OutboxEvent, ParentStudent, Student, User
from services import outbox

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
KAVITHA = _h("usr_kavitha_01", "college_admin")
OTHER_COLLEGE_ADMIN = _h("usr_kavitha_01", "college_admin", "col_other_999")
RAMESH = _h("usr_ramesh_01", "parent")
LAKSHMI = _h("usr_lakshmi_01", "parent")
PRIYA = _h("usr_priya_01", "student")


@pytest.fixture
def throwaway_student():
    """A student that a deletion request may anonymise for good."""
    tag = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        db.add(User(id=f"usr_tmp_{tag}", college_id="col_demo_001", email=f"tmp.{tag}@demo.edu", hashed_password="x",
                    role="student", name="Temp Student", phone="9000000000", avatar_initials="TS"))
        db.flush()
        db.add(Student(id=f"std_tmp_{tag}", college_id="col_demo_001", user_id=f"usr_tmp_{tag}", register_no=f"TMP{tag}",
                       branch="CSE", semester=5, batch_name="CSE-A"))
        db.flush()            # models declare no relationship(): insert parents before links
        db.add(ParentStudent(id=f"ps_tmp_{tag}", college_id="col_demo_001", parent_user_id="usr_ramesh_01",
                             student_id=f"std_tmp_{tag}", relationship="Father"))
        db.commit()
    finally:
        db.close()
    yield f"std_tmp_{tag}"
    db = SessionLocal()
    try:
        sid = f"std_tmp_{tag}"
        rids = list(db.execute(select(DataRequest.id).where(DataRequest.subject_student_id == sid)).scalars())
        db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id.in_(rids or ["_"])))
        db.execute(delete(DataRequest).where(DataRequest.subject_student_id == sid))
        db.execute(delete(ConsentRecord).where(ConsentRecord.subject_student_id == sid))
        db.execute(delete(ParentStudent).where(ParentStudent.student_id == sid))
        db.execute(delete(Student).where(Student.id == sid))
        db.execute(delete(User).where(User.id == f"usr_tmp_{tag}"))
        db.commit()
    finally:
        db.close()


def _drain():
    outbox.dispatch_pending(SessionLocal, limit=100_000)


# ---- audit trail -----------------------------------------------------------

@pytest.mark.link("L38")
def test_trail_is_filtered_paged_and_read_only():
    client.post("/api/v1/consent", json={"purpose": "sms_alerts", "status": "granted"}, headers=RAMESH)   # makes a fresh row
    r = client.get("/api/v1/admin/audit?college_id=col_demo_001&action=consent.&page_size=5", headers=STAFF).json()
    assert r["total"] >= 1 and len(r["items"]) <= 5
    assert all(i["action"].startswith("consent.") and i["college_id"] == "col_demo_001" for i in r["items"])
    newest = r["items"][0]
    assert newest["action"] == "consent.recorded" and newest["actor_name"] == "Mr. Ramesh K"
    page2 = client.get("/api/v1/admin/audit?college_id=col_demo_001&page=2&page_size=5", headers=STAFF).json()
    assert {i["id"] for i in page2["items"]}.isdisjoint({i["id"] for i in r["items"]}) or r["total"] <= 5
    # no write/delete endpoint exists for the trail
    assert client.delete(f"/api/v1/admin/audit/{newest['id']}", headers=STAFF).status_code in (404, 405)
    assert client.post("/api/v1/admin/audit", json={}, headers=STAFF).status_code in (404, 405)
    # looking at a college's records is itself audited
    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "support.access", AuditLog.college_id == "col_demo_001")).first()
    finally:
        db.close()


def test_csv_export_is_audited():
    r = client.get("/api/v1/admin/audit/export.csv?college_id=col_demo_001&action=consent.", headers=STAFF)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("at,college_id,actor_user_id")
    db = SessionLocal()
    try:
        row = db.execute(select(AuditLog).where(AuditLog.action == "audit.exported").order_by(AuditLog.created_at.desc())).scalars().first()
        assert row.detail["filters"]["action"] == "consent." and row.detail["rows"] == len(r.text.splitlines()) - 1
    finally:
        db.close()


@pytest.mark.parametrize("headers", [KAVITHA, RAMESH, PRIYA, _h("usr_arun_01", "trainer")])
def test_only_staff_read_the_trail(headers):
    assert client.get("/api/v1/admin/audit", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/data-requests", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/consent?college_id=col_demo_001", headers=headers).status_code == 403


# ---- consent ---------------------------------------------------------------

@pytest.mark.link("L38")
def test_withdrawal_is_a_new_row_and_hides_the_child_from_the_parent():
    db = SessionLocal()
    try:
        karthik = db.execute(select(ParentStudent.student_id).where(ParentStudent.parent_user_id == "usr_lakshmi_01")).scalars().first()
        before = db.execute(select(ConsentRecord).where(ConsentRecord.subject_student_id == karthik)).scalars().all()
    finally:
        db.close()
    assert client.get("/api/v1/parent/overview", headers=LAKSHMI).json()["consent_required"] is False
    w = client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "withdrawn"}, headers=LAKSHMI)
    assert w.status_code == 201
    hidden = client.get("/api/v1/parent/overview?lang=ta", headers=LAKSHMI).json()
    assert hidden["consent_required"] is True and hidden["consent_state"] == "withdrawn"
    assert "kpis" not in hidden and hidden["consent"]["title"].startswith("உங்கள்")
    assert client.get("/api/v1/consent", headers=LAKSHMI).json()["consents"]["parent_data_processing"] == "withdrawn"
    client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "granted"}, headers=LAKSHMI)
    assert client.get("/api/v1/parent/overview", headers=LAKSHMI).json()["consent_required"] is False
    db = SessionLocal()
    try:
        after = db.execute(select(ConsentRecord).where(ConsentRecord.subject_student_id == karthik)).scalars().all()
        assert len(after) == len(before) + 2                  # append-only
    finally:
        db.close()
    staff = client.get(f"/api/v1/admin/consent/{karthik}/history", headers=STAFF).json()["history"]
    assert [h["status"] for h in staff[:2]] == ["granted", "withdrawn"]


def test_consent_only_for_own_child_or_self():
    assert client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "granted", "student_id": "std_priya_01"},
                       headers=LAKSHMI).status_code == 404
    assert client.post("/api/v1/consent", json={"purpose": "public_portfolio", "status": "granted", "student_id": "std_cse_x"},
                       headers=PRIYA).status_code == 404
    assert client.post("/api/v1/consent", json={"purpose": "selling_data", "status": "granted"}, headers=RAMESH).status_code == 422
    assert client.post("/api/v1/consent", json={"purpose": "ai_hints", "status": "granted"}, headers=KAVITHA).status_code == 403
    ov = client.get("/api/v1/admin/consent?college_id=col_demo_001&purpose=parent_data_processing&page_size=20", headers=STAFF).json()
    assert ov["total"] == 612 and len(ov["items"]) == 20 and all(set(i["consents"]) == {"parent_data_processing"} for i in ov["items"])
    hist = client.get("/api/v1/admin/consent/std_priya_01/history", headers=STAFF).json()["history"]
    assert any(h["purpose"] == "parent_data_processing" and h["status"] == "granted" for h in hist)


# ---- data requests (L27 return path to 02 is planned until 02 exists) ------

def test_export_request_end_to_end(throwaway_student):
    r = client.post("/api/v1/college/data-requests", json={"student_id": throwaway_student, "kind": "export",
                                                           "reason": "Student asked for a copy of their data"}, headers=KAVITHA)
    assert r.status_code == 201 and r.json()["status"] == "received" and r.json()["days_left"] == 30
    rid = r.json()["id"]
    assert client.post("/api/v1/college/data-requests", json={"student_id": throwaway_student, "kind": "export",
                                                              "reason": "Duplicate of the same request"}, headers=KAVITHA).status_code == 409
    queue = client.get("/api/v1/admin/data-requests", headers=STAFF).json()["items"]
    assert queue[0]["status"] in ("received", "in_progress") and any(i["id"] == rid for i in queue)
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_irep_staff_01", Notification.link == "/admin/audit/requests")).first()
    finally:
        db.close()

    assert client.post(f"/api/v1/admin/data-requests/{rid}/complete", headers=STAFF).json()["status"] == "in_progress"
    assert client.get(f"/api/v1/college/data-requests/{rid}/export", headers=KAVITHA).status_code == 409   # not built yet
    _drain()                                                       # the outbox builds the file after commit
    mine = next(i for i in client.get("/api/v1/college/data-requests", headers=KAVITHA).json()["items"] if i["id"] == rid)
    assert mine["status"] == "completed" and mine["has_export"] is True
    dl = client.get(f"/api/v1/college/data-requests/{rid}/export", headers=KAVITHA)
    assert dl.status_code == 200 and dl.json()["profile"]["register_no"].startswith("TMP")
    assert client.get(f"/api/v1/college/data-requests/{rid}/export", headers=OTHER_COLLEGE_ADMIN).status_code == 404
    assert client.post(f"/api/v1/admin/data-requests/{rid}/complete", headers=STAFF).status_code == 409
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_kavitha_01", Notification.title_en == "Data export ready")).first()
    finally:
        db.close()


def test_deletion_anonymises_and_rejection_needs_a_reason(throwaway_student):
    other = client.post("/api/v1/college/data-requests", json={"student_id": throwaway_student, "kind": "export",
                                                               "reason": "Wrong student selected by mistake"}, headers=KAVITHA).json()["id"]
    assert client.post(f"/api/v1/admin/data-requests/{other}/reject", json={"reason": ""}, headers=STAFF).status_code == 422
    assert client.post(f"/api/v1/admin/data-requests/{other}/reject", json={"reason": "Raised for the wrong student"}, headers=STAFF).json()["status"] == "rejected"

    rid = client.post("/api/v1/college/data-requests", json={"student_id": throwaway_student, "kind": "deletion",
                                                             "reason": "Student left the programme and asked for deletion"}, headers=KAVITHA).json()["id"]
    done = client.post(f"/api/v1/admin/data-requests/{rid}/complete", headers=STAFF).json()
    assert done["status"] == "completed"
    db = SessionLocal()
    try:
        s = db.get(Student, throwaway_student)
        u = db.get(User, s.user_id)
        assert s.register_no.startswith("DELETED-") and u.name.startswith("Deleted student") and u.phone is None and u.is_active is False
        assert db.execute(select(ParentStudent).where(ParentStudent.student_id == throwaway_student)).first() is None
        assert db.execute(select(AuditLog).where(AuditLog.entity_id == rid, AuditLog.action == "data_request.completed")).first()
    finally:
        db.close()


def test_college_admin_only_for_own_students():
    assert client.post("/api/v1/college/data-requests", json={"student_id": "std_priya_01", "kind": "export",
                                                              "reason": "Not my college's student"}, headers=OTHER_COLLEGE_ADMIN).status_code == 404
    assert client.post("/api/v1/college/data-requests", json={"student_id": "std_priya_01", "kind": "export", "reason": "short"},
                       headers=KAVITHA).status_code == 422
    assert client.post("/api/v1/college/data-requests", json={"student_id": "std_priya_01", "kind": "export",
                                                              "reason": "A parent may not raise this"}, headers=RAMESH).status_code == 403
