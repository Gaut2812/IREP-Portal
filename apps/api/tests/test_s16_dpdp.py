"""S16 DPDP: minors, verifiable parental consent, notices, self-service requests.
Spec: docs/screens/47-16-billing-and-dpdp.md (DPDP part)."""
import datetime
import sys
import time
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
from models.schema import AuditLog, ConsentRecord, DataRequest, Notification, Student, StudyBuddyMessage
from seed.seed_s16_dpdp import MINOR, PARENT, seed_s16_dpdp
from services import consent as consent_svc

client = TestClient(app)
VINOTH_USER = "usr_aids_2_001_1654"


def _h(sub, role, college_id="col_demo_001", auth_time=None):
    claims = {"sub": sub, "role": role, "college_id": college_id, "name": sub}
    if auth_time is not None:
        claims["auth_time"] = auth_time
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _now() -> int:
    return int(time.time())


SELVI_FRESH = lambda: _h(PARENT, "parent", auth_time=_now() - 60)              # noqa: E731  signed in a minute ago
SELVI_STALE = _h(PARENT, "parent", auth_time=_now() - 3600)                    # an hour ago
VINOTH = _h(VINOTH_USER, "student")
PRIYA = _h("usr_priya_01", "student")
RAMESH = _h("usr_ramesh_01", "parent", auth_time=_now())
KAVITHA = _h("usr_kavitha_01", "college_admin")
OTHER_ADMIN = _h("usr_kavitha_01", "college_admin", "col_other_999")


@pytest.fixture(autouse=True)
def dpdp_state():
    """Every test starts and ends with the seeded DPDP demo state."""
    start = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
    yield
    db = SessionLocal()
    try:
        db.execute(delete(ConsentRecord).where(ConsentRecord.subject_student_id == "std_priya_01", ConsentRecord.recorded_at >= start))
        db.execute(delete(DataRequest).where(DataRequest.created_at >= start))
        db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.student_id == MINOR))
        seed_s16_dpdp(db)
        db.commit()
    finally:
        db.close()


def test_minor_and_age_rules():
    today = datetime.date(2026, 11, 22)
    assert consent_svc.age_on(datetime.date(2008, 11, 22), today) == 18
    assert consent_svc.age_on(datetime.date(2008, 11, 23), today) == 17
    assert consent_svc.is_minor(type("S", (), {"date_of_birth": None})())        # unknown: treated as a minor
    assert consent_svc.identity_fresh(_now() - 60) and not consent_svc.identity_fresh(_now() - 3600)
    assert not consent_svc.identity_fresh(None)


def test_minor_request_then_parent_approves_with_fresh_otp_sign_in():
    view = client.get("/api/v1/consent", headers=VINOTH).json()
    assert view["is_minor"] is True and view["purposes"]["ai_hints"]["status"] == "requested"
    assert view["purposes"]["ai_hints"]["effective"] is False and view["purposes"]["ai_hints"]["needs_parent"] is True

    # a minor's own "yes" to an optional purpose only creates a request for the parents
    r = client.post("/api/v1/consent", json={"purpose": "recordings", "status": "granted"}, headers=VINOTH)
    assert r.status_code == 201 and r.json()["status"] == "requested" and r.json()["notice_version"] == "2026-11"
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == PARENT, Notification.link == "/parent/consent")).first()
        assert db.execute(select(AuditLog).where(AuditLog.action == "consent.requested", AuditLog.entity_id == MINOR)).first()
    finally:
        db.close()

    # the parent, signed in with the OTP an hour ago, must sign in again
    stale = client.post("/api/v1/consent", json={"purpose": "ai_hints", "status": "granted", "student_id": MINOR}, headers=SELVI_STALE)
    assert stale.status_code == 403 and stale.json()["detail"]["message"].startswith("To give consent, sign in again")
    over = client.get("/api/v1/parent/consent", headers=SELVI_STALE).json()
    assert over["identity_fresh"] is False and over["children"][0]["student_id"] == MINOR

    ok = client.post("/api/v1/consent", json={"purpose": "ai_hints", "status": "granted", "student_id": MINOR}, headers=SELVI_FRESH())
    assert ok.status_code == 201 and ok.json()["status"] == "granted"
    db = SessionLocal()
    try:
        row = db.execute(select(ConsentRecord).where(ConsentRecord.id == ok.json()["id"])).scalar_one()
        assert row.method == "otp_parent" and row.verified_at is not None and row.notice_version == "2026-11"
        assert consent_svc.allowed(db, db.get(Student, MINOR), "ai_hints")
    finally:
        db.close()
    assert client.get("/api/v1/consent", headers=VINOTH).json()["purposes"]["ai_hints"]["effective"] is True


