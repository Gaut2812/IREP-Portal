"""Screen 15 Parent View: per-parent scoping, released cards only, RSVP persistence."""
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import MonthlyCard, Rsvp, AuditLog
import pytest

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Parent"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


RAMESH = _token("usr_ramesh_01", "parent", name="Mr. Ramesh K")
LAKSHMI = _token("usr_lakshmi_01", "parent", name="Mrs. Lakshmi S")


def test_overview_for_priya_matches_pdf_card():
    res = client.get("/api/v1/parent/overview", headers=RAMESH)
    assert res.status_code == 200
    d = res.json()
    assert d["ward"]["name"] == "Priya R" and d["ward"]["details"] == "Sem 5 · AI & DS"
    assert d["kpis"]["readiness_score"] == 74 and d["kpis"]["readiness_band"] == "Nearly Ready"
    assert d["kpis"]["attendance_pct"] == 92 and d["kpis"]["attendance_note"] == "Excellent"
    assert d["kpis"]["certifications"] == 1 and d["kpis"]["cert_note"].startswith("AWS exam on ")
    card = d["monthly_card"]
    assert card["month"] == "October" and card["prev_month"] == "September" and card["status"] in ("approved", "sent")
    rows = {r["area"]: r for r in card["rows"]}
    assert rows["Coding (problems solved)"]["prev"] == "252" and rows["Coding (problems solved)"]["curr"] == "286"
    assert rows["Communication"]["status"] == "Needs practice" and rows["Communication"]["color"] == "amber"
    assert card["how_to_help"].startswith("Encourage 10 minutes")
    assert d["portfolio"]["github_projects"] >= 1
    titles = [e["title"] for e in d["upcoming"]]
    assert "Project Demo Day" in titles
    assert d["trainers"] and d["trainers"][0]["name"] == "Arun Kumar"


def test_tamil_overview():
    d = client.get("/api/v1/parent/overview?lang=ta", headers=RAMESH).json()
    assert d["kpis"]["readiness_band_label"] == "கிட்டத்தட்ட தயார்"
    assert d["monthly_card"]["month"] == "அக்டோபர்"
    assert d["monthly_card"]["rows"][0]["area"] == "கோடிங் (தீர்க்கப்பட்டவை)"


def test_siblings_and_other_parents_are_isolated():
    kids = client.get("/api/v1/parent/me/children", headers=LAKSHMI).json()["children"]
    assert [k["name"] for k in kids] == ["Karthik S"]
    d = client.get("/api/v1/parent/overview", headers=LAKSHMI).json()
    assert d["ward"]["name"] == "Karthik S" and d["kpis"]["readiness_score"] == 52
    assert d["kpis"]["attendance_note"] == "Needs attention"
    # Lakshmi cannot read Priya, Ramesh cannot read Karthik
    assert client.get("/api/v1/parent/children/std_priya_01/overview", headers=LAKSHMI).status_code == 404
    assert client.get(f"/api/v1/parent/children/{kids[0]['id']}/overview", headers=RAMESH).status_code == 404
    assert client.get("/api/v1/parent/overview", headers=_token("usr_ramesh_01", "parent", college_id="col_other_999")).status_code == 404
    assert client.get("/api/v1/parent/overview", headers=_token("usr_priya_01", "student")).status_code == 403


def test_only_released_cards_are_shown():
    db = SessionLocal()
    try:
        card = db.execute(select(MonthlyCard).filter_by(student_id="std_priya_01", year=2026, month=10)).scalar_one()
        card.status = "draft"
        db.commit()
        d = client.get("/api/v1/parent/overview", headers=RAMESH).json()
        assert d["monthly_card"]["month"] == "September"
        card.status = "approved"
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L38")
def test_rsvp_persists_and_is_audited():
    res = client.post("/api/v1/parent/events/evt_demo_day/rsvp", json={"status": "yes", "guests": 2}, headers=RAMESH)
    assert res.status_code == 200 and res.json()["rsvp_status"] == "yes"
    d = client.get("/api/v1/parent/overview", headers=RAMESH).json()
    demo = next(e for e in d["upcoming"] if e["id"] == "evt_demo_day")
    assert demo["rsvp_status"] == "yes" and demo["guests"] == 2
    # update instead of duplicate
    client.post("/api/v1/parent/events/evt_demo_day/rsvp", json={"status": "maybe", "guests": 1}, headers=RAMESH)
    db = SessionLocal()
    try:
        rows = db.execute(select(Rsvp).filter_by(event_id="evt_demo_day", parent_user_id="usr_ramesh_01")).scalars().all()
        assert len(rows) == 1 and rows[0].status == "maybe"
        assert db.execute(select(AuditLog).filter_by(action="rsvp.save", entity_id="evt_demo_day")).scalars().first() is not None
    finally:
        db.close()
    assert client.post("/api/v1/parent/events/evt_demo_day/rsvp", json={"status": "sure"}, headers=RAMESH).status_code == 422
    assert client.post("/api/v1/parent/events/evt_guest_gcc/rsvp", json={"status": "yes"}, headers=RAMESH).status_code == 404
    assert client.post("/api/v1/parent/events/evt_demo_day/rsvp", json={"status": "yes"}, headers=_token("usr_priya_01", "student")).status_code == 403
