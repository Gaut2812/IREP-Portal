"""Screens 21 and 16 (monthly cards, L22), 20 (MoU reports, L35) and 49 (support, L28 and L39).
Spec: docs/screens/21-16-20-49-reports-and-support.md"""
import sys
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
from models.schema import AuditLog, MonthlyCard, Notification, ReportRun, SupportMessage, SupportTicket

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


ARUN, MEENA = _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer")
RAMESH, LAKSHMI = _h("usr_ramesh_01", "parent"), _h("usr_lakshmi_01", "parent")
PRIYA, KAVITHA = _h("usr_priya_01", "student"), _h("usr_kavitha_01", "college_admin")
STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
MONTH = "2026-11"
CARD = "mc_std_priya_01_202611"
TEXT = {"trainer_remark_en": "Strong month: steady coding and a clear demo.", "trainer_remark_ta": "சிறந்த மாதம்: தொடர்ந்த கோடிங் மற்றும் தெளிவான விளக்கம்.",
        "how_to_help_en": "Ask Priya to explain her project at dinner.", "how_to_help_ta": "இரவு உணவின்போது தன் புராஜெக்ட்டை விளக்கச் சொல்லுங்கள்."}


@pytest.fixture
def november():
    yield
    db = SessionLocal()
    try:
        db.execute(delete(MonthlyCard).where(MonthlyCard.year == 2026, MonthlyCard.month == 11))
        db.execute(delete(Notification).where(Notification.kind == "report"))
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L22")
def test_trainer_approval_releases_the_card_to_the_parent(november):
    r = client.post("/api/v1/trainer/reports/generate", json={"month": MONTH}, headers=ARUN)
    assert r.status_code == 200 and r.json()["created"] > 0
    assert client.post("/api/v1/trainer/reports/generate", json={"month": MONTH}, headers=ARUN).json()["created"] == 0   # never overwrites
    listed = client.get(f"/api/v1/trainer/reports?month={MONTH}", headers=ARUN).json()
    row = next(s for s in listed["students"] if s["student_id"] == "std_priya_01")
    assert row["card_id"] == CARD and row["status"] == "draft" and not row["ready"]

    card = client.get(f"/api/v1/trainer/reports/{CARD}", headers=ARUN).json()
    coding = next(x for x in card["rows"] if x["area"] == "Coding (problems solved)")
    assert coding["prev"] == "286"                                   # "last month" comes from the October card
    assert all(c["id"] != CARD for c in client.get("/api/v1/parent/reports", headers=RAMESH).json()["cards"])   # draft: hidden
    assert client.get(f"/api/v1/parent/reports/{CARD}", headers=RAMESH).status_code == 404

    # the trainer writes English only: Tamil is translated on save, so parents still read the card in Tamil
    saved = client.put(f"/api/v1/trainer/reports/{CARD}", json={"trainer_remark_en": TEXT["trainer_remark_en"]}, headers=ARUN).json()
    assert saved["trainer_remark_ta"] and saved["trainer_remark_ta"] != TEXT["trainer_remark_en"]
    assert saved["missing"] == ["how_to_help_en"]
    no_help = client.post(f"/api/v1/trainer/reports/{CARD}/approve", headers=ARUN)
    assert no_help.status_code == 422 and "help text" in no_help.json()["detail"]
    assert client.put(f"/api/v1/trainer/reports/{CARD}", json=TEXT, headers=ARUN).status_code == 200
    ok = client.post(f"/api/v1/trainer/reports/{CARD}/approve", headers=ARUN)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    assert client.put(f"/api/v1/trainer/reports/{CARD}", json=TEXT, headers=ARUN).status_code == 409         # read-only once released
    assert client.post(f"/api/v1/trainer/reports/{CARD}/approve", headers=ARUN).status_code == 409

    mine = client.get("/api/v1/parent/reports?lang=ta", headers=RAMESH).json()
    first = mine["cards"][0]
    assert first["id"] == CARD and first["month_label"] == "நவம்பர் 2026" and first["trainer_remark"].startswith("சிறந்த மாதம்")
    pdf = client.get(f"/api/v1/parent/reports/{CARD}/pdf", headers=RAMESH)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and b"Strong month" in pdf.content
    assert client.get("/api/v1/parent/overview", headers=RAMESH).json()["monthly_card"]["id"] == CARD           # 15 shows it too
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_ramesh_01", Notification.link == "/parent/reports",
                                                     Notification.kind == "report")).first()
        assert db.execute(select(AuditLog).where(AuditLog.action == "monthly_card.released", AuditLog.entity_id == CARD)).first()
    finally:
        db.close()


def test_bulk_approval_skips_incomplete_cards(november):
    client.post("/api/v1/trainer/reports/generate", json={"month": MONTH}, headers=ARUN)
    client.put(f"/api/v1/trainer/reports/{CARD}", json=TEXT, headers=ARUN)
    other = next(s["card_id"] for s in client.get(f"/api/v1/trainer/reports?month={MONTH}", headers=ARUN).json()["students"]
                 if s["card_id"] and s["card_id"] != CARD)
    out = client.post("/api/v1/trainer/reports/approve", json={"card_ids": [CARD, other, "mc_nope"]}, headers=ARUN).json()
    assert out["released"] == [CARD] and {s["card_id"] for s in out["skipped"]} == {other, "mc_nope"}


