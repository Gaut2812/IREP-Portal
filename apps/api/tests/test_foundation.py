"""S0 foundation tests: role-aware demo fallback, tenant helpers, cohort seed,
notification centre and audit log."""
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from main import app
from core.database import SessionLocal
from core.security import create_access_token, TokenPayload
from core.tenant import get_student_for_user, get_child_for_parent, get_parent_children
from models.schema import Branch, Batch, BatchTrainer, Student, Certificate, Internship, User, Notification, AuditLog
from services.notifications import notify_user
from services.audit import record_audit
from fastapi import HTTPException

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Test"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


# ---- demo fallback honours X-Demo-Role ----------------------------------

def test_me_defaults_to_demo_student_without_token():
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["role"] == "student"
    assert res.json()["sub"] == "usr_priya_01"


@pytest.mark.parametrize("header_role,expected_sub,expected_role", [
    ("trainer", "usr_arun_01", "trainer"),
    ("college", "usr_kavitha_01", "college_admin"),
    ("college_admin", "usr_kavitha_01", "college_admin"),
    ("parent", "usr_ramesh_01", "parent"),
])
def test_demo_role_header_selects_profile(header_role, expected_sub, expected_role):
    res = client.get("/api/v1/auth/me", headers={"X-Demo-Role": header_role})
    assert res.status_code == 200
    assert res.json()["sub"] == expected_sub
    assert res.json()["role"] == expected_role


def test_real_jwt_wins_over_demo_header():
    res = client.get("/api/v1/auth/me", headers={**_token("usr_arun_01", "trainer"), "X-Demo-Role": "parent"})
    assert res.json()["role"] == "trainer"


def test_role_guard_rejects_wrong_role():
    res = client.get("/api/v1/trainer/coding-problems", headers=_token("usr_priya_01", "student"))
    assert res.status_code == 403
    res = client.get("/api/v1/trainer/coding-problems", headers={"X-Demo-Role": "trainer"})
    assert res.status_code == 200


# ---- demo logins return real JWTs for every role --------------------------

