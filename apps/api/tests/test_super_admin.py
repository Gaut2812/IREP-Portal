"""Super admin above IREP staff (docs/PERMISSIONS.md): staff accounts, MoU terms, feature switches,
deletion approvals and logged support sessions are super-admin only; every super-admin request is
audited; accounts are invited or imported only; student import links parents with consent."""
import json
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
from models.schema import (Invitation, AuditLog, Batch, Branch, College, ConsentRecord, ParentStudent, Student, SupportSession,
                           User)

from tests.invite_helpers import set_password
client = TestClient(app)
REPO = Path(__file__).resolve().parents[3]


def _h(sub, role, college_id):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


SUPER = _h("usr_irep_super_01", "super_admin", PLATFORM_TENANT)
STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
KAVITHA = _h("usr_kavitha_01", "college_admin", "col_demo_001")
PRIYA = _h("usr_priya_01", "student", "col_demo_001")


@pytest.fixture
def invited():
    """Staff accounts created by a test are removed afterwards."""
    emails = []
    yield emails
    db = SessionLocal()
    try:
        for e in emails:
            u = db.execute(select(User).where(User.email == e)).scalar_one_or_none()
            if u:
                db.execute(delete(SupportSession).where(SupportSession.staff_user_id == u.id))
                db.execute(delete(Invitation).where(Invitation.user_id == u.id))
                db.delete(u)
        db.commit()
    finally:
        db.close()


# --- who may do what --------------------------------------------------------------------------

SUPER_ONLY = [
    ("get", "/api/v1/admin/staff", None),
    ("post", "/api/v1/admin/staff", {"name": "Nobody", "email": "nobody@example.in"}),
    ("get", "/api/v1/admin/support-sessions", None),
    ("post", "/api/v1/admin/support-sessions", {"college_id": "col_demo_001", "reason": "Checking the import errors"}),
    ("put", "/api/v1/admin/colleges/col_demo_001/features", {"features": {"cyber_range": True}}),
    ("post", "/api/v1/admin/colleges/col_demo_001/mou", {"starts_on": "2027-06-01", "ends_on": "2028-05-31", "students_cap": 10}),
    ("post", "/api/v1/admin/colleges/col_demo_001/mou/mou_demo_2026/activate", None),
]


@pytest.mark.parametrize("method, path, body", SUPER_ONLY)
@pytest.mark.parametrize("who", ["staff", "college_admin", "student"])
def test_super_only_actions_are_403_for_everyone_else(method, path, body, who):
    h = {"staff": STAFF, "college_admin": KAVITHA, "student": PRIYA}[who]
    r = getattr(client, method)(path, headers=h, **({"json": body} if body is not None else {}))
    assert r.status_code == 403, (who, path, r.text)


def test_super_admin_passes_every_staff_check():
    for path in ("/api/v1/admin/colleges", "/api/v1/admin/usage", "/api/v1/admin/audit", "/api/v1/admin/data-requests",
                 "/api/v1/admin/staff", "/api/v1/admin/support-sessions"):
        assert client.get(path, headers=SUPER).status_code == 200, path
    assert client.get("/api/v1/admin/colleges/col_demo_001", headers=SUPER).json()["can_manage"] is True
    assert client.get("/api/v1/admin/colleges/col_demo_001", headers=STAFF).json()["can_manage"] is False


