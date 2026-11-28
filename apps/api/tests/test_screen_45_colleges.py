"""Screen 45 · Colleges and MoU terms (IREP staff). Spec: docs/screens/45-colleges-and-mou.md"""
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
from models.schema import Invitation, AuditLog, College, MouTerm, OutboxEvent, User

from tests.invite_helpers import set_password
client = TestClient(app)


def _h(sub, role, college_id):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
SUPER = _h("usr_irep_super_01", "super_admin", PLATFORM_TENANT)          # MoU terms and feature switches
KAVITHA = _h("usr_kavitha_01", "college_admin", "col_demo_001")
ARUN = _h("usr_arun_01", "trainer", "col_demo_001")


@pytest.fixture
def code():
    """A fresh college code; the college and its users are removed afterwards."""
    c = "T" + uuid.uuid4().hex[:7].upper()
    yield c
    db = SessionLocal()
    try:
        ids = list(db.execute(select(College.id).where(College.code == c)).scalars())
        if ids:
            db.execute(delete(MouTerm).where(MouTerm.college_id.in_(ids)))
            db.execute(delete(OutboxEvent).where(OutboxEvent.college_id.in_(ids)))
            db.execute(delete(Invitation).where(Invitation.college_id.in_(ids)))
            db.execute(delete(User).where(User.college_id.in_(ids)))
            db.execute(delete(College).where(College.id.in_(ids)))
            db.commit()
    finally:
        db.close()


def _create(code, **over):
    body = {"name": "Sri Test College of Engineering", "code": code, "city": "Madurai", "state": "Tamil Nadu", **over}
    return client.post("/api/v1/admin/colleges", json=body, headers=STAFF)


def _audit(college_id, action):
    db = SessionLocal()
    try:
        return db.execute(select(AuditLog).where(AuditLog.college_id == college_id, AuditLog.action == action)).scalars().all()
    finally:
        db.close()


def test_staff_create_and_list_a_college(code):
    r = _create(code.lower())
    assert r.status_code == 201 and r.json()["status"] == "onboarding"
    cid = r.json()["id"]
    row = next(c for c in client.get("/api/v1/admin/colleges", headers=STAFF).json()["colleges"] if c["id"] == cid)
    assert (row["code"], row["status"], row["students"], row["admins"], row["mou_ends_on"]) == (code, "onboarding", 0, 0, None)
    d = client.get(f"/api/v1/admin/colleges/{cid}", headers=STAFF).json()
    assert d["features"]["virtual_labs"] is True and d["features"]["cyber_range"] is False
    assert len(_audit(cid, "college.created")) == 1
    # the demo college is listed too, with its real student count
    demo = next(c for c in client.get("/api/v1/admin/colleges", headers=STAFF).json()["colleges"] if c["id"] == "col_demo_001")
    assert demo["students"] == 612


def test_duplicate_code_and_bad_input(code):
    assert _create(code).status_code == 201
    dup = _create(code.lower(), name="Another College")
    assert dup.status_code == 409 and code in dup.json()["detail"]
    assert _create("X").status_code == 422                      # code too short
    assert _create("BAD CODE!").status_code == 422
    assert _create(code + "Z", city="").status_code == 422


@pytest.mark.parametrize("headers", [KAVITHA, ARUN, _h("usr_priya_01", "student", "col_demo_001")])
def test_only_irep_staff(headers):
    assert client.get("/api/v1/admin/colleges", headers=headers).status_code == 403
    assert client.post("/api/v1/admin/colleges", json={"name": "Nope College", "code": "NOPE1", "city": "X1", "state": "Y1"},
                       headers=headers).status_code == 403


