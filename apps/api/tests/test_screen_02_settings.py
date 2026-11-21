"""Screen 02 · College settings. Spec: docs/screens/02-college-settings.md"""
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
from models.schema import (AuditLog, Batch, BatchTrainer, Branch, College, ConsentRecord, DataRequest, MouTerm, Notification, OutboxEvent,
                           ParentStudent, Student, User)
from services import outbox

client = TestClient(app)
STAFF = {"Authorization": "Bearer " + create_access_token({"sub": "usr_irep_staff_01", "role": "irep_admin", "college_id": PLATFORM_TENANT})}
KAVITHA = {"Authorization": "Bearer " + create_access_token({"sub": "usr_kavitha_01", "role": "college_admin", "college_id": "col_demo_001"})}


def _login(email, password, role="college"):
    return client.post("/api/v1/auth/login", json={"role": role, "identifier": email, "password": password})


@pytest.fixture
def college():
    code = "G" + uuid.uuid4().hex[:7].upper()
    cid = client.post("/api/v1/admin/colleges", json={"name": "Settings Test College", "code": code, "city": "Salem",
                                                      "state": "Tamil Nadu"}, headers=STAFF).json()["id"]
    email = f"admin.{code.lower()}@college.example"
    r = client.post(f"/api/v1/admin/colleges/{cid}/admins", json={"name": "Dr. Admin", "email": email}, headers=STAFF).json()
    tok = _login(email, r["temporary_password"]).json()["access_token"]
    yield {"id": cid, "code": code, "admin_id": r["id"], "h": {"Authorization": f"Bearer {tok}"}}
    db = SessionLocal()
    try:
        sids = list(db.execute(select(Student.id).where(Student.college_id == cid)).scalars())
        rids = list(db.execute(select(DataRequest.id).where(DataRequest.college_id == cid)).scalars())
        db.execute(delete(OutboxEvent).where(OutboxEvent.college_id == cid))
        db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id.in_(rids or ["_"])))
        db.execute(delete(DataRequest).where(DataRequest.college_id == cid))
        db.execute(delete(ConsentRecord).where(ConsentRecord.subject_student_id.in_(sids or ["_"])))
        db.execute(delete(ParentStudent).where(ParentStudent.college_id == cid))
        db.execute(delete(Student).where(Student.college_id == cid))
        db.execute(delete(BatchTrainer).where(BatchTrainer.college_id == cid))
        db.execute(delete(Batch).where(Batch.college_id == cid))
        db.execute(delete(Branch).where(Branch.college_id == cid))
        db.execute(delete(Notification).where(Notification.college_id == cid))
        db.execute(delete(User).where(User.college_id == cid))
        db.execute(delete(MouTerm).where(MouTerm.college_id == cid))
        db.execute(delete(College).where(College.id == cid))
        db.commit()
    finally:
        db.close()


def test_add_a_placement_officer_who_signs_in_to_the_college_ui(college):
    tag = college["code"].lower()
    r = client.post("/api/v1/college/users", json={"name": "Suresh P", "email": f"placement.{tag}@college.example",
                                                   "role": "placement_officer"}, headers=college["h"])
    assert r.status_code == 201
    login = _login(f"placement.{tag}@college.example", r.json()["temporary_password"])
    assert login.status_code == 200 and login.json()["user"]["role"] == "placement_officer"
    tok = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/api/v1/college/overview", headers=tok).status_code == 200       # college UI, own college
    assert client.get("/api/v1/college/settings", headers=tok).status_code == 403       # settings are admin-only
    assert client.post("/api/v1/college/users", json={"name": "Dup", "email": f"PLACEMENT.{tag}@college.example",
                                                      "role": "college_admin"}, headers=college["h"]).status_code == 409
    assert client.post("/api/v1/college/users", json={"name": "Bad Role", "email": f"x.{tag}@college.example",
                                                      "role": "irep_admin"}, headers=college["h"]).status_code == 422
    users = {u["email"]: u for u in client.get("/api/v1/college/settings", headers=college["h"]).json()["users"]}
    assert users[f"placement.{tag}@college.example"]["role"] == "placement_officer"
    assert users[f"admin.{tag}@college.example"]["is_me"] is True


def test_deactivation_rules_and_sign_in(college):
    tag = college["code"].lower()
    me = college["admin_id"]
    assert client.post(f"/api/v1/college/users/{me}/deactivate", headers=college["h"]).status_code == 409   # not yourself
    second = client.post("/api/v1/college/users", json={"name": "Second Admin", "email": f"second.{tag}@college.example",
                                                        "role": "college_admin"}, headers=college["h"]).json()
    assert client.post(f"/api/v1/college/users/{second['id']}/deactivate", headers=college["h"]).json()["is_active"] is False
    off = _login(f"second.{tag}@college.example", second["temporary_password"])
    assert off.status_code == 401 and "deactivated" in off.json()["detail"]
    # with the second admin inactive, the first is the last active admin: it can't be deactivated by the second either
    assert client.post(f"/api/v1/college/users/{second['id']}/reactivate", headers=college["h"]).json()["is_active"] is True
    assert _login(f"second.{tag}@college.example", second["temporary_password"]).status_code == 200
    # other colleges' users are not found
    assert client.post("/api/v1/college/users/usr_kavitha_01/deactivate", headers=college["h"]).status_code == 404
    db = SessionLocal()
    try:
        actions = set(db.execute(select(AuditLog.action).where(AuditLog.college_id == college["id"])).scalars())
        assert {"college.user_created", "college.user_deactivated", "college.user_reactivated", "auth.login_inactive"} <= actions
    finally:
        db.close()


