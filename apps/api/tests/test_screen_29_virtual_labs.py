"""Screen 29 Virtual Labs: entitlement, approval gate, one running lab, quota, culler, tenant/role."""
import datetime
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete, func

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import LabSession, LabApproval, UsageLedger, Student, User, VirtualLabItem
from services.lab_orchestrator import cull, lock_reason, IDLE_LIMIT_MIN
from seed.seed_screen29 import seed_screen29

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Priya R"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


PRIYA = _token("usr_priya_01", "student")
ARUN = _token("usr_arun_01", "trainer", name="Arun Kumar")


@pytest.fixture(autouse=True)
def demo_state():
    db = SessionLocal()
    try:
        seed_screen29(db)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.execute(delete(UsageLedger).where(UsageLedger.student_id == "std_priya_01", UsageLedger.ref_type == "test"))
        seed_screen29(db)
        db.commit()
    finally:
        db.close()


def _lab(d, lab_id):
    return next(l for l in d["labs"] if l["id"] == lab_id)


def test_catalog_matches_pdf5_state():
    d = client.get("/api/v1/student/labs", headers=PRIYA).json()
    assert [l["name"] for l in d["labs"]] == ["Linux Sandbox", "Docker & Kubernetes Lab", "Cloud Sandbox", "AI Notebook Lab", "Cyber Range", "Full-Stack Workspace",
                                                 "SQL Playground", "Python Playground"]   # PDF 5 order, then the browser labs
    assert [c["label"] for c in _lab(d, "lab_cloud")["chips"]] == ["Sem 5+", "Credits: 68%"]
    assert _lab(d, "lab_docker_k8s")["footer"] == "Last used: yesterday"
    assert [c["label"] for c in _lab(d, "lab_ai_notebook")["chips"]] == ["AI & DS", "Ready"]
    cyber = _lab(d, "lab_cyber_range")
    assert cyber["action"] == "request" and cyber["footer"] == "Trainer approval needed"
    assert [c["label"] for c in cyber["chips"]] == ["Cybersecurity", "Track access"]
    act = d["active_sessions"][0]
    assert act["lab_name"] == "AI Notebook Lab" and act["workspace_file"] == "rag_notes_demo.ipynb" and act["running_minutes"] == 38
    assert d["usage"]["cloud_credits_left_pct"] == 68


def test_one_running_lab_then_stop_records_usage():
    r = client.post("/api/v1/student/labs/lab_linux/launch", headers=PRIYA)
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "already_running"
    assert client.post("/api/v1/student/lab-sessions/ls_demo_priya_notebook/stop", headers=PRIYA).json()["minutes"] == 38
    r = client.post("/api/v1/student/labs/lab_linux/launch", headers=PRIYA)
    assert r.status_code == 200
    sess = r.json()["session"]
    assert sess["lab_name"] == "Linux Sandbox" and sess["status"] == "running" and sess["open_url"].startswith("/lab/")
    assert client.post(f"/api/v1/student/lab-sessions/{sess['id']}/heartbeat", headers=PRIYA).status_code == 200
    assert client.get(f"/api/v1/student/lab-sessions/{sess['id']}", headers=PRIYA).json()["status"] == "running"
    db = SessionLocal()
    try:
        ledger = db.execute(select(UsageLedger).filter_by(ref_id="ls_demo_priya_notebook")).scalars().all()
        assert len(ledger) == 1 and ledger[0].kind == "lab_minutes" and ledger[0].amount == 38
    finally:
        db.close()


@pytest.mark.link("L08")
def test_cyber_range_approval_gate():
    r = client.post("/api/v1/student/labs/lab_cyber_range/launch", headers=PRIYA)
    assert r.status_code == 403 and r.json()["detail"]["reason"] == "approval"
    assert client.post("/api/v1/student/labs/lab_cyber_range/request-access", json={"accept_aup": False}, headers=PRIYA).status_code == 422
    req = client.post("/api/v1/student/labs/lab_cyber_range/request-access", json={"accept_aup": True}, headers=PRIYA)
    assert req.json()["status"] == "pending"
    d = client.get("/api/v1/student/labs", headers=PRIYA).json()
    assert _lab(d, "lab_cyber_range")["action"] == "pending" and _lab(d, "lab_cyber_range")["footer"] == "Request pending"

    pending = client.get("/api/v1/trainer/approvals/labs", headers=ARUN).json()["approvals"]
    ap = next(a for a in pending if a["student_name"] == "Priya R" and a["lab_id"] == "lab_cyber_range")
    assert ap["aup_accepted"] is True
    # another trainer without Priya's batch cannot decide; deny needs a reason
    assert client.post(f"/api/v1/trainer/approvals/labs/{ap['id']}", json={"decision": "approve"}, headers=_token("usr_meena_01", "trainer", name="Meena S")).status_code == 404
    assert client.post(f"/api/v1/trainer/approvals/labs/{ap['id']}", json={"decision": "deny"}, headers=ARUN).status_code == 422
    assert client.post(f"/api/v1/trainer/approvals/labs/{ap['id']}", json={"decision": "approve"}, headers=ARUN).json()["status"] == "approved"
    assert client.post(f"/api/v1/trainer/approvals/labs/{ap['id']}", json={"decision": "approve"}, headers=ARUN).status_code == 409

    client.post("/api/v1/student/lab-sessions/ls_demo_priya_notebook/stop", headers=PRIYA)
    r = client.post("/api/v1/student/labs/lab_cyber_range/launch", headers=PRIYA)
    assert r.status_code == 200 and r.json()["session"]["lab_name"] == "Cyber Range"


