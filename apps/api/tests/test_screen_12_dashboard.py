"""Screen 12 Student Dashboard: payload shape, readiness math, why-score, tenant scope."""
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import Student, ReadinessSnapshot, User
from services.readiness import compute_score, compute_breakdown, DEFAULT_WEIGHTS, compute_snapshot, band_for

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Priya R"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name, 'avatar': 'PR'})}"}


def test_readiness_formula_matches_pdf_values():
    skills = {"dsa": 78, "aptitude": 71, "cloud": 64, "track": 82, "future_skills": 58, "communication": 69}
    assert compute_score(skills, 92, DEFAULT_WEIGHTS) == 74
    rows = compute_breakdown(skills, 92, DEFAULT_WEIGHTS)
    assert abs(sum(r["weight"] for r in rows) - 1.0) < 1e-9
    assert {r["key"] for r in rows} == set(DEFAULT_WEIGHTS)
    assert band_for(74) == "Nearly Ready" and band_for(75) == "Placement Ready" and band_for(59) == "Needs Support"


def test_dashboard_payload_from_rows():
    res = client.get("/api/v1/student/dashboard", headers=_token("usr_priya_01", "student"))
    assert res.status_code == 200
    d = res.json()
    st = d["student"]
    assert st["name"] == "Priya R"
    assert st["greeting"].startswith("Good")
    assert st["readiness_score"] == 74 and st["readiness_band"] == "Nearly Ready" and st["readiness_delta"] == 6
    assert st["has_snapshot"] is True
    assert st["attendance_pct"] == 92
    assert [s["key"] for s in d["skill_progress"]] == ["dsa", "aptitude", "cloud", "track", "future_skills", "communication"]
    assert [s["percentage"] for s in d["skill_progress"]] == [78, 71, 64, 82, 58, 69]
    assert len(d["this_week"]) >= 5
    assert any(row["day"] == "Sat" and row["is_lab"] for row in d["this_week"])
    assert d["current_project"]["title"].startswith("Clinic")
    assert 0 <= d["current_project"]["progress_pct"] <= 100
    titles = [e["title"] for e in d["upcoming_events"]]
    assert "Mid-term DSA test" in titles and "AWS Cloud Practitioner" in titles
    assert any(b["name"] == "Cloud Deployer" for b in d["badges"])


def test_dashboard_tamil_labels():
    d = client.get("/api/v1/student/dashboard?lang=ta", headers=_token("usr_priya_01", "student")).json()
    assert d["skill_progress"][0]["skill"] == "DSA வடிவங்கள்"
    assert d["student"]["greeting"].endswith("👋")


def test_why_score_breakdown_sums_to_score():
    res = client.get("/api/v1/student/dashboard/why-score", headers=_token("usr_priya_01", "student"))
    assert res.status_code == 200
    d = res.json()
    assert d["score"] == 74
    total = sum(c["contribution"] for c in d["components"])
    assert round(total) == 74
    assert len(d["history"]) >= 2


def test_other_student_gets_their_own_dashboard():
    db = SessionLocal()
    try:
        karthik_user = db.execute(select(User).filter_by(name="Karthik S")).scalars().first()
    finally:
        db.close()
    d = client.get("/api/v1/student/dashboard", headers=_token(karthik_user.id, "student", name="Karthik S")).json()
    assert d["student"]["name"] == "Karthik S"
    assert d["student"]["readiness_score"] == 52
    assert d["student"]["readiness_band"] == "Needs Support"


def test_cross_tenant_and_role_guard():
    assert client.get("/api/v1/student/dashboard", headers=_token("usr_priya_01", "student", college_id="col_other_999")).status_code == 404
    assert client.get("/api/v1/student/dashboard", headers=_token("usr_ramesh_01", "parent")).status_code == 403


def test_compute_snapshot_persists_and_updates_student():
    db = SessionLocal()
    try:
        st = db.execute(select(Student).filter_by(id="std_priya_01")).scalar_one()
        before = db.execute(select(ReadinessSnapshot).filter_by(student_id=st.id)).scalars().all()
        snap = compute_snapshot(db, st, persist=False)
        assert snap.score == 74 and snap.band == "Nearly Ready"
        assert len(db.execute(select(ReadinessSnapshot).filter_by(student_id=st.id)).scalars().all()) == len(before)
        db.rollback()
    finally:
        db.close()


def test_readiness_job_requires_staff_role():
    assert client.post("/api/v1/admin/jobs/readiness", headers=_token("usr_priya_01", "student")).status_code == 403
