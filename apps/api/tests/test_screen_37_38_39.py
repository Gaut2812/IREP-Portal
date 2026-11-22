"""S15: Screen 37 trainer mock interviews (L16), 38 mock drives (L17, L29), 39 placement readiness (L34, L35).
Spec: docs/screens/37-38-39-interviews-drives-readiness.md"""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import (AuditLog, DriveRound, Event, Interview, InterviewBooking, InterviewSlot, MockDrive, Notification,
                           Trainer)
from seed.seed_screen36 import seed_screen36
from seed.seed_screen38 import seed_screen38

client = TestClient(app)


def _h(sub, role, cid="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": cid})}


ARUN = _h("usr_arun_01", "trainer")
MEENA_T = _h("usr_meena_01", "trainer")
PRIYA = _h("usr_priya_01", "student")
KAVITHA = _h("usr_kavitha_01", "college_admin")
OTHER_COLLEGE = _h("usr_x", "college_admin", "col_other_999")


@pytest.fixture(autouse=True)
def demo_state():
    def reset():
        db = SessionLocal()
        try:
            seed_screen36(db, college_id="col_demo_001")
            seed_screen38(db, college_id="col_demo_001")
            db.commit()
        finally:
            db.close()
    reset()
    yield
    reset()


@pytest.fixture
def new_drive_event():
    """A drive created through screen 42 (L29); removed afterwards with its rounds and slots."""
    made = []
    yield made
    db = SessionLocal()
    try:
        for eid in made:
            d = db.execute(select(MockDrive).where(MockDrive.event_id == eid)).scalar_one_or_none()
            if d:
                rids = list(db.execute(select(DriveRound.id).where(DriveRound.drive_id == d.id)).scalars())
                sids = list(db.execute(select(InterviewSlot.id).where(InterviewSlot.drive_round_id.in_(rids or ["_"]))).scalars())
                db.execute(delete(InterviewBooking).where(InterviewBooking.slot_id.in_(sids or ["_"])))
                db.execute(delete(Interview).where(Interview.slot_id.in_(sids or ["_"])))
                db.execute(delete(InterviewSlot).where(InterviewSlot.id.in_(sids or ["_"])))
                db.execute(delete(DriveRound).where(DriveRound.id.in_(rids or ["_"])))
                db.delete(d)
                db.flush()
            db.execute(delete(Event).where(Event.id == eid))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------- 37

@pytest.mark.link("L16")
def test_trainer_scores_a_booked_interview_and_the_student_sees_it_on_36():
    view = client.get("/api/v1/trainer/interviews", headers=ARUN).json()
    keys = [c["key"] for c in view["rubric"]["criteria"]]
    waiting = next(i for i in view["to_score"] if i["id"] == "iv_drive_service_4")
    assert waiting["drive"] == "Mock drive: service-company pattern"                    # L17 label on 37
    # Priya books an open slot on 36; Arun sees who booked it on 37
    slot = client.get("/api/v1/student/interviews", headers=PRIYA).json()["available_slots"][0]
    assert client.post(f"/api/v1/student/interview-slots/{slot['id']}/book", headers=PRIYA).status_code == 200
    booked = next(s for s in client.get("/api/v1/trainer/interviews", headers=ARUN).json()["slots"] if s["id"] == slot["id"])
    assert booked["booked_by"] == "Priya R"
    # scoring: every criterion, feedback, notes; submitting twice is refused
    r = client.post("/api/v1/trainer/interviews/iv_drive_service_4/submit", headers=ARUN, json={
        "scores": {k: 4 for k in keys}, "feedback_en": "Solid round; slow down when explaining.",
        "feedback_ta": "நல்ல சுற்று; விளக்கும்போது நிதானமாகப் பேசுங்கள்.", "comments": [{"at_seconds": 75, "text": "Good clarifying questions."}]})
    assert r.status_code == 200 and r.json()["overall"] == 4.0
    assert client.post("/api/v1/trainer/interviews/iv_drive_service_4/submit", headers=ARUN, json={
        "scores": {k: 4 for k in keys}, "feedback_en": "again"}).status_code == 409
    # the score reaches the student's 36 (Priya's own latest stays hers; check the scored student's data via the trainer list)
    after = client.get("/api/v1/trainer/interviews", headers=ARUN).json()
    assert not any(i["id"] == "iv_drive_service_4" for i in after["to_score"])
    assert next(i for i in after["submitted"] if i["id"] == "iv_drive_service_4")["overall"] == 4.0
    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "interview.submit", AuditLog.entity_id == "iv_drive_service_4")).first()
    finally:
        db.close()


