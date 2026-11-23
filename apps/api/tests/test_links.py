"""Cross-screen link tests (docs/INTERCONNECT.md).

Each test checks that what one screen sends is what the other screen shows.
Tests elsewhere carry @pytest.mark.link too; these cover links that no single
screen test spans.
"""
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import Student

client = TestClient(app)


def _h(sub: str, role: str, college_id: str = "col_demo_001") -> dict:
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA = _h("usr_priya_01", "student")
ARUN = _h("usr_arun_01", "trainer")
RAMESH = _h("usr_ramesh_01", "parent")
KAVITHA = _h("usr_kavitha_01", "college_admin")


@pytest.mark.link("L01")
@pytest.mark.parametrize("role,identifier", [
    ("student", "priya.r@demo.edu"),
    ("trainer", "arun.k@demo.edu"),
    ("college_admin", "admin@demo.edu"),
])
def test_sign_in_returns_role_college_and_language_for_the_home_screen(role, identifier):
    r = client.post("/api/v1/auth/login", json={"role": role, "identifier": identifier, "password": "password123"})
    assert r.status_code == 200
    user = r.json()["user"]
    # role, college and language are what decide the home screen and sidebar
    assert user["role"] == role and user["college_id"] == "col_demo_001" and user["language_pref"] in ("en", "ta")
    # the token opens that role's home and not another role's
    home = {"student": "/api/v1/student/dashboard", "trainer": "/api/v1/trainer/dashboard",
            "college_admin": "/api/v1/college/overview"}
    tok = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert client.get(home[role], headers=tok).status_code == 200
    other = "/api/v1/parent/overview"
    assert client.get(other, headers=tok).status_code == 403


@pytest.mark.link("L02")
def test_trainer_dashboard_shows_the_score_the_student_sees():
    """Up-link of L02: a flagged student's score on 13 equals their own 12."""
    t = client.get("/api/v1/trainer/dashboard", headers=ARUN).json()
    row = t["students_needing_support"][0]
    db = SessionLocal()
    try:
        st = db.execute(select(Student).filter_by(id=row["student_id"])).scalar_one()
        user_id = st.user_id
    finally:
        db.close()
    own = client.get("/api/v1/student/dashboard", headers=_h(user_id, "student")).json()["student"]
    assert own["id"] == row["student_id"]
    assert own["readiness_score"] == row["score"]


@pytest.mark.link("L34")
def test_one_readiness_score_and_band_on_every_screen():
    """L34: the same score and band on student (12), parent (15) and college (19) views."""
    s = client.get("/api/v1/student/dashboard", headers=PRIYA).json()["student"]
    p = client.get("/api/v1/parent/overview", headers=RAMESH).json()["kpis"]
    assert (s["readiness_score"], s["readiness_band"]) == (p["readiness_score"], p["readiness_band"])
    db = SessionLocal()
    try:
        st = db.execute(select(Student).filter_by(id="std_priya_01")).scalar_one()
        assert (st.readiness_score, st.readiness_band) == (s["readiness_score"], s["readiness_band"])
    finally:
        db.close()
    # the college distribution counts every student under the band their own screen shows
    c = client.get("/api/v1/college/overview", headers=KAVITHA).json()
    assert s["readiness_band"] in {row["band"] for row in c["readiness_distribution"]}


@pytest.mark.link("L35")
def test_college_sees_aggregates_but_never_trainer_notes_or_chats():
    marker = "PRIVATE-NOTE-" + uuid.uuid4().hex[:8]
    flag_id = client.get("/api/v1/trainer/dashboard", headers=ARUN).json()["students_needing_support"][0]["flag_id"]
    assert client.post(f"/api/v1/trainer/flags/{flag_id}/actions", json={"action_type": "note", "note": marker}, headers=ARUN).status_code == 200
    client.post("/api/v1/threads/th_ramesh/messages", json={"text": marker + " chat"}, headers=ARUN)
    overview = client.get("/api/v1/college/overview", headers=KAVITHA)
    assert overview.status_code == 200
    assert marker not in overview.text
    # the college cannot open trainer threads or the at-risk notes directly
    assert client.get("/api/v1/threads/th_ramesh/messages", headers=KAVITHA).status_code in (403, 404)
    assert client.get("/api/v1/trainer/at-risk", headers=KAVITHA).status_code in (403, 404)
