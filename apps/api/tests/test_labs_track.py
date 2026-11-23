"""Labs track (S9+): JupyterHub launcher behind the labs service, outbox start/stop,
hardened docker args, browser labs with signed beacons, external sandbox, trainer lab board.
JupyterHub is mocked (httpx.MockTransport). Spec: docs/labs/README.md"""
import datetime
import json
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import AuditLog, LabSession, Notification, OutboxEvent, VirtualLabItem
from services import lab_orchestrator as lo

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN, MEENA = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer")


class FakeHub:
    """Records JupyterHub REST calls and answers like JupyterHub 5."""

    def __init__(self):
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.calls.append((request.method, request.url.path, body, request.headers.get("authorization")))
        if request.method == "POST" and request.url.path.endswith("/tokens"):
            return httpx.Response(201, json={"token": "tok123"})
        if request.method == "POST" and "/servers/" in request.url.path:
            return httpx.Response(202)
        if request.method == "POST":
            return httpx.Response(201, json={})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404)


@pytest.fixture
def hub(monkeypatch):
    fake = FakeHub()
    adapter = lo.JupyterHubAdapter(base_url="http://hub:8000", token="svc-token", public_url="https://labs.example",
                                   client=httpx.Client(transport=httpx.MockTransport(fake)))
    monkeypatch.setattr(lo, "get_lab_adapter", lambda isolated=False: adapter)
    return fake


@pytest.fixture(autouse=True)
def priya_free():
    """Pause Priya's seeded demo session so she can launch; re-seed restores it."""
    db = SessionLocal()
    try:
        for s in db.execute(select(LabSession).where(LabSession.student_id == "std_priya_01", LabSession.status.in_(["running", "starting"]))).scalars():
            s.status = "stopped"
        db.commit()
    finally:
        db.close()
    yield
    from seed.seed_screen29 import seed_screen29
    db = SessionLocal()
    try:
        seed_screen29(db)
        db.commit()
    finally:
        db.close()


def _run_outbox(event_type, session_id):
    db = SessionLocal()
    try:
        ev = db.execute(select(OutboxEvent).where(OutboxEvent.event_type == event_type, OutboxEvent.entity_id == session_id)
                        .order_by(OutboxEvent.created_at.desc())).scalars().first()
        assert ev is not None, f"{event_type} not queued"
        {"lab.start": lo._start_server, "lab.stop": lo._stop_server}[event_type](db, ev)
        db.commit()
    finally:
        db.close()


def test_server_lab_starts_through_the_outbox_and_opens_with_a_scoped_token(hub):
    r = client.post("/api/v1/student/labs/lab_linux/launch", headers=PRIYA)
    assert r.status_code == 200, r.text
    sid = r.json()["session"]["id"]
    assert r.json()["session"]["status"] == "starting" and hub.calls == []          # nothing external inside the request
    assert client.get(f"/api/v1/student/lab-sessions/{sid}/connect", headers=PRIYA).status_code == 409

    _run_outbox("lab.start", sid)
    user = lo.hub_username("col_demo_001", "std_priya_01")
    assert "priya" not in user and "std_" not in user                               # a pseudonym, no names or ids
    (m1, p1, _, auth), (m2, p2, b2, _) = hub.calls[:2]
    assert (m1, p1) == ("POST", f"/hub/api/users/{user}") and auth == "token svc-token"
    assert m2 == "POST" and p2 == f"/hub/api/users/{user}/servers/{lo.hub_server_name(sid)}" and b2["profile"] == "linux"

    url = client.get(f"/api/v1/student/lab-sessions/{sid}/connect", headers=PRIYA).json()["url"]
    assert url == f"https://labs.example/user/{user}/{lo.hub_server_name(sid)}/?token=tok123"
    token_call = hub.calls[-1]
    assert token_call[2]["scopes"] == [f"access:servers!server={user}/{lo.hub_server_name(sid)}"] and 0 < token_call[2]["expires_in"] <= 120 * 60 + 60

    assert client.post(f"/api/v1/student/lab-sessions/{sid}/stop", headers=PRIYA).status_code == 200
    _run_outbox("lab.stop", sid)
    assert hub.calls[-1][0] == "DELETE" and hub.calls[-1][2] == {"remove": True}
    _run_outbox("lab.start", sid)                                                   # a late re-run does not restart it
    assert hub.calls[-1][0] == "DELETE"
    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "lab.connect", AuditLog.entity_id == sid)).first()
    finally:
        db.close()