@pytest.mark.link("L16")
def test_cancelling_a_booked_slot_frees_the_student_and_tells_them():
    slot = client.get("/api/v1/student/interviews", headers=PRIYA).json()["available_slots"][0]
    client.post(f"/api/v1/student/interview-slots/{slot['id']}/book", headers=PRIYA)
    assert client.delete(f"/api/v1/trainer/interview-slots/{slot['id']}", headers=ARUN).status_code == 200
    mine = client.get("/api/v1/student/interviews", headers=PRIYA).json()
    assert not any(b["slot_id"] == slot["id"] for b in mine["my_bookings"])
    db = SessionLocal()
    try:
        n = db.execute(select(Notification).where(Notification.user_id == "usr_priya_01", Notification.title_en == "Mock interview cancelled")
                       .order_by(Notification.created_at.desc())).scalars().first()
        assert n is not None and n.title_ta == "மாதிரி நேர்காணல் ரத்து செய்யப்பட்டது"
    finally:
        db.close()
    assert client.delete(f"/api/v1/trainer/interview-slots/{slot['id']}", headers=ARUN).status_code == 404     # already cancelled


@pytest.mark.link("L16")
def test_recording_upload_reaches_the_students_signed_link():
    r = client.post("/api/v1/trainer/interviews/iv_priya_2/recording", headers=ARUN,
                    files={"file": ("round2.mp4", b"\x00\x00\x00\x18ftypmp42" + b"0" * 2048, "video/mp4")})
    assert r.status_code == 200
    url = client.get("/api/v1/student/interviews/iv_priya_2/recording", headers=PRIYA).json()["url"]
    assert "recordings/interviews/iv_priya_2.mp4" in url
    path = url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url.lstrip("/")
    got = client.get("/" + path)
    assert got.status_code == 200 and got.content.startswith(b"\x00\x00\x00\x18ftyp")
    assert client.post("/api/v1/trainer/interviews/iv_priya_2/recording", headers=ARUN,
                       files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415


def test_trainer_routes_guard_role_and_ownership():
    assert client.get("/api/v1/trainer/interviews", headers=PRIYA).status_code == 403
    # another trainer's interview and slot: 404
    assert client.post("/api/v1/trainer/interviews/iv_drive_service_4/submit", headers=MEENA_T,
                       json={"scores": {}, "feedback_en": "not mine"}).status_code == 404
    assert client.delete("/api/v1/trainer/interview-slots/slot_demo_tech", headers=MEENA_T).status_code == 404


def test_trainer_view_in_tamil():
    view = client.get("/api/v1/trainer/interviews?lang=ta", headers=ARUN).json()
    assert view["rubric"]["criteria"][0]["label"] == "சிக்கல் தீர்த்தல்"
    assert any(s["round_label"] == "HR சுற்று" for s in view["slots"])
    assert view["to_score"][0]["drive"] == "மாதிரி முகாம்: சேவை நிறுவன முறை"


# ---------------------------------------------------------------- 38

def _new_drive(new_drive_event, days=12):
    start = (datetime.datetime.now() + datetime.timedelta(days=days)).replace(hour=10, minute=0, second=0, microsecond=0)
    e = client.post("/api/v1/college/events", headers=KAVITHA, json={
        "title_en": "Mock drive: test pattern", "title_ta": "மாதிரி முகாம்: சோதனை", "kind": "drive",
        "starts_at": start.isoformat(), "audience": "students", "batch_id": "bat_aids_s5_aids"}).json()
    new_drive_event.append(e["id"])
    drive = next(d for d in client.get("/api/v1/college/drives", headers=KAVITHA).json()["drives"] if d["event_id"] == e["id"])
    return drive, start


@pytest.mark.link("L29")
def test_a_drive_event_on_42_creates_its_drive_on_38(new_drive_event):
    drive, _ = _new_drive(new_drive_event)
    assert drive["status"] == "draft" and drive["batch"] and drive["rounds"] == 0
    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "drive.created", AuditLog.entity_id == drive["id"])).first()
    finally:
        db.close()
    # other kinds of events do not create drives
    e = client.post("/api/v1/college/events", headers=KAVITHA, json={
        "title_en": "Guest talk", "title_ta": "விருந்தினர் உரை", "kind": "guest",
        "starts_at": (datetime.datetime.now() + datetime.timedelta(days=5)).isoformat(), "audience": "all"}).json()
    new_drive_event.append(e["id"])
    assert not any(d["event_id"] == e["id"] for d in client.get("/api/v1/college/drives", headers=KAVITHA).json()["drives"])


