"""Screen 19 College Dashboard: aggregates equal direct queries, filters, roles, downloads."""
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import Student, Branch, Certificate, Internship, ReportRun

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Dr. Kavitha"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


ADMIN = _token("usr_kavitha_01", "college_admin")


def test_overview_matches_source_tables():
    res = client.get("/api/v1/college/overview", headers=ADMIN)
    assert res.status_code == 200
    d = res.json()
    db = SessionLocal()
    try:
        total = db.execute(select(func.count(Student.id)).filter_by(college_id="col_demo_001")).scalar_one()
        assert d["kpis"]["students_enrolled"]["value"] == total == 612
        assert d["kpis"]["students_enrolled"]["branches"] == 4
        avg_att = db.execute(select(func.avg(Student.attendance_pct)).filter_by(college_id="col_demo_001")).scalar_one()
        assert d["kpis"]["avg_attendance"]["value"] == round(avg_att)
        certs = db.execute(select(func.count(Certificate.id)).filter_by(college_id="col_demo_001", status="earned")).scalar_one()
        assert d["kpis"]["certifications"]["value"] == certs == 184
        interns = db.execute(select(func.count(Internship.id)).filter_by(college_id="col_demo_001")).scalar_one()
        assert d["kpis"]["internships"]["value"] == interns == 73
        bands = dict(db.execute(select(Student.readiness_band, func.count(Student.id)).where(Student.college_id == "col_demo_001").group_by(Student.readiness_band)).all())
        for row in d["readiness_distribution"]:
            assert row["count"] == bands.get(row["band"], 0)
        assert sum(r["percentage"] for r in d["readiness_distribution"]) in (99, 100, 101)
        per_branch = dict(db.execute(
            select(Branch.name, func.count(Student.id)).join(Student, Student.branch_id == Branch.id).group_by(Branch.name)
        ).all())
        for row in d["branch_readiness"]:
            assert row["students"] == per_branch[row["branch"]]
        assert [r["branch"] for r in d["branch_readiness"]] == ["CSE", "IT", "AI & DS", "Cybersecurity"]
        assert [c["count"] for c in d["cumulative_certifications"]] == [28, 54, 92, 143, 184]
    finally:
        db.close()
    titles = [e["title"] for e in d["upcoming_events"]]
    assert "Project Demo Day" in titles
    assert len(d["mou_reports"]) >= 3
    all_reports = client.get("/api/v1/college/reports", headers=ADMIN).json()["reports"]
    assert any(r["id"] == "rep_sep_progress" for r in all_reports)
    assert all(r["generated_at"] and r["data_as_of"] for r in d["mou_reports"])


def test_semester_filter():
    d = client.get("/api/v1/college/overview?semester=6", headers=ADMIN).json()
    db = SessionLocal()
    try:
        sem6 = db.execute(select(func.count(Student.id)).filter_by(college_id="col_demo_001", semester=6)).scalar_one()
    finally:
        db.close()
    assert d["kpis"]["students_enrolled"]["value"] == sem6 == 112
    assert d["filters"]["semester"] == 6
    assert client.get("/api/v1/college/overview?semester=1", headers=ADMIN).status_code == 422


def test_tamil_labels():
    d = client.get("/api/v1/college/overview?lang=ta", headers=ADMIN).json()
    assert d["readiness_distribution"][0]["label"] == "வேலைவாய்ப்புக்கு தயார்"
    assert d["mou_reports"][0]["title"] != ""


def test_trainer_and_parent_cannot_open():
    assert client.get("/api/v1/college/overview", headers=_token("usr_arun_01", "trainer")).status_code == 403
    assert client.get("/api/v1/college/overview", headers=_token("usr_ramesh_01", "parent")).status_code == 403
    assert client.get("/api/v1/college/overview", headers=_token("usr_priya_01", "student")).status_code == 403


def test_other_college_is_empty():
    d = client.get("/api/v1/college/overview", headers=_token("usr_x", "college_admin", college_id="col_other_999")).json()
    assert d["kpis"]["students_enrolled"]["value"] == 0
    assert d["branch_readiness"] == [] and d["mou_reports"] == []


def test_report_download_and_generate():
    res = client.get("/api/v1/college/reports/rep_sep_progress/download", headers=ADMIN)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/pdf")
    assert res.content.startswith(b"%PDF")
    assert client.get("/api/v1/college/reports/rep_sep_progress/download", headers=_token("usr_arun_01", "trainer")).status_code == 403
    assert client.get("/api/v1/college/reports/rep_sep_progress/download", headers=_token("usr_x", "college_admin", college_id="col_other_999")).status_code == 404

    gen = client.post("/api/v1/college/reports/generate", json={"report_type": "readiness"}, headers=ADMIN)
    assert gen.status_code == 200
    rid = gen.json()["report"]["id"]
    dl = client.get(f"/api/v1/college/reports/{rid}/download", headers=ADMIN)
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")
    db = SessionLocal()
    try:
        run = db.execute(select(ReportRun).filter_by(id=rid)).scalar_one()
        assert run.status == "ready" and run.generated_at and run.data_as_of
    finally:
        db.close()
