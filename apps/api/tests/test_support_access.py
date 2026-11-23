"""IREP staff read student or parent data only inside an active support session
(services/support_access.py, docs/PERMISSIONS.md). Every read is audited with the session id."""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import AuditLog, DataRequest, SupportSession

client = TestClient(app)


def _h(sub, role, cid):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": cid})}


STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
SUPER = _h("usr_irep_super_01", "super_admin", PLATFORM_TENANT)
KAVITHA = _h("usr_kavitha_01", "college_admin", "col_demo_001")
CONSENT = "/api/v1/admin/consent?college_id=col_demo_001"
HISTORY = "/api/v1/admin/consent/std_priya_01/history"


def _open(college="col_demo_001", staff="usr_irep_staff_01", minutes=30):
    r = client.post("/api/v1/admin/support-sessions", headers=SUPER, json={
        "college_id": college, "staff_user_id": staff, "minutes": minutes, "reason": "Parent asked why the card is missing"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture(autouse=True)
def no_open_sessions():
    """Each test starts and ends without open sessions for the demo staff account."""
    def close_all():
        db = SessionLocal()
        try:
            for s in db.execute(select(SupportSession).where(SupportSession.ended_at.is_(None))).scalars():
                s.ended_at = datetime.datetime.utcnow()
            db.commit()
        finally:
            db.close()
    close_all()
    yield
    close_all()


def _audits(action, since):
    db = SessionLocal()
    try:
        return db.execute(select(AuditLog).where(AuditLog.action == action, AuditLog.created_at >= since)).scalars().all()
    finally:
        db.close()


def test_without_a_session_student_data_is_403_and_the_attempt_is_logged():
    t0 = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
    for path in (CONSENT, HISTORY):
        r = client.get(path, headers=STAFF)
        assert r.status_code == 403 and "support session" in r.json()["detail"], path
    denied = _audits("support.read_denied", t0)
    assert {a.detail["view"] for a in denied} >= {"consent", "consent_history"}


def test_inside_a_session_reads_work_and_each_read_is_audited_with_the_session():
    t0 = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
    sid = _open()
    assert client.get(CONSENT, headers=STAFF).status_code == 200
    assert client.get(HISTORY, headers=STAFF).status_code == 200
    reads = _audits("support.read", t0)
    assert len(reads) == 2 and all(a.detail["support_session_id"] == sid and a.college_id == "col_demo_001" for a in reads)
    # ending the session closes access at once
    client.post(f"/api/v1/admin/support-sessions/{sid}/end", headers=SUPER)
    assert client.get(CONSENT, headers=STAFF).status_code == 403


def test_a_session_is_scoped_to_one_college_one_person_and_its_time():
    _open(college="col_demo_001", staff="usr_irep_super_01")          # someone else's session
    assert client.get(CONSENT, headers=STAFF).status_code == 403
    db = SessionLocal()
    try:
        other = db.execute(select(DataRequest.college_id)).first()
    finally:
        db.close()
    sid = _open()
    assert client.get("/api/v1/admin/consent?college_id=col_other_999", headers=STAFF).status_code == 403   # other college
    db = SessionLocal()
    try:
        s = db.get(SupportSession, sid)
        s.expires_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)                      # time is up
        db.commit()
    finally:
        db.close()
    assert client.get(CONSENT, headers=STAFF).status_code == 403


def test_super_admin_needs_a_session_too():
    assert client.get(CONSENT, headers=SUPER).status_code == 403
    _open(staff="usr_irep_super_01")
    assert client.get(CONSENT, headers=SUPER).status_code == 200


def test_data_request_queue_hides_names_and_export_needs_a_session():
    rid = client.post("/api/v1/college/data-requests", headers=KAVITHA, json={
        "student_id": "std_priya_01", "kind": "export", "reason": "Student asked for a copy of her data"})
    if rid.status_code == 409:                                         # an open one already exists
        rid = next(i for i in client.get("/api/v1/college/data-requests", headers=KAVITHA).json()["items"]
                   if i["student_id"] == "std_priya_01" and i["kind"] == "export" and i["status"] in ("received", "in_progress"))["id"]
    else:
        rid = rid.json()["id"]
    item = next(i for i in client.get("/api/v1/admin/data-requests", headers=STAFF).json()["items"] if i["id"] == rid)
    assert item["name_hidden"] is True and item["student_name"] is None and item["student_id"] == "std_priya_01"
    assert client.get(f"/api/v1/admin/data-requests/{rid}/export", headers=STAFF).status_code == 403
    _open()
    item = next(i for i in client.get("/api/v1/admin/data-requests", headers=STAFF).json()["items"] if i["id"] == rid)
    assert item["name_hidden"] is False and item["student_name"] == "Priya R"
    assert client.post(f"/api/v1/admin/data-requests/{rid}/reject", headers=STAFF,
                       json={"reason": "Test request, not needed"}).json()["status"] == "rejected"


def test_audit_trail_hides_student_and_parent_names_without_a_session():
    rows = client.get("/api/v1/admin/audit?college_id=col_demo_001&page_size=200", headers=STAFF).json()["items"]
    people = [r for r in rows if r["actor_role"] in ("student", "parent")]
    assert people and all(r["actor_name"] is None and r["actor_user_id"] for r in people)
    _open()
    rows = client.get("/api/v1/admin/audit?college_id=col_demo_001&page_size=200", headers=STAFF).json()["items"]
    assert any(r["actor_name"] for r in rows if r["actor_role"] in ("student", "parent"))


def test_college_admin_routes_are_unaffected():
    assert client.get("/api/v1/college/data-requests", headers=KAVITHA).status_code == 200