def test_semester_and_track_locks():
    db = SessionLocal()
    try:
        lab_cloud = db.execute(select(VirtualLabItem).filter_by(id="lab_cloud")).scalar_one()
        lab_nb = db.execute(select(VirtualLabItem).filter_by(id="lab_ai_notebook")).scalar_one()
        sem3 = db.execute(select(Student).where(Student.semester == 3, Student.track == "Software Engineering")).scalars().first()
        now = datetime.datetime.now()
        assert lock_reason(db, sem3, lab_cloud, now)[0] == "semester"
        assert lock_reason(db, sem3, lab_nb, now)[0] == "track"
        user = db.execute(select(User).filter_by(id=sem3.user_id)).scalar_one()
    finally:
        db.close()
    r = client.post("/api/v1/student/labs/lab_cloud/launch", headers=_token(user.id, "student", name=user.name))
    assert r.status_code == 403 and r.json()["detail"]["reason"] == "semester"
    assert "Semester 5" in r.json()["detail"]["message"]


def test_exhausted_quota_blocks_with_clear_message():
    from services.quotas import lab_minutes_per_student
    db = SessionLocal()
    try:
        quota = lab_minutes_per_student(db, "col_demo_001")              # from the active MoU (L36)
        db.add(UsageLedger(id="ul_test_quota", college_id="col_demo_001", student_id="std_priya_01", kind="lab_minutes",
                           amount=quota, period=datetime.datetime.now().strftime("%Y-%m"), ref_type="test"))
        db.commit()
    finally:
        db.close()
    client.post("/api/v1/student/lab-sessions/ls_demo_priya_notebook/stop", headers=PRIYA)
    r = client.post("/api/v1/student/labs/lab_linux/launch", headers=PRIYA)
    assert r.status_code == 403 and r.json()["detail"]["reason"] == "quota"
    assert f"{quota} lab minutes" in r.json()["detail"]["message"]
    d = client.get("/api/v1/student/labs", headers=PRIYA).json()
    assert _lab(d, "lab_linux")["locked"]["reason"] == "quota"
    # cloud credits are metered separately and still allowed
    assert client.post("/api/v1/student/labs/lab_cloud/launch", headers=PRIYA).status_code == 200


def test_idle_and_expired_sessions_are_culled():
    db = SessionLocal()
    try:
        s = db.execute(select(LabSession).filter_by(id="ls_demo_priya_notebook")).scalar_one()
        now = s.last_active_at + datetime.timedelta(minutes=IDLE_LIMIT_MIN + 1)
        assert cull(db, "col_demo_001", now) >= 1
        assert s.status == "expired" and s.stop_reason == "idle"
        db.commit()
    finally:
        db.close()
    assert client.get("/api/v1/student/labs", headers=PRIYA).json()["active_sessions"] == []


def test_guards():
    assert client.get("/api/v1/student/labs", headers=_token("usr_ramesh_01", "parent")).status_code == 403
    assert client.get("/api/v1/student/labs", headers=_token("usr_priya_01", "student", college_id="col_other_999")).status_code == 404
    db = SessionLocal()
    try:
        karthik = db.execute(select(User).filter_by(name="Karthik S")).scalars().first()
    finally:
        db.close()
    other = _token(karthik.id, "student", name="Karthik S")
    assert client.post("/api/v1/student/lab-sessions/ls_demo_priya_notebook/stop", headers=other).status_code == 404
    assert client.get("/api/v1/student/lab-sessions/ls_demo_priya_notebook", headers=other).status_code == 404