def test_a_server_that_never_starts_is_failed_and_frees_the_student(hub):
    sid = client.post("/api/v1/student/labs/lab_linux/launch", headers=PRIYA).json()["session"]["id"]
    db = SessionLocal()
    try:
        s = db.get(LabSession, sid)
        lo.cull(db, "col_demo_001", now=s.started_at + datetime.timedelta(minutes=lo.START_TIMEOUT_MIN + 1))
        db.commit()
        assert db.get(LabSession, sid).status == "failed"
    finally:
        db.close()
    assert client.post("/api/v1/student/labs/lab_linux/launch", headers=PRIYA).status_code == 200


def test_docker_dev_adapter_is_hardened():
    db = SessionLocal()
    try:
        lab = db.get(VirtualLabItem, "lab_linux")
        cyber = db.get(VirtualLabItem, "lab_cyber_range")
    finally:
        db.close()
    s = LabSession(id="ls_test", college_id="col_demo_001", student_id="std_priya_01", lab_id="lab_linux")
    args = lo.docker_run_args(s, lab)
    for flag in (["--network", "none"], ["--cap-drop", "ALL"], ["--security-opt", "no-new-privileges"], ["--pids-limit", "256"],
                 ["--user", "1000:1000"], ["--memory", "1g"]):
        i = args.index(flag[0])
        assert args[i + 1] == flag[1]
    assert "--read-only" in args and "--privileged" not in args
    assert lo.docker_run_args(s, cyber)[lo.docker_run_args(s, cyber).index("--network") + 1] == "irep-cyber-range"


def test_browser_lab_runs_now_and_is_kept_alive_by_signed_beacons():
    r = client.post("/api/v1/student/labs/lab_sql_browser/launch", headers=PRIYA).json()["session"]
    assert r["status"] == "running" and r["runtime"] == "browser" and r["browser_kit"] == "sql" and r["beacon_token"]
    token = r["beacon_token"]
    db = SessionLocal()
    try:
        s = db.get(LabSession, r["id"])
        s.last_active_at = datetime.datetime.now() - datetime.timedelta(minutes=10)
        db.commit()
    finally:
        db.close()
    b = client.post("/api/v1/labs/beacon", content=json.dumps({"token": token}), headers={"Content-Type": "text/plain"})   # sendBeacon
    assert b.status_code == 200 and b.json()["status"] == "running"
    db = SessionLocal()
    try:
        assert (datetime.datetime.now() - db.get(LabSession, r["id"]).last_active_at).total_seconds() < 5
    finally:
        db.close()
    assert client.post("/api/v1/labs/beacon", json={"token": token + "x"}).status_code == 401
    assert client.post("/api/v1/labs/beacon", json={"token": PRIYA["Authorization"][7:]}).status_code == 401      # an access token is not a beacon
    assert client.get("/api/v1/student/labs", headers={"Authorization": f"Bearer {token}"}).status_code == 401       # and a beacon is not an access token
    assert client.get(f"/api/v1/student/lab-sessions/{r['id']}/connect", headers=PRIYA).status_code == 409           # runs in the page
    client.post(f"/api/v1/student/lab-sessions/{r['id']}/stop", headers=PRIYA)
    assert client.post("/api/v1/labs/beacon", json={"token": token}).json()["status"] == "stopped"


def test_external_sandbox_opens_the_colleges_link():
    sid = client.post("/api/v1/student/labs/lab_cloud/launch", headers=PRIYA).json()["session"]["id"]
    assert client.get(f"/api/v1/student/lab-sessions/{sid}/connect", headers=PRIYA).json()["url"] == "https://awsacademy.instructure.com/"


def test_trainer_lab_board_and_stop():
    sid = client.post("/api/v1/student/labs/lab_python_browser/launch", headers=PRIYA).json()["session"]["id"]
    board = client.get("/api/v1/trainer/labs", headers=ARUN).json()
    row = next(r for r in board["sessions"] if r["id"] == sid)
    assert row["student"] == "Priya R" and row["lab"] == "Python Playground" and board["summary"]["live"] >= 1
    assert all(r["id"] != sid for r in client.get("/api/v1/trainer/labs", headers=MEENA).json()["sessions"])
    assert client.post(f"/api/v1/trainer/lab-sessions/{sid}/stop", json={}, headers=MEENA).status_code == 404
    assert client.get("/api/v1/trainer/labs", headers=PRIYA).status_code == 403
    out = client.post(f"/api/v1/trainer/lab-sessions/{sid}/stop", json={"reason": "Class is over"}, headers=ARUN)
    assert out.status_code == 200 and out.json()["status"] == "stopped"
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_priya_01", Notification.kind == "lab",
                                                     Notification.body_en == "Class is over")).first()
        assert db.execute(select(AuditLog).where(AuditLog.action == "lab.stop_by_trainer", AuditLog.entity_id == sid)).first()
    finally:
        db.close()