def test_last_admin_cannot_be_deactivated(college):
    tag = college["code"].lower()
    other = client.post("/api/v1/college/users", json={"name": "Other Admin", "email": f"other.{tag}@college.example",
                                                       "role": "college_admin"}, headers=college["h"]).json()
    other_h = {"Authorization": "Bearer " + _login(f"other.{tag}@college.example", other["temporary_password"]).json()["access_token"]}
    assert client.post(f"/api/v1/college/users/{college['admin_id']}/deactivate", headers=other_h).status_code == 200
    # now 'other' is the only active admin; the first admin (inactive) can't be used, and other can't remove themselves
    assert client.post(f"/api/v1/college/users/{other['id']}/deactivate", headers=other_h).status_code == 409


def test_branding_validation(college):
    ok = client.put("/api/v1/college/settings/branding", json={"logo_url": "https://cdn.example/logo.png", "chat_retention_days": 180},
                    headers=college["h"])
    assert ok.json() == {"logo_url": "https://cdn.example/logo.png", "chat_retention_days": 180}
    assert client.put("/api/v1/college/settings/branding", json={"logo_url": "javascript:alert(1)", "chat_retention_days": 180},
                      headers=college["h"]).status_code == 422
    assert client.put("/api/v1/college/settings/branding", json={"logo_url": None, "chat_retention_days": 7},
                      headers=college["h"]).status_code == 422


def test_student_search_is_tenant_scoped(college):
    assert client.get("/api/v1/college/students?search=Priya", headers=college["h"]).json()["students"] == []
    demo = client.get("/api/v1/college/students?search=Priya", headers=KAVITHA).json()["students"]
    assert any(s["id"] == "std_priya_01" for s in demo)


@pytest.mark.link("L27")
def test_data_request_round_trip_02_to_48_and_back(college):
    h, tag = college["h"], college["code"].lower()
    br = client.post("/api/v1/college/branches", json={"name": "Computer Science", "code": "CSE"}, headers=h).json()["id"]
    client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "CSE-A", "semester": 4, "academic_year": "2026-27"}, headers=h)
    csv = ("register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone\n"
           f"R{tag}1,Nila V,nila.{tag}@stu.example,,CSE,CSE-A,4,,\n")
    client.post("/api/v1/college/students/import?dry_run=false", files={"file": ("s.csv", csv.encode(), "text/csv")}, headers=h)
    sid = client.get(f"/api/v1/college/students?search=R{tag}1", headers=h).json()["students"][0]["id"]

    rid = client.post("/api/v1/college/data-requests", json={"student_id": sid, "kind": "export",
                                                             "reason": "Student requested a copy of their data"}, headers=h).json()["id"]
    assert client.post(f"/api/v1/admin/data-requests/{rid}/complete", headers=STAFF).json()["status"] == "in_progress"
    outbox.dispatch_pending(SessionLocal, limit=100_000)
    mine = next(i for i in client.get("/api/v1/college/data-requests", headers=h).json()["items"] if i["id"] == rid)
    assert mine["status"] == "completed" and mine["has_export"]
    assert client.get(f"/api/v1/college/data-requests/{rid}/export", headers=h).json()["profile"]["name"] == "Nila V"


@pytest.mark.parametrize("headers", [
    {"Authorization": "Bearer " + create_access_token({"sub": "usr_arun_01", "role": "trainer", "college_id": "col_demo_001"})},
    {"Authorization": "Bearer " + create_access_token({"sub": "usr_ramesh_01", "role": "parent", "college_id": "col_demo_001"})},
    STAFF,
])
def test_only_college_admins(headers):
    assert client.get("/api/v1/college/settings", headers=headers).status_code == 403
    assert client.get("/api/v1/college/students?search=Priya", headers=headers).status_code == 403


def test_inactive_parent_gets_no_otp_login():
    db = SessionLocal()
    try:
        u = db.get(User, "usr_lakshmi_01")
        u.is_active = False
        db.commit()
        r = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543214"})
        assert r.status_code == 200 and "demo_otp" in r.json()        # same answer as an unknown number
        v = client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": r.json()["demo_otp"]})
        assert v.status_code == 404
    finally:
        u = db.get(User, "usr_lakshmi_01")
        u.is_active = True
        db.commit()
        db.close()