def test_mou_versions_and_activation(code):
    cid = _create(code).json()["id"]
    base = {"starts_on": "2026-12-01", "ends_on": "2027-11-30", "students_cap": 500}
    bad = client.post(f"/api/v1/admin/colleges/{cid}/mou", json={**base, "ends_on": "2026-11-01"}, headers=SUPER)
    assert bad.status_code == 422
    assert client.post(f"/api/v1/admin/colleges/{cid}/mou", json={**base, "students_cap": 0}, headers=SUPER).status_code == 422
    first = client.post(f"/api/v1/admin/colleges/{cid}/mou", json=base, headers=SUPER).json()
    assert first["status"] == "active"
    draft = client.post(f"/api/v1/admin/colleges/{cid}/mou", json={**base, "students_cap": 650, "activate": False}, headers=SUPER).json()
    assert draft["status"] == "draft"
    client.post(f"/api/v1/admin/colleges/{cid}/mou/{draft['id']}/activate", headers=SUPER)
    terms = {m["id"]: m["status"] for m in client.get(f"/api/v1/admin/colleges/{cid}", headers=STAFF).json()["mou_terms"]}
    assert terms == {first["id"]: "superseded", draft["id"]: "active"}
    assert len(_audit(cid, "mou.activated")) == 2
    # still onboarding: no college admin yet
    assert client.get(f"/api/v1/admin/colleges/{cid}", headers=STAFF).json()["college"]["status"] == "onboarding"


def test_feature_switches(code):
    cid = _create(code).json()["id"]
    r = client.put(f"/api/v1/admin/colleges/{cid}/features", json={"features": {"cyber_range": True}}, headers=SUPER)
    assert r.json()["features"]["cyber_range"] is True and r.json()["features"]["virtual_labs"] is True
    assert client.put(f"/api/v1/admin/colleges/{cid}/features", json={"features": {"teleport": True}}, headers=SUPER).status_code == 422
    assert _audit(cid, "college.features_changed")[0].detail == {"changed": {"cyber_range": True}}


def test_first_admin_signs_in_to_their_own_college_only(code):
    cid = _create(code).json()["id"]
    client.post(f"/api/v1/admin/colleges/{cid}/mou", json={"starts_on": "2026-12-01", "ends_on": "2027-11-30", "students_cap": 300}, headers=SUPER)
    email = f"coordinator.{code.lower()}@college.example"
    r = client.post(f"/api/v1/admin/colleges/{cid}/admins", json={"name": "Dr. Meera Iyer", "email": email}, headers=STAFF)
    assert r.status_code == 201 and r.json()["college_status"] == "active"
    temp = set_password(r.json())
    assert client.post(f"/api/v1/admin/colleges/{cid}/admins", json={"name": "Dup", "email": email.upper()}, headers=STAFF).status_code == 409

    login = client.post("/api/v1/auth/login", json={"role": "college", "identifier": email, "password": temp})
    assert login.status_code == 200 and login.json()["user"]["college_id"] == cid
    tok = {"Authorization": "Bearer " + login.json()["access_token"]}
    overview = client.get("/api/v1/college/overview", headers=tok).json()
    assert overview["kpis"]["students_enrolled"]["value"] == 0           # sees their (empty) college, not the demo one
    assert client.get("/api/v1/admin/colleges", headers=tok).status_code == 403
    db = SessionLocal()
    try:
        u = db.execute(select(User).where(User.email == email)).scalar_one()
        assert u.hashed_password != temp                                  # stored hashed only
    finally:
        db.close()
    assert len(_audit(cid, "college.admin_created")) == 1


def test_keycloak_mode_invites_through_the_outbox(code, monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "keycloak")
    # staff use a local token here only to reach the endpoint; keycloak mode accepts local tokens just for parents,
    # so call through the verifier-free path by swapping the dependency result
    from core import security
    app.dependency_overrides[security.get_current_user] = lambda: security.TokenPayload(
        sub="usr_irep_staff_01", role="irep_admin", college_id=PLATFORM_TENANT, name="IREP Staff")
    try:
        cid = client.post("/api/v1/admin/colleges", json={"name": "Keycloak Test College", "code": code, "city": "Salem", "state": "TN"}).json()["id"]
        r = client.post(f"/api/v1/admin/colleges/{cid}/admins", json={"name": "Anitha R", "email": f"anitha.{code.lower()}@college.example"})
        assert r.status_code == 201 and "temporary_password" not in r.json()
    finally:
        app.dependency_overrides.clear()
    db = SessionLocal()
    try:
        ev = db.execute(select(OutboxEvent).where(OutboxEvent.college_id == cid, OutboxEvent.event_type == "identity.invite_user")).scalar_one()
        assert ev.payload["user_id"] == r.json()["id"]
    finally:
        db.close()