@pytest.mark.link("L17")
def test_publishing_a_drive_puts_interview_slots_on_the_trainers_37(new_drive_event):
    drive, start = _new_drive(new_drive_event)
    did = drive["id"]
    assert client.put(f"/api/v1/college/drives/{did}", headers=KAVITHA, json={"company_pattern": "Service: aptitude + technical"}).status_code == 200
    assert client.post(f"/api/v1/college/drives/{did}/rounds", headers=KAVITHA, json={
        "kind": "test", "test_id": "test_service_aptitude", "cutoff": 60}).status_code == 201
    assert client.post(f"/api/v1/college/drives/{did}/rounds", headers=KAVITHA, json={
        "kind": "interview", "round_type": "technical", "trainer_id": "trn_arun_01", "starts_at": (start + datetime.timedelta(hours=2)).isoformat(),
        "duration_min": 30, "slot_count": 3, "cutoff": 3.5}).status_code == 201
    # validation: unknown test, trainer outside the batch, past start, cut-off out of range
    assert client.post(f"/api/v1/college/drives/{did}/rounds", headers=KAVITHA, json={"kind": "test", "test_id": "nope"}).status_code == 404
    assert client.post(f"/api/v1/college/drives/{did}/rounds", headers=KAVITHA, json={
        "kind": "interview", "round_type": "technical", "trainer_id": "trn_nope", "starts_at": start.isoformat(), "slot_count": 1}).status_code == 404
    assert client.post(f"/api/v1/college/drives/{did}/rounds", headers=KAVITHA, json={
        "kind": "test", "test_id": "test_service_aptitude", "cutoff": 120}).status_code == 422
    out = client.post(f"/api/v1/college/drives/{did}/publish", headers=KAVITHA).json()
    assert out["status"] == "published" and out["slots_created"] == 3
    # L17: the slots are on Arun's 37, marked with the drive, 30 minutes apart
    mine = [s for s in client.get("/api/v1/trainer/interviews", headers=ARUN).json()["slots"] if s["drive"] == "Mock drive: test pattern"]
    assert len(mine) == 3
    times = sorted(datetime.datetime.fromisoformat(s["starts_at"]) for s in mine)
    assert times[1] - times[0] == datetime.timedelta(minutes=30)

    # a published drive is frozen
    assert client.post(f"/api/v1/college/drives/{did}/rounds", headers=KAVITHA, json={"kind": "test", "test_id": "test_service_aptitude"}).status_code == 409
    assert client.post(f"/api/v1/college/drives/{did}/publish", headers=KAVITHA).status_code == 409
    db = SessionLocal()
    try:
        arun = db.get(Trainer, "trn_arun_01")
        note = db.execute(select(Notification).where(Notification.user_id == arun.user_id, Notification.link == "/trainer/interviews")
                          .order_by(Notification.created_at.desc())).scalars().first()
        assert note.title_en == "Mock drive slots: Mock drive: test pattern" and note.title_ta.startswith("மாதிரி முகாம் நேரங்கள்")
        assert db.execute(select(AuditLog).where(AuditLog.action == "drive.published", AuditLog.entity_id == did)).first()
    finally:
        db.close()