@pytest.mark.parametrize("role,identifier", [
    ("student", "priya.r@demo.edu"),
    ("trainer", "arun.k@demo.edu"),
    ("college", "admin@demo.edu"),
])
def test_demo_login_each_role(role, identifier):
    res = client.post("/api/v1/auth/login", json={"role": role, "identifier": identifier, "password": "password123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == identifier


def _otp_login(phone):
    otp = client.post("/api/v1/auth/parent/otp/request", json={"phone": phone}).json()["demo_otp"]
    return client.post("/api/v1/auth/parent/otp/verify", json={"phone": phone, "otp": otp})


def test_parent_otp_resolves_by_phone():
    from seed.seed_screen01 import seed_screen01
    res = _otp_login("9876543214")
    assert res.status_code == 200
    assert res.json()["user"]["id"] == "usr_lakshmi_01"
    assert _otp_login("9876543210").json()["user"]["id"] == "usr_ramesh_01"
    db = SessionLocal()
    try:
        seed_screen01(db)
        db.commit()
    finally:
        db.close()


# ---- tenant helpers --------------------------------------------------------

def test_student_resolution_is_per_user_not_per_college():
    db = SessionLocal()
    try:
        priya = get_student_for_user(TokenPayload(sub="usr_priya_01", role="student", college_id="col_demo_001"), db)
        assert priya.id == "std_priya_01"
        karthik_user = db.execute(select(User).filter_by(name="Karthik S")).scalars().first()
        karthik = get_student_for_user(TokenPayload(sub=karthik_user.id, role="student", college_id="col_demo_001"), db)
        assert karthik.id != priya.id
        with pytest.raises(HTTPException) as exc:
            get_student_for_user(TokenPayload(sub="usr_priya_01", role="student", college_id="col_other_999"), db)
        assert exc.value.status_code == 404
    finally:
        db.close()


def test_parent_sees_only_own_children():
    db = SessionLocal()
    try:
        ramesh = TokenPayload(sub="usr_ramesh_01", role="parent", college_id="col_demo_001")
        lakshmi = TokenPayload(sub="usr_lakshmi_01", role="parent", college_id="col_demo_001")
        ramesh_kids = get_parent_children(ramesh, db)
        lakshmi_kids = get_parent_children(lakshmi, db)
        assert [c.id for c in ramesh_kids] == ["std_priya_01"]
        assert len(lakshmi_kids) == 1 and lakshmi_kids[0].id != "std_priya_01"
        with pytest.raises(HTTPException) as exc:
            get_child_for_parent(lakshmi, db, "std_priya_01")
        assert exc.value.status_code == 404
    finally:
        db.close()


def test_parent_overview_endpoint_scoped_per_parent():
    r1 = client.get("/api/v1/parent/overview", headers=_token("usr_ramesh_01", "parent"))
    r2 = client.get("/api/v1/parent/overview", headers=_token("usr_lakshmi_01", "parent"))
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["ward"]["name"] == "Priya R"
    assert r2.json()["ward"]["name"] == "Karthik S"
    assert r2.json()["kpis"]["readiness_score"] == 52
    # probing another parent's child id is a 404
    r3 = client.get("/api/v1/parent/overview?child_id=std_priya_01", headers=_token("usr_lakshmi_01", "parent"))
    assert r3.status_code == 404
    # students cannot open the parent overview
    assert client.get("/api/v1/parent/overview", headers=_token("usr_priya_01", "student")).status_code == 403


# ---- cohort seed -----------------------------------------------------------

def test_cohort_matches_mockup_figures():
    db = SessionLocal()
    try:
        assert db.execute(select(func.count(Student.id)).filter_by(college_id="col_demo_001")).scalar_one() == 612
        per_branch = dict(db.execute(
            select(Branch.name, func.count(Student.id)).join(Student, Student.branch_id == Branch.id).group_by(Branch.name)
        ).all())
        assert per_branch == {"CSE": 228, "IT": 164, "AI & DS": 142, "Cybersecurity": 78}
        arun = db.execute(
            select(Batch.short_name, func.count(Student.id), func.avg(Student.readiness_score))
            .join(BatchTrainer, BatchTrainer.batch_id == Batch.id)
            .join(Student, Student.batch_id == Batch.id)
            .where(BatchTrainer.trainer_id == "trn_arun_01")
            .group_by(Batch.short_name)
        ).all()
        by_name = {row[0]: (row[1], round(row[2])) for row in arun}
        assert by_name == {"CSE-A": (50, 82), "CSE-B": (50, 76), "IT-A": (48, 71), "AI&DS": (50, 79), "Cyber": (50, 68)}
        assert db.execute(select(func.count(Certificate.id)).filter_by(status="earned")).scalar_one() == 184
        assert db.execute(select(func.count(Internship.id))).scalar_one() == 73
        priya = db.execute(select(Student).filter_by(id="std_priya_01")).scalar_one()
        assert priya.batch_id == "bat_aids_s5_aids" and priya.branch_id == "br_aids"
    finally:
        db.close()


# ---- notifications + audit -----------------------------------------------

def test_notification_centre_roundtrip():
    db = SessionLocal()
    try:
        created = notify_user(db, "usr_priya_01", "Test notice", "Body", kind="info", link="/student")
        db.commit()
        nid = created[0].id
    finally:
        db.close()
    headers = _token("usr_priya_01", "student")
    unread_before = client.get("/api/v1/notifications/unread-count", headers=headers).json()["unread"]
    assert unread_before >= 1
    listing = client.get("/api/v1/notifications", headers=headers).json()
    assert any(i["id"] == nid for i in listing["items"])
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=headers).status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=headers).json()["unread"] == unread_before - 1
    # another user cannot read it
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=_token("usr_arun_01", "trainer")).status_code == 404


def test_audit_log_is_written():
    db = SessionLocal()
    try:
        before = db.execute(select(func.count(AuditLog.id))).scalar_one()
        record_audit(db, TokenPayload(sub="usr_arun_01", role="trainer", college_id="col_demo_001"), "test.action", "thing", "t1", {"k": 1})
        db.commit()
        after = db.execute(select(func.count(AuditLog.id))).scalar_one()
        assert after == before + 1
        row = db.execute(select(AuditLog).filter_by(action="test.action").order_by(AuditLog.created_at.desc())).scalars().first()
        assert row.actor_user_id == "usr_arun_01" and row.detail == {"k": 1}
    finally:
        db.close()