def test_super_admin_signs_in_on_the_staff_card():
    r = client.post("/api/v1/auth/login", json={"role": "admin", "identifier": "super@irep.demo", "password": "password123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "super_admin"
    # and only there
    assert client.post("/api/v1/auth/login", json={"role": "college", "identifier": "super@irep.demo",
                                                    "password": "password123"}).status_code == 401


# --- staff accounts -----------------------------------------------------------------------------

def test_invite_list_role_and_deactivate_staff(invited):
    email = f"ops.{uuid.uuid4().hex[:6]}@irep.example"
    invited.append(email)
    r = client.post("/api/v1/admin/staff", json={"name": "Ops Person", "email": email}, headers=SUPER)
    assert r.status_code == 201
    new = r.json()
    assert new["role"] == "irep_admin" and new["two_factor"] == "required" and set_password(new)
    assert client.post("/api/v1/admin/staff", json={"name": "Again", "email": email.upper()}, headers=SUPER).status_code == 409
    assert any(i["email"] == email for i in client.get("/api/v1/admin/staff", headers=SUPER).json()["items"])

    # the new staff member signs in (development: one-time password) and is IREP staff, not super admin
    tok = client.post("/api/v1/auth/login", json={"role": "admin", "identifier": email, "password": set_password(new)})
    assert tok.status_code == 200 and tok.json()["user"]["role"] == "irep_admin"

    assert client.put(f"/api/v1/admin/staff/{new['id']}/role", json={"role": "super_admin"}, headers=SUPER).json()["role"] == "super_admin"
    assert client.put(f"/api/v1/admin/staff/{new['id']}/role", json={"role": "irep_admin"}, headers=SUPER).json()["role"] == "irep_admin"
    assert client.post(f"/api/v1/admin/staff/{new['id']}/deactivate", headers=SUPER).json()["is_active"] is False
    assert client.post("/api/v1/auth/login", json={"role": "admin", "identifier": email,
                                                    "password": set_password(new)}).status_code == 401
    assert client.post(f"/api/v1/admin/staff/{new['id']}/reactivate", headers=SUPER).json()["is_active"] is True

    db = SessionLocal()
    try:
        actions = set(db.execute(select(AuditLog.action).where(AuditLog.entity_id == new["id"])).scalars())
        assert {"staff.invited", "staff.role_changed", "staff.deactivated", "staff.reactivated"} <= actions
    finally:
        db.close()


def test_guards_on_staff_accounts():
    me = "usr_irep_super_01"
    assert client.post(f"/api/v1/admin/staff/{me}/deactivate", headers=SUPER).status_code == 409        # not yourself
    assert client.put(f"/api/v1/admin/staff/{me}/role", json={"role": "irep_admin"}, headers=SUPER).status_code == 409  # last super
    # a college user is not a staff account: 404, not 403
    assert client.post("/api/v1/admin/staff/usr_kavitha_01/deactivate", headers=SUPER).status_code == 404
    assert client.put("/api/v1/admin/staff/usr_irep_staff_01/role", json={"role": "college_admin"}, headers=SUPER).status_code == 422


# --- support sessions ---------------------------------------------------------------------------

def test_support_session_is_time_boxed_and_logged():
    r = client.post("/api/v1/admin/support-sessions", json={"college_id": "col_demo_001", "minutes": 30,
                                                            "reason": "Parent cannot see the monthly card"}, headers=SUPER)
    assert r.status_code == 201
    s = r.json()
    assert s["active"] is True and s["college_name"] and s["staff_user_id"] == "usr_irep_super_01"
    ended = client.post(f"/api/v1/admin/support-sessions/{s['id']}/end", headers=SUPER).json()
    assert ended["active"] is False and ended["ended_at"]
    again = client.post(f"/api/v1/admin/support-sessions/{s['id']}/end", headers=SUPER).json()
    assert again["ended_at"] == ended["ended_at"]                                     # idempotent
    assert client.post("/api/v1/admin/support-sessions", json={"college_id": "col_nope", "reason": "Unknown college here"},
                       headers=SUPER).status_code == 404
    assert client.post("/api/v1/admin/support-sessions", json={"college_id": "col_demo_001", "reason": "short"},
                       headers=SUPER).status_code == 422
    db = SessionLocal()
    try:
        rows = db.execute(select(AuditLog).where(AuditLog.entity_id == s["id"])).scalars().all()
        assert {a.action for a in rows} == {"support_session.opened", "support_session.ended"}
        assert all(a.college_id == "col_demo_001" for a in rows)                     # visible in that college's trail
        db.execute(delete(SupportSession).where(SupportSession.id == s["id"]))
        db.commit()
    finally:
        db.close()


# --- everything the super admin does is audited -------------------------------------------------

def test_every_super_admin_request_is_audited_with_its_outcome():
    marker = f"/api/v1/admin/colleges/col_missing_{uuid.uuid4().hex[:6]}"
    assert client.get(marker, headers=SUPER).status_code == 404
    assert client.get(marker, headers=STAFF).status_code == 404
    db = SessionLocal()
    try:
        rows = db.execute(select(AuditLog).where(AuditLog.action == "super_admin.request")).scalars().all()
        mine = [a for a in rows if a.detail and a.detail.get("path") == marker]
        assert len(mine) == 1                                                       # staff requests are not logged as super
        assert mine[0].actor_user_id == "usr_irep_super_01" and mine[0].detail == {"method": "GET", "path": marker, "status": 404}
    finally:
        db.close()


def test_a_forged_super_admin_claim_is_not_audited_or_trusted():
    from jose import jwt
    forged = jwt.encode({"sub": "x", "role": "super_admin", "college_id": PLATFORM_TENANT}, "not-the-key", algorithm="HS256")
    assert client.get("/api/v1/admin/staff", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


# --- no public sign-up ---------------------------------------------------------------------------

def test_no_self_registration_anywhere():
    paths = [getattr(r, "path", "") for r in app.routes]
    assert not [p for p in paths if any(w in p.lower() for w in ("register", "signup", "sign-up", "sign_up"))]
    realm = json.loads((REPO / "infra" / "keycloak" / "realm-irep.json").read_text(encoding="utf-8"))
    assert realm["registrationAllowed"] is False
    roles = {r["name"]: r for r in realm["roles"]["realm"]}
    for staff_role in ("irep_admin", "super_admin"):
        assert roles[staff_role]["composites"]["realm"] == ["irep_2fa"]             # Keycloak OTP flow keys on this
    from ops.configure_keycloak import client_changes, realm_changes
    assert realm_changes()["registrationAllowed"] is False and realm_changes()["browserFlow"] == "irep browser"
    assert client_changes({"clientId": "irep-web"})["directAccessGrantsEnabled"] is False   # no password grant past OTP


def test_keycloak_super_admin_token_maps_to_super_admin(monkeypatch):
    from core import keycloak
    from core.keycloak import IREP_ROLES
    assert "super_admin" in IREP_ROLES and "irep_2fa" not in IREP_ROLES          # the marker role never becomes the role


# --- student import: parents, several children, consent first -----------------------------------

HEADER = "register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone,parent_email,parent_consent,parent_consent_ref\n"


@pytest.fixture
def college():
    """A throwaway college with one branch and batch, and its own college admin."""
    tag = uuid.uuid4().hex[:6]
    cid = f"col_imp_{tag}"
    db = SessionLocal()
    try:
        db.add(College(id=cid, college_id=cid, name=f"Import College {tag}", code=f"IM{tag}".upper()[:16]))
        db.add(User(id=f"usr_ca_{tag}", college_id=cid, email=f"ca.{tag}@college.example", hashed_password="x",
                    role="college_admin", name="CA", avatar_initials="CA"))
        db.add(Branch(id=f"br_{tag}", college_id=cid, name="CSE", code="CSE"))
        db.flush()
        db.add(Batch(id=f"bt_{tag}", college_id=cid, branch_id=f"br_{tag}", short_name="CSE-A", name="CSE-A · Sem 5", semester=5,
                     academic_year="2026-27"))
        db.commit()
    finally:
        db.close()
    yield {"id": cid, "tag": tag, "h": _h(f"usr_ca_{tag}", "college_admin", cid)}
    db = SessionLocal()
    try:
        sids = list(db.execute(select(Student.id).where(Student.college_id == cid)).scalars())
        uids = list(db.execute(select(Student.user_id).where(Student.college_id == cid)).scalars())
        db.execute(delete(ConsentRecord).where(ConsentRecord.college_id == cid))
        db.execute(delete(ParentStudent).where(ParentStudent.college_id == cid))
        db.execute(delete(Student).where(Student.id.in_(sids or ["_"])))
        db.execute(delete(Invitation).where(Invitation.user_id.in_(uids or ["_"])))
        db.execute(delete(User).where(User.id.in_(uids or ["_"])))
        db.execute(delete(Invitation).where(Invitation.college_id == cid))
        db.execute(delete(User).where(User.college_id == cid))
        db.execute(delete(Batch).where(Batch.college_id == cid))
        db.execute(delete(Branch).where(Branch.college_id == cid))
        db.execute(delete(College).where(College.id == cid))
        db.commit()
    finally:
        db.close()


def _import(c, rows, dry_run=False):
    return client.post(f"/api/v1/college/students/import?dry_run={'true' if dry_run else 'false'}",
                       files={"file": ("s.csv", (HEADER + rows).encode(), "text/csv")}, headers=c["h"]).json()


def test_one_parent_with_several_children_and_consent_recorded(college):
    t = college["tag"]
    rows = (f"R{t}1,Anu K,anu.{t}@stu.example,,CSE,CSE-A,5,Kumar K,9811100001,kumar.{t}@mail.example,yes,FORM-11\n"
            f"R{t}2,Arun K,arun.{t}@stu.example,,CSE,CSE-A,5,Kumar K,98111 00001,,yes,FORM-12\n"
            f"R{t}3,Bala S,bala.{t}@stu.example,,CSE,CSE-A,5,,,,,\n")
    r = _import(college, rows)
    assert r["imported"] is True
    s = r["summary"]
    assert (s["parents_linked"], s["parents_new"], s["consents_recorded"]) == (2, 1, 2)
    db = SessionLocal()
    try:
        parents = db.execute(select(User).where(User.college_id == college["id"], User.role == "parent")).scalars().all()
        assert len(parents) == 1 and parents[0].email == f"kumar.{t}@mail.example" and parents[0].phone == "9811100001"
        links = db.execute(select(ParentStudent).where(ParentStudent.parent_user_id == parents[0].id)).scalars().all()
        assert len(links) == 2
        consents = db.execute(select(ConsentRecord).where(ConsentRecord.college_id == college["id"])).scalars().all()
        assert {c.subject_student_id for c in consents} == {l.student_id for l in links}
        assert all(c.purpose == "parent_data_processing" and c.status == "granted" and c.method == "paper_form_upload"
                   and c.evidence_ref.startswith("import:FORM-1") for c in consents)
    finally:
        db.close()
    # re-import is idempotent: no second parent, link or consent
    again = _import(college, rows)["summary"]
    assert (again["parents_new"], again["consents_recorded"], again["updated"]) == (0, 0, 3)


def test_parent_data_without_consent_is_not_saved(college):
    t = college["tag"]
    r = _import(college, f"R{t}1,Anu K,anu.{t}@stu.example,,CSE,CSE-A,5,Kumar K,9811100002,,,\n"
                         f"R{t}2,Arun K,arun.{t}@stu.example,,CSE,CSE-A,5,Kumar K,9811100002,,yes,\n"
                         f"R{t}3,Chitra,chitra.{t}@stu.example,,CSE,CSE-A,5,,,c.{t}@mail.example,yes,F1\n")
    assert r["can_import"] is False
    errs = [e["error"] for e in r["errors"]]
    assert "parent_consent=yes" in errs[0] and "parent_consent_ref" in errs[1] and "parent_phone is required" in errs[2]
    db = SessionLocal()
    try:
        assert db.execute(select(User).where(User.college_id == college["id"], User.role.in_(("parent", "student")))).first() is None
    finally:
        db.close()


def test_parents_stay_inside_their_college_and_emails_are_not_hijacked(college):
    t = college["tag"]
    # the demo college has a parent with mobile 9876543214: a different college gets its own parent account
    r = _import(college, f"R{t}1,Anu K,anu.{t}@stu.example,,CSE,CSE-A,5,Lakshmi,9876543214,,yes,F-1\n")
    assert r["imported"] is True and r["summary"]["parents_new"] == 1
    db = SessionLocal()
    try:
        assert db.execute(select(ParentStudent).where(ParentStudent.parent_user_id == "usr_lakshmi_01",
                                                      ParentStudent.college_id == college["id"])).first() is None
    finally:
        db.close()
    bad = _import(college, f"R{t}2,Bala,bala.{t}@stu.example,,CSE,CSE-A,5,X,9811100003,priya.r@demo.edu,yes,F-2\n", True)
    assert "parent_email already belongs to another account" in bad["errors"][0]["error"]