def test_results_are_scores_only_and_the_shortlist_is_published_once():
    r = client.get("/api/v1/college/drives/drv_demo_service/results", headers=KAVITHA).json()
    assert r["shortlisted"] == 2 and [f["cleared"] for f in r["funnel"]] == [3, 3]
    sneha = next(s for s in r["students"] if s["name"] == "Sneha N")
    assert [c["score"] for c in sneha["rounds"]] == [80.0, 4.1] and sneha["shortlisted"] is True
    flat = str(r)
    assert "feedback" not in flat and "practise" not in flat                       # trainer notes never reach the college (5.4)
    out = client.post("/api/v1/college/drives/drv_demo_service/shortlist", headers=KAVITHA).json()
    assert out == {"drive_id": "drv_demo_service", "status": "results_published", "shortlisted": 2, "total": r["total"]}
    assert client.post("/api/v1/college/drives/drv_demo_service/shortlist", headers=KAVITHA).status_code == 409


def test_drives_guard_role_and_college():
    assert client.get("/api/v1/college/drives", headers=ARUN).status_code == 403
    assert client.get("/api/v1/college/drives", headers=PRIYA).status_code == 403
    assert client.get("/api/v1/college/drives/drv_demo_service", headers=OTHER_COLLEGE).status_code == 404
    assert client.post("/api/v1/college/drives/drv_demo_product/publish", headers=OTHER_COLLEGE).status_code == 404


def test_drive_in_tamil():
    d = client.get("/api/v1/college/drives/drv_demo_product?lang=ta", headers=KAVITHA).json()
    assert d["title"] == "மாதிரி முகாம்: தயாரிப்பு நிறுவன முறை"
    assert [r["label"] for r in d["round_list"]] == ["தேர்வு", "AI அனுமதி கோடிங்"]


# ---------------------------------------------------------------- 39

@pytest.mark.link("L34", "L35")
def test_readiness_drills_down_branch_batch_student_with_aggregates_only():
    top = client.get("/api/v1/college/readiness", headers=KAVITHA).json()
    s = top["summary"]
    assert s["students"] > 0 and sum(s["bands"].values()) == s["students"] and top["groups"][0]["level"] == "branch"
    aids = next(g for g in top["groups"] if g["id"] == "br_aids")
    batches = client.get("/api/v1/college/readiness?branch_id=br_aids", headers=KAVITHA).json()
    assert batches["groups"][0]["level"] == "batch" and sum(g["students"] for g in batches["groups"]) == aids["students"]
    one = client.get("/api/v1/college/readiness?batch_id=bat_aids_s5_aids", headers=KAVITHA).json()
    priya = next(st for st in one["students"] if st["name"] == "Priya R")
    assert set(priya) == {"id", "name", "register_no", "score", "band", "band_label", "delta"}        # no notes, no breakdown
    assert one["scope"]["branch"]["id"] == "br_aids" and one["components"]
    ready = client.get("/api/v1/college/readiness?batch_id=bat_aids_s5_aids&band=ready", headers=KAVITHA).json()
    assert ready["students"] and all(st["band"] == "ready" for st in ready["students"])


def test_readiness_guards_and_tamil():
    assert client.get("/api/v1/college/readiness", headers=ARUN).status_code == 403
    assert client.get("/api/v1/college/readiness?batch_id=bat_aids_s5_aids", headers=OTHER_COLLEGE).status_code == 404
    assert client.get("/api/v1/college/readiness?branch_id=br_aids&batch_id=bat_nope", headers=KAVITHA).status_code == 404
    ta = client.get("/api/v1/college/readiness?batch_id=bat_aids_s5_aids&lang=ta", headers=KAVITHA).json()
    assert ta["band_labels"] == {"ready": "வேலைக்குத் தயார்", "nearly": "கிட்டத்தட்ட தயார்", "support": "உதவி தேவை"}
    assert any(c["label"] == "வருகை" for c in ta["components"])