def test_study_buddy_waits_for_the_parent_for_a_minor_in_english_and_tamil():
    r = client.post("/api/v1/student/buddy/ask", json={"question": "What is a linked list?"}, headers=VINOTH)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "parental_consent_required"
    assert "18" in r.json()["detail"]["message_ta"]
    client.post("/api/v1/consent", json={"purpose": "ai_hints", "status": "granted", "student_id": MINOR}, headers=SELVI_FRESH())
    assert client.post("/api/v1/student/buddy/ask", json={"question": "What is a linked list?"}, headers=VINOTH).status_code == 200


def test_adult_decides_for_themselves():
    r = client.post("/api/v1/consent", json={"purpose": "public_portfolio", "status": "granted", "student_id": "std_priya_01"},
                    headers=RAMESH)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "adult_decides" and r.json()["detail"]["message"].startswith("Your child is 18")
    own = client.post("/api/v1/consent", json={"purpose": "public_portfolio", "status": "granted"}, headers=PRIYA)
    assert own.status_code == 201 and own.json()["status"] == "granted"
    view = client.get("/api/v1/consent?lang=ta", headers=PRIYA).json()
    assert view["is_minor"] is False and view["purposes"]["public_portfolio"]["effective"] is True
    assert "போர்ட்ஃபோலியோ" in view["purposes"]["public_portfolio"]["notice"]                # Tamil notice


def test_parent_consent_overview_guards():
    assert client.get("/api/v1/parent/consent", headers=VINOTH).status_code == 403
    # a parent cannot act for a child who is not linked to them (404)
    r = client.post("/api/v1/consent", json={"purpose": "ai_hints", "status": "granted", "student_id": MINOR}, headers=RAMESH)
    assert r.status_code == 404


def test_college_records_date_of_birth():
    r = client.put("/api/v1/college/students/std_priya_01/dob", json={"date_of_birth": "2010-01-15"}, headers=KAVITHA)
    assert r.status_code == 200 and r.json()["is_minor"] is True
    assert client.put("/api/v1/college/students/std_priya_01/dob", json={"date_of_birth": "2024-01-01"}, headers=KAVITHA).status_code == 422
    assert client.put("/api/v1/college/students/std_priya_01/dob", json={"date_of_birth": "2004-01-01"}, headers=PRIYA).status_code == 403
    assert client.put("/api/v1/college/students/std_priya_01/dob", json={"date_of_birth": "2004-01-01"}, headers=OTHER_ADMIN).status_code == 404
    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "student.dob_set", AuditLog.entity_id == "std_priya_01")).first()
    finally:
        db.close()


def test_import_validates_the_dob_column():
    head = "register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone,parent_email,parent_consent,parent_consent_ref,dob\n"
    row = "910021AI0001,Vinoth S,vinoth.s@demo.edu,9662901948,AIDS,AIDS-S2,2,,,,,,{}\n"

    def dry(dob):
        return client.post("/api/v1/college/students/import?dry_run=true", headers=KAVITHA,
                           files={"file": ("s.csv", (head + row.format(dob)).encode(), "text/csv")}).json()
    assert dry("2009-06-21")["summary"]["errors"] == 0
    bad = dry("21/06/2009")
    assert bad["summary"]["errors"] == 1 and "YYYY-MM-DD" in str(bad)


def test_self_service_requests():
    # a minor asks a parent instead (English and Tamil)
    r = client.post("/api/v1/me/data-requests", json={"kind": "export", "reason": "I want a copy of my data"}, headers=VINOTH)
    assert r.status_code == 403 and r.json()["detail"]["message"].startswith("You are under 18")
    ta = client.post("/api/v1/me/data-requests", json={"kind": "export", "reason": "I want a copy of my data"},
                     headers={**VINOTH, "Accept-Language": "ta"})
    assert ta.status_code == 403
    # the parent asks for the child; an adult asks for themselves
    p = client.post("/api/v1/me/data-requests", json={"kind": "export", "reason": "A copy of my son's records", "student_id": MINOR},
                    headers=SELVI_FRESH())
    assert p.status_code == 201 and p.json()["student_id"] == MINOR
    assert client.post("/api/v1/me/data-requests", json={"kind": "export", "reason": "A copy of my son's records", "student_id": MINOR},
                       headers=SELVI_FRESH()).status_code == 409
    own = client.post("/api/v1/me/data-requests", json={"kind": "deletion", "reason": "I am leaving the programme"}, headers=PRIYA)
    assert own.status_code == 201
    mine = client.get("/api/v1/me/data-requests", headers=PRIYA).json()["items"]
    assert [i["kind"] for i in mine] == ["deletion"]
    assert client.get(f"/api/v1/me/data-requests/{own.json()['id']}/export", headers=PRIYA).status_code == 404
    assert client.get(f"/api/v1/me/data-requests/{p.json()['id']}/export", headers=PRIYA).status_code == 404     # not hers
    assert client.post("/api/v1/me/data-requests", json={"kind": "export", "reason": "copy please now"}, headers=KAVITHA).status_code == 403
    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "data_request.created", AuditLog.entity_id == own.json()["id"])).first()
    finally:
        db.close()
