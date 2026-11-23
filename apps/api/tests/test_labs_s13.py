"""Labs track S13: exercise checkers (expected results stay on the server), cAdvisor metering,
spectate links on the class page. Spec: docs/labs/README.md"""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import LabSession
from services.lab_checkers import check
from services.lab_metering import CadvisorClient, meter

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN, MEENA = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer")


@pytest.fixture(autouse=True)
def restore():
    db = SessionLocal()
    try:
        for s in db.execute(select(LabSession).where(LabSession.student_id == "std_priya_01", LabSession.status.in_(["running", "starting"]))).scalars():
            s.status = "stopped"
        db.commit()
    finally:
        db.close()
    yield
    from seed.seed_lab_exercises import seed_lab_exercises
    from seed.seed_screen29 import seed_screen29
    db = SessionLocal()
    try:
        seed_screen29(db)
        seed_lab_exercises(db)
        db.commit()
    finally:
        db.close()


def test_sql_exercises_are_checked_on_the_server_without_revealing_answers():
    ex = client.get("/api/v1/student/labs/lab_sql_browser/exercises?lang=ta", headers=PRIYA).json()
    assert ex["kit"] == "sql" and len(ex["exercises"]) == 3 and ex["max_score"] == 35
    first = ex["exercises"][0]
    assert first["title"] == "அதிக மதிப்பெண் பெற்றவர்கள்" and "CREATE TABLE" in first["setup"]
    assert all(set(e) == {"id", "position", "title", "prompt", "setup", "points", "passed", "attempts"} for e in ex["exercises"])
    assert all("expected" not in e and "ordered" not in e for e in ex["exercises"])     # the answer never leaves the server
    assert client.post(f"/api/v1/student/lab-exercises/{first['id']}/check", json={"rows": [["Asha"]]}, headers=PRIYA).status_code == 409
    client.post("/api/v1/student/labs/lab_sql_browser/launch", headers=PRIYA)
    wrong = client.post(f"/api/v1/student/lab-exercises/{first['id']}/check", json={"rows": [["Asha"]]}, headers=PRIYA).json()
    assert wrong["passed"] is False and wrong["attempts"] == 1
    right = client.post(f"/api/v1/student/lab-exercises/{first['id']}/check", json={"rows": [["Meera"], ["Asha"]]}, headers=PRIYA).json()
    assert right["passed"] is True and right["points"] == 10                             # unordered exercise
    ranked = client.post("/api/v1/student/lab-exercises/lex_sql_3/check", json={"rows": [["Asha"], ["Meera"], ["Ravi"], ["Karthik"]]}, headers=PRIYA).json()
    assert ranked["passed"] is False                                                     # ordered exercise
    assert client.post("/api/v1/student/lab-exercises/lex_sql_2/check", json={"rows": [[2]]}, headers=PRIYA).json()["passed"] is True
    after = client.get("/api/v1/student/labs/lab_sql_browser/exercises", headers=PRIYA).json()
    assert after["score"] == 20
    progress = client.get("/api/v1/trainer/labs/exercises", headers=ARUN).json()
    row = next(e for e in progress["exercises"] if e["id"] == first["id"])
    assert row["passed"] >= 1 and row["tried"] >= 1
    assert client.get("/api/v1/trainer/labs/exercises", headers=PRIYA).status_code == 403
    assert client.get("/api/v1/student/labs/lab_nope/exercises", headers=PRIYA).status_code == 404


def test_python_checker_compares_output():
    client.post("/api/v1/student/labs/lab_python_browser/launch", headers=PRIYA)
    ok = client.post("/api/v1/student/lab-exercises/lex_py_2/check", json={"output": "1\n4\n9\n16\n25\n\n"}, headers=PRIYA).json()
    assert ok["passed"] is True
    assert check("python", ["55"], "54") is False and check("sql", [["1"]], "not rows") is False


def test_cadvisor_metering_marks_activity_and_records_peaks():
    sid = client.post("/api/v1/student/labs/lab_sql_browser/launch", headers=PRIYA).json()["session"]["id"]
    long_ago = datetime.datetime.now() - datetime.timedelta(minutes=25)
    db = SessionLocal()
    try:
        s = db.get(LabSession, sid)
        s.last_active_at, s.cpu_seconds = long_ago, 10.0
        db.commit()
    finally:
        db.close()

    def cadvisor(request):
        assert request.url.path == "/api/v1.3/docker"
        return httpx.Response(200, json={
            "/docker/abc": {"spec": {"labels": {"irep.session": sid}}, "stats": [
                {"cpu": {"usage": {"total": 30 * 10**9}}, "memory": {"usage": 512 * 1024 * 1024}}]},
            "/docker/other": {"spec": {"labels": {}}, "stats": [{"cpu": {"usage": {"total": 10**12}}, "memory": {"usage": 1}}]},
        })
    c = CadvisorClient(base_url="http://cadvisor:8080", client=httpx.Client(transport=httpx.MockTransport(cadvisor)))
    db = SessionLocal()
    try:
        out = meter(db, client=c)
        db.commit()
        s = db.get(LabSession, sid)
        assert out == {"sessions": 1, "active": 1} and s.cpu_seconds == 30.0 and s.mem_peak_mb == 512
        assert s.last_active_at > long_ago and s.metered_at is not None                   # CPU use counts as activity
        again = meter(db, client=c)                                                       # no new CPU: not active
        assert again["active"] == 0
    finally:
        db.close()
    db = SessionLocal()
    try:
        assert meter(db) == {"skipped": True} if not settings.LAB_METER_URL else True     # off without LAB_METER_URL
    finally:
        db.close()


def test_spectate_link_on_the_class_page(monkeypatch):
    monkeypatch.setattr(settings, "JUPYTERHUB_PUBLIC_URL", "https://labs.example.edu")
    url = "https://labs.example.edu/user/trainer/demo/lab?share=readonly"
    r = client.put("/api/v1/trainer/sessions/sess_thu_rag/spectate", json={"url": url, "label": "Arun's notebook"}, headers=ARUN)
    assert r.status_code == 200 and r.json()["spectate_url"] == url
    state = client.get("/api/v1/live/sess_thu_rag", headers=PRIYA).json()
    if state["meeting"]["state"] != "ended":
        assert state["spectate"] == {"url": url, "label": "Arun's notebook"}
    assert client.put("/api/v1/trainer/sessions/sess_thu_rag/spectate", json={"url": "https://evil.example.com/x"}, headers=ARUN).status_code == 422
    assert client.put("/api/v1/trainer/sessions/sess_thu_rag/spectate", json={"url": "http://labs.example.edu/x"}, headers=ARUN).status_code == 422
    assert client.put("/api/v1/trainer/sessions/sess_thu_rag/spectate", json={"url": url}, headers=MEENA).status_code == 404
    assert client.put("/api/v1/trainer/sessions/sess_thu_rag/spectate", json={"url": url}, headers=PRIYA).status_code == 403
    assert client.delete("/api/v1/trainer/sessions/sess_thu_rag/spectate", headers=ARUN).json()["spectate_url"] is None
    assert client.get("/api/v1/live/sess_thu_rag", headers=PRIYA).json()["spectate"] is None
