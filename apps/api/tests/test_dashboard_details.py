"""Student dashboard (screen 12), Phase 2: what is behind each tile, and no numbers hard-coded for one student."""
import datetime
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from fastapi.testclient import TestClient
from sqlalchemy import delete

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import CodingSubmission
from services.dashboard_details import HEATMAP_DAYS, streaks

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA = _h("usr_priya_01", "student")


def test_streaks_count_consecutive_days_and_today_does_not_break_the_run():
    today = datetime.date(2026, 11, 28)
    d = lambda n: today - datetime.timedelta(days=n)
    assert streaks({d(1), d(2), d(3)}, today) == (3, 3)                 # nothing yet today: the run still stands
    assert streaks({today, d(1), d(5), d(6), d(7), d(8)}, today) == (2, 4)
    assert streaks(set(), today) == (0, 0)


def test_details_behind_each_tile():
    sid = f"sub_t_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(CodingSubmission(id=sid, college_id="col_demo_001", problem_id="prob_two_sum", student_id="std_priya_01",
                                language="python", code="x", status="Accepted", tests_passed=3, tests_total=3))
        db.commit()
    try:
        d = client.get("/api/v1/student/dashboard/details", headers=PRIYA).json()
        topics = {t["topic"]: t["solved"] for t in d["problems"]["by_topic"]}
        assert topics.get("Arrays & Hash Map", 0) >= 1 and d["problems"]["this_month"] >= 1
        assert any(r["title"] == "Two Sum" for r in d["problems"]["recent"])
        assert len(d["activity"]["days"]) == HEATMAP_DAYS and d["activity"]["days"][-1]["count"] >= 1
        assert d["activity"]["best"] >= d["activity"]["current"] >= 1
        earned = [b for b in d["badges"] if b["earned"]]
        locked = [b for b in d["badges"] if not b["earned"]]
        assert earned and d["badges"][: len(earned)] == earned                       # earned first
        assert all(b["description"] for b in locked)                                   # locked ones say how to earn them
        assert all(s["how"] for s in d["skills"]) and {s["key"] for s in d["skills"]} >= {"dsa", "aptitude"}
        dash = client.get("/api/v1/student/dashboard", headers=PRIYA).json()["student"]
        assert dash["problems_delta"] == d["problems"]["this_month"]                  # no longer a number fixed for Priya
        ta = client.get("/api/v1/student/dashboard/details?lang=ta", headers=PRIYA).json()
        assert "கோடிங்" in next(s["how"] for s in ta["skills"] if s["key"] == "dsa")
    finally:
        with SessionLocal() as db:
            db.execute(delete(CodingSubmission).where(CodingSubmission.id == sid))
            db.commit()


def test_details_guards():
    assert client.get("/api/v1/student/dashboard/details", headers=_h("usr_arun_01", "trainer")).status_code == 403
    assert client.get("/api/v1/student/dashboard/details", headers=_h("usr_priya_01", "student", "col_other_999")).status_code == 404