def test_card_guards(november):
    client.post("/api/v1/trainer/reports/generate", json={"month": MONTH}, headers=ARUN)
    assert client.get(f"/api/v1/trainer/reports/{CARD}", headers=MEENA).status_code == 404                   # not her batch
    assert client.get(f"/api/v1/trainer/reports/{CARD}", headers=_h("usr_arun_01", "trainer", "col_other_test")).status_code in (403, 404)
    assert client.get("/api/v1/trainer/reports", headers=RAMESH).status_code == 403
    assert client.get("/api/v1/parent/reports", headers=ARUN).status_code == 403
    assert client.get("/api/v1/trainer/reports?month=2026-13", headers=ARUN).status_code == 422
    # seeded card ids are not predictable: look up Priya's released September card
    db = SessionLocal()
    try:
        sept = db.execute(select(MonthlyCard.id).where(MonthlyCard.student_id == "std_priya_01", MonthlyCard.month == 9)).scalar_one()
    finally:
        db.close()
    assert client.get(f"/api/v1/parent/reports/{sept}", headers=RAMESH).status_code == 200
    assert client.get(f"/api/v1/parent/reports/{sept}", headers=LAKSHMI).status_code == 404                 # not her child
    # without the parent-data consent, 16 shows nothing (screen 48)
    client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "withdrawn", "student_id": "std_priya_01"}, headers=RAMESH)
    try:
        assert client.get("/api/v1/parent/reports", headers=RAMESH).json() == {
            "consent_required": True, "ward": {"id": "std_priya_01", "name": "Priya R"}, "cards": []}
        assert client.get(f"/api/v1/parent/reports/{sept}", headers=RAMESH).status_code == 403
    finally:
        client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "granted", "student_id": "std_priya_01"}, headers=RAMESH)


@pytest.mark.link("L35")
def test_mou_report_carries_terms_and_aggregates_only():
    r = client.post("/api/v1/college/reports/generate", json={"report_type": "progress"}, headers=KAVITHA)
    rid = r.json()["report"]["id"]
    try:
        pdf = client.get(f"/api/v1/college/reports/{rid}/download", headers=KAVITHA).content
        assert b"Students enrolled against the cap" in pdf and b"of 650" in pdf
        assert b"Priya" not in pdf and b"Arun" not in pdf                                     # no names, notes or chats
        assert client.get(f"/api/v1/college/reports/{rid}/download", headers=_h("usr_kavitha_01", "college_admin", "col_other_test")).status_code == 404
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ReportRun).where(ReportRun.id == rid))
            db.commit()
        finally:
            db.close()


# ------------------------------------------------------------------ Screen 49

@pytest.fixture
def tickets():
    yield
    db = SessionLocal()
    try:
        ids = list(db.execute(select(SupportTicket.id).where(SupportTicket.subject.like("Test:%"))).scalars())
        db.execute(delete(SupportMessage).where(SupportMessage.ticket_id.in_(ids or ["_"])))
        db.execute(delete(SupportTicket).where(SupportTicket.id.in_(ids or ["_"])))
        db.execute(delete(Notification).where(Notification.kind == "support"))
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L39")
@pytest.mark.link("L28")
def test_report_a_problem_and_staff_reply_reaches_the_notification_centre(tickets):
    r = client.post("/api/v1/support/tickets", json={"subject": "Test: hint button does nothing", "body": "On problem 3 the hint button spins.",
                                                      "category": "bug", "page_path": "/student/coding"}, headers=PRIYA)
    assert r.status_code == 201
    tid = r.json()["id"]
    staff_view = client.get("/api/v1/support/tickets?status_filter=open", headers=STAFF).json()
    row = next(t for t in staff_view["tickets"] if t["id"] == tid)
    assert staff_view["staff"] and row["college"] == "Demo Engineering College" and row["page_path"] == "/student/coding"
    assert client.get(f"/api/v1/support/tickets/{tid}", headers=ARUN).status_code == 404                     # not his ticket
    assert all(t["id"] != tid for t in client.get("/api/v1/support/tickets", headers=ARUN).json()["tickets"])

    assert client.post(f"/api/v1/support/tickets/{tid}/messages", json={"body": "Fixed: please reload the page."}, headers=STAFF).json()["status"] == "answered"
    notes = client.get("/api/v1/notifications", headers=PRIYA).json()
    items = notes.get("notifications", notes.get("items", notes)) if isinstance(notes, dict) else notes
    assert any("IREP support replied" in (n.get("title") or n.get("title_en") or "") for n in items)           # 44 Notification centre
    thread = client.get(f"/api/v1/support/tickets/{tid}", headers=PRIYA).json()["thread"]
    assert [m["is_staff"] for m in thread] == [False, True]
    assert client.post(f"/api/v1/support/tickets/{tid}/messages", json={"body": "Works now, thanks."}, headers=PRIYA).json()["status"] == "open"
    assert client.post(f"/api/v1/support/tickets/{tid}/close", headers=PRIYA).json()["status"] == "closed"
    assert client.post(f"/api/v1/support/tickets/{tid}/messages", json={"body": "One more"}, headers=PRIYA).status_code == 409


def test_support_validation(tickets):
    assert client.post("/api/v1/support/tickets", json={"subject": "Test: x", "body": "body text", "category": "rant"}, headers=PRIYA).status_code == 422
    assert client.post("/api/v1/support/tickets", json={"subject": "Hi", "body": "b"}, headers=PRIYA).status_code == 422
    assert client.get("/api/v1/support/tickets", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
