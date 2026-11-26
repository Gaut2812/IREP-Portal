"""Screen 36 Mock Interviews: PDF 7 payload, DB-enforced no double booking,
scores hidden until the trainer submits, cancel window, signed recording, guards."""
import datetime
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import InterviewBooking, InterviewSlot, User, Interview
from seed.seed_screen36 import seed_screen36

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Priya R"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


PRIYA = _token("usr_priya_01", "student")
ARUN = _token("usr_arun_01", "trainer", name="Arun Kumar")
SCORES = {"problem_solving": 5, "coding": 4, "thinking_aloud": 4, "core_cs": 4, "project": 4, "communication": 4}


@pytest.fixture(autouse=True)
def demo_state():
    db = SessionLocal()
    try:
        seed_screen36(db)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        # remove bookings by other students made in these tests, then restore
        db.execute(InterviewBooking.__table__.delete().where(InterviewBooking.slot_id.in_(["slot_demo_tech", "slot_demo_hr", "slot_demo_ai"])))
        seed_screen36(db)
        db.commit()
    finally:
        db.close()


def _sneha():
    db = SessionLocal()
    try:
        u = db.execute(select(User).filter_by(name="Sneha N")).scalars().first()
        return _token(u.id, "student", name="Sneha N")
    finally:
        db.close()


def test_payload_matches_pdf7():
    d = client.get("/api/v1/student/interviews", headers=PRIYA).json()
    li = d["latest_interview"]
    assert li["title"] == "Mock Interview #2 – Technical" and li["interviewer"] == "Arun Kumar" and li["duration_min"] == 40
    assert li["overall"] == 3.8
    assert [c["label"] for c in li["chips"]] == ["Hire-ready for service roles", "Improve for product roles"]
    assert [(r["label"], r["score"]) for r in li["rubric"]] == [
        ("Problem solving", 4), ("Coding & correctness", 4), ("Thinking aloud", 3),
        ("Core CS knowledge", 4), ("Project explanation", 4), ("Communication & confidence", 3)]
    assert li["feedback"].startswith("Strong on DSA")
    assert [t["label"] for t in d["trend"]] == ["#1 · 3.0", "#2 · 3.8"] and d["target"] == 4.2
    assert [s["type_label"] for s in d["available_slots"]] == ["Technical", "HR round", "AI-allowed coding"]
    assert len(li["comments"]) == 5 and li["comments"][1]["label"] == "9:00"


def test_double_booking_is_impossible():
    assert client.post("/api/v1/student/interview-slots/slot_demo_tech/book", headers=PRIYA).status_code == 200
    # a classmate cannot take the same slot
    r = client.post("/api/v1/student/interview-slots/slot_demo_tech/book", headers=_sneha())
    assert r.status_code == 409
    # and the database itself rejects a second booking row
    db = SessionLocal()
    try:
        db.add(InterviewBooking(id="bk_dup_test", college_id="col_demo_001", slot_id="slot_demo_tech", student_id="std_priya_01"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
    d = client.get("/api/v1/student/interviews", headers=PRIYA).json()
    assert [b["slot_id"] for b in d["my_bookings"]] == ["slot_demo_tech"]
    assert "slot_demo_tech" not in [s["id"] for s in d["available_slots"]]
    # one upcoming round per type
    db = SessionLocal()
    try:
        db.add(InterviewSlot(id="slot_test_tech2", college_id="col_demo_001", trainer_id="trn_arun_01", round_type="technical",
                             starts_at=datetime.datetime.now() + datetime.timedelta(days=6), status="open"))
        db.commit()
    finally:
        db.close()
    assert client.post("/api/v1/student/interview-slots/slot_test_tech2/book", headers=PRIYA).status_code == 409


def test_cancel_reopens_slot():
    bid = client.post("/api/v1/student/interview-slots/slot_demo_hr/book", headers=PRIYA).json()["booking_id"]
    assert client.delete(f"/api/v1/student/bookings/{bid}", headers=PRIYA).status_code == 200
    ids = [s["id"] for s in client.get("/api/v1/student/interviews", headers=PRIYA).json()["available_slots"]]
    assert "slot_demo_hr" in ids
    assert client.delete(f"/api/v1/student/bookings/{bid}", headers=PRIYA).status_code == 404


def test_scores_appear_only_after_trainer_submits():
    client.post("/api/v1/student/interview-slots/slot_demo_ai/book", headers=PRIYA)
    db = SessionLocal()
    try:
        iv = db.execute(select(Interview).filter_by(student_id="std_priya_01", slot_id="slot_demo_ai")).scalar_one()
        iv_id = iv.id
        assert iv.round_number == 3
    finally:
        db.close()
    d = client.get("/api/v1/student/interviews", headers=PRIYA).json()
    assert d["latest_interview"]["round_number"] == 2 and len(d["trend"]) == 2
    bad = client.post(f"/api/v1/trainer/interviews/{iv_id}/submit", json={"scores": {"problem_solving": 5}, "feedback_en": "Short"}, headers=ARUN)
    assert bad.status_code == 422
    assert client.post(f"/api/v1/trainer/interviews/{iv_id}/submit", json={"scores": SCORES, "feedback_en": "Great progress"}, headers=PRIYA).status_code == 403
    ok = client.post(f"/api/v1/trainer/interviews/{iv_id}/submit",
                     json={"scores": SCORES, "overall": 4.3, "feedback_en": "Great progress overall", "comments": [{"at_seconds": 300, "text": "Clear approach"}]},
                     headers=ARUN)
    assert ok.status_code == 200 and ok.json()["overall"] == 4.3
    d = client.get("/api/v1/student/interviews", headers=PRIYA).json()
    assert d["latest_interview"]["round_number"] == 3 and d["latest_interview"]["overall"] == 4.3
    assert [c["label"] for c in d["latest_interview"]["chips"]] == ["Hire-ready for service roles", "Hire-ready for product roles"]
    assert len(d["trend"]) == 3
    assert client.post(f"/api/v1/trainer/interviews/{iv_id}/submit", json={"scores": SCORES, "feedback_en": "again please"}, headers=ARUN).status_code == 409


def test_signed_recording():
    r = client.get("/api/v1/student/interviews/iv_priya_2/recording", headers=PRIYA)
    assert r.status_code == 200 and "/media/recordings/interviews/priya_round2.mp4?exp=" in r.json()["url"]
    assert client.get("/api/v1/student/interviews/iv_priya_2/recording", headers=_sneha()).status_code == 404


def test_guards():
    assert client.get("/api/v1/student/interviews", headers=_token("usr_ramesh_01", "parent")).status_code == 403
    assert client.get("/api/v1/student/interviews", headers=_token("usr_priya_01", "student", college_id="col_other_999")).status_code == 404
    db = SessionLocal()
    try:
        u = db.execute(select(User).filter_by(name="Divya M")).scalars().first()   # IT-A: Arun's batch too, but not his slots' batch rule
    finally:
        db.close()
    assert client.post("/api/v1/student/interview-slots/slot_does_not_exist/book", headers=PRIYA).status_code == 404


def test_booking_notification_reads_well_in_english_and_tamil():
    bid = client.post("/api/v1/student/interview-slots/slot_demo_hr/book", headers=PRIYA).json()["booking_id"]
    try:
        en = client.get("/api/v1/notifications?lang=en", headers=PRIYA).json()["items"]
        ta = client.get("/api/v1/notifications?lang=ta", headers=PRIYA).json()["items"]
        booked_en = next(n for n in en if n["title"] == "Mock interview booked")
        booked_ta = next(n for n in ta if n["title"] == "மாதிரி நேர்காணல் பதிவு செய்யப்பட்டது")
        assert booked_en["body"].startswith("Your mock interview (HR round) is on ")
        assert booked_ta["body"].startswith("உங்கள் மாதிரி நேர்காணல் (HR சுற்று)")
    finally:
        client.delete(f"/api/v1/student/bookings/{bid}", headers=PRIYA)
