"""Screens 41 (college messages) and 40 (surveys, set up on 02): links L20, L30, L26; announcements
at scale (chunked outbox fan-out); the college's AWS Academy link. Spec: docs/screens/41-40-messages-surveys.md"""
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import Broadcast, GroupMessage, Notification, OutboxEvent, ParentStudent, Student
import routers.surveys as surveys_router
from services import broadcasts

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


KAVITHA, ARUN, PRIYA = _h("usr_kavitha_01", "college_admin"), _h("usr_arun_01", "trainer"), _h("usr_priya_01", "student")
RAMESH, LAKSHMI = _h("usr_ramesh_01", "parent"), _h("usr_lakshmi_01", "parent")
OTHER = _h("usr_kavitha_01", "college_admin", "col_other_test")
BATCH = "bat_aids_s5_aids"


@pytest.fixture(autouse=True)
def restore():
    yield
    from seed.seed_screen29 import seed_screen29
    from seed.seed_screen35 import seed_screen35
    from seed.seed_screen41 import seed_screen41
    db = SessionLocal()
    try:
        seed_screen41(db)
        seed_screen35(db)
        seed_screen29(db)
        db.commit()
    finally:
        db.close()


def _deliver(broadcast_id):
    """Run this announcement's queued chunks, as the dispatcher would."""
    db = SessionLocal()
    try:
        evs = db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "broadcast.chunk", OutboxEvent.entity_id == broadcast_id,
                                                   OutboxEvent.status == "pending")).scalars().all()
        for ev in evs:
            broadcasts._chunk(db, ev)
            ev.status = "done"
        db.commit()
        return evs
    finally:
        db.close()


@pytest.mark.link("L20")
def test_college_and_trainer_chat():
    trainers = client.get("/api/v1/college/message-contacts", headers=KAVITHA).json()["trainers"]
    assert any(t["user_id"] == "usr_arun_01" for t in trainers)
    tid = client.post("/api/v1/college/threads", json={"trainer_user_id": "usr_arun_01"}, headers=KAVITHA).json()["thread_id"]
    assert client.post("/api/v1/college/threads", json={"trainer_user_id": "usr_arun_01"}, headers=KAVITHA).json()["thread_id"] == tid
    assert client.post(f"/api/v1/threads/{tid}/messages", json={"text": "Can we move Friday's lab to 2 pm?"}, headers=KAVITHA).status_code == 200
    mine = client.get("/api/v1/college/threads", headers=KAVITHA).json()["threads"]
    assert any(t["id"] == tid for t in mine)
    trainer_side = client.get("/api/v1/trainer/threads?category=College", headers=ARUN).json()
    rows = trainer_side.get("threads", trainer_side.get("items", []))
    assert any(t["id"] == tid for t in rows)
    msgs = client.get(f"/api/v1/threads/{tid}/messages", headers=ARUN).json()
    assert "Friday" in str(msgs)
    assert client.post("/api/v1/college/threads", json={"trainer_user_id": "usr_priya_01"}, headers=KAVITHA).status_code == 403   # policy
    assert client.post("/api/v1/college/threads", json={"trainer_user_id": "usr_arun_01"}, headers=OTHER).status_code == 404
    assert client.get("/api/v1/college/threads", headers=PRIYA).status_code == 403


@pytest.mark.link("L30")
def test_announcement_reaches_the_group_students_and_parents():
    r = client.post("/api/v1/college/announcements", json={
        "title": "Placement drive on Friday", "title_ta": "வெள்ளி அன்று வேலைவாய்ப்பு முகாம்",
        "body": "Bring two copies of your resume.", "body_ta": "உங்கள் சுயவிவரத்தின் இரண்டு நகல்களைக் கொண்டு வாருங்கள்.",
        "audience": "both", "batch_ids": [BATCH]}, headers=KAVITHA)
    assert r.status_code == 201, r.text
    b = r.json()
    db = SessionLocal()
    try:
        students = db.execute(select(func.count(Student.id)).where(Student.batch_id == BATCH)).scalar_one()
        parents = db.execute(select(func.count(func.distinct(ParentStudent.parent_user_id))).join(Student, Student.id == ParentStudent.student_id)
                             .where(Student.batch_id == BATCH)).scalar_one()
    finally:
        db.close()
    assert b["recipients"] == students + parents and b["status"] == "sending" and b["delivered"] == 0
    evs = _deliver(b["id"])
    assert len(evs) >= 2                                                                   # students and parents, chunked
    done = client.get(f"/api/v1/college/announcements/{b['id']}", headers=KAVITHA).json()
    assert done["delivered"] == b["recipients"] and done["status"] == "done"
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_priya_01",
                                                     Notification.link == f"/student/discussions?announcement={b['id']}")).first()
        assert db.execute(select(GroupMessage).where(GroupMessage.group_id == "grp_placement", GroupMessage.id.like("gm_bc_%"),
                                                     GroupMessage.message_text.contains("Placement drive"))).first()      # 34
        again = broadcasts.deliver_chunk(db, b["id"], "student", [db.execute(select(Student.user_id).where(Student.id == "std_priya_01")).scalar_one()])
        assert again == 0                                                                  # idempotent retry
    finally:
        db.close()
    overview = client.get("/api/v1/parent/overview?lang=ta", headers=RAMESH).json()["announcements"]
    assert overview[0]["title"] == "வெள்ளி அன்று வேலைவாய்ப்பு முகாம்"                       # 15
    assert client.post("/api/v1/college/announcements", json={"title": "x y z", "body": "abc", "batch_ids": ["bat_nope"]}, headers=KAVITHA).status_code == 404
    assert client.post("/api/v1/college/announcements", json={"title": "x y z", "body": "abc", "audience": "all"}, headers=KAVITHA).status_code == 422
    assert client.post("/api/v1/college/announcements", json={"title": "x y z", "body": "abc"}, headers=ARUN).status_code == 403


def test_large_audiences_are_split_into_chunks(monkeypatch):
    monkeypatch.setattr(broadcasts, "CHUNK", 50)
    b = client.post("/api/v1/college/announcements", json={"title": "Exam timetable", "body": "Posted on the notice board.",
                                                           "audience": "students"}, headers=KAVITHA).json()
    assert b["recipients"] > 600 and b["chunks"] == f"0/{-(-b['recipients'] // 50)}"
    _deliver(b["id"])
    assert client.get(f"/api/v1/college/announcements/{b['id']}", headers=KAVITHA).json()["delivered"] == b["recipients"]


@pytest.mark.link("L26")
def test_survey_goes_out_and_aggregates_come_back(monkeypatch):
    body = {"title_en": "Lab week feedback", "questions": [
        {"kind": "rating", "text_en": "How useful were the labs?"},
        {"kind": "choice", "text_en": "Best time for parent meetings?", "options_en": ["Morning", "Evening"]},
        {"kind": "text", "text_en": "Any comments?", "required": False}]}
    sid = client.post("/api/v1/college/surveys", json=body, headers=KAVITHA).json()["id"]
    assert client.post(f"/api/v1/college/surveys/{sid}/publish", headers=KAVITHA).status_code == 422     # Tamil missing
    ta = {**body, "title_ta": "ஆய்வக வாரக் கருத்து", "questions": [
        {**body["questions"][0], "text_ta": "ஆய்வகங்கள் எவ்வளவு பயனுள்ளவை?"},
        {**body["questions"][1], "text_ta": "பெற்றோர் சந்திப்புக்குச் சிறந்த நேரம்?", "options_ta": ["காலை", "மாலை"]},
        {**body["questions"][2], "text_ta": "கருத்துகள்?"}]}
    assert client.put(f"/api/v1/college/surveys/{sid}", json=ta, headers=KAVITHA).status_code == 200
    pub = client.post(f"/api/v1/college/surveys/{sid}/publish", headers=KAVITHA).json()
    assert pub["status"] == "published" and pub["notified"] >= 2
    mine = next(s for s in client.get("/api/v1/parent/surveys?lang=ta", headers=RAMESH).json()["surveys"] if s["id"] == sid)
    assert mine["title"] == "ஆய்வக வாரக் கருத்து" and mine["questions"][1]["options"] == ["காலை", "மாலை"] and not mine["answered"]
    assert client.post(f"/api/v1/parent/surveys/{sid}/responses", json={"answers": {"q1": 9, "q2": "Morning"}}, headers=RAMESH).status_code == 422
    assert client.post(f"/api/v1/parent/surveys/{sid}/responses", json={"answers": {"q2": "Morning"}}, headers=RAMESH).status_code == 422
    assert client.post(f"/api/v1/parent/surveys/{sid}/responses", json={"answers": {"q1": 5, "q2": "மாலை", "q3": "More lab hours please"}},
                       headers=RAMESH).status_code == 201
    assert client.post(f"/api/v1/parent/surveys/{sid}/responses", json={"answers": {"q1": 4, "q2": "Morning"}}, headers=RAMESH).status_code == 409
    assert client.post(f"/api/v1/parent/surveys/{sid}/responses", json={"answers": {"q1": 3, "q2": "Morning"}}, headers=LAKSHMI).status_code == 201
    hidden = client.get(f"/api/v1/college/surveys/{sid}/results", headers=KAVITHA).json()
    assert hidden["hidden"] is True and hidden["responses"] == 2                         # too few to show safely
    monkeypatch.setattr(surveys_router, "MIN_RESPONSES_FOR_RESULTS", 2)
    res = client.get(f"/api/v1/college/surveys/{sid}/results", headers=KAVITHA).json()
    q1, q2, q3 = res["questions"]
    assert q1["average"] == 4.0 and q1["distribution"]["5"] == 1 and q2["counts"] == {"Morning": 1, "Evening": 1}
    assert q3["comments"] == ["More lab hours please"] and "ramesh" not in str(res).lower()
    assert client.post(f"/api/v1/college/surveys/{sid}/close", headers=KAVITHA).json()["status"] == "closed"
    assert client.post(f"/api/v1/parent/surveys/{sid}/responses", json={"answers": {"q1": 3, "q2": "Morning"}}, headers=RAMESH).status_code == 404
    assert client.get("/api/v1/college/surveys", headers=RAMESH).status_code == 403
    assert client.get(f"/api/v1/college/surveys/{sid}/results", headers=OTHER).status_code == 404
    bad = {**ta, "questions": [{"kind": "choice", "text_en": "Only one?", "options_en": ["A"]}]}
    assert client.post("/api/v1/college/surveys", json=bad, headers=KAVITHA).status_code == 422


def test_college_sets_its_aws_academy_link():
    assert client.put("/api/v1/college/labs/cloud-sandbox", json={"url": "https://evil.example.com/course"}, headers=KAVITHA).status_code == 422
    url = "https://awsacademy.instructure.com/courses/12345"
    assert client.put("/api/v1/college/labs/cloud-sandbox", json={"url": url}, headers=KAVITHA).json()["external_url"] == url
    db = SessionLocal()
    try:
        from models.schema import LabSession
        for s in db.execute(select(LabSession).where(LabSession.student_id == "std_priya_01", LabSession.status.in_(["running", "starting"]))).scalars():
            s.status = "stopped"
        db.commit()
    finally:
        db.close()
    sid = client.post("/api/v1/student/labs/lab_cloud/launch", headers=PRIYA).json()["session"]["id"]
    assert client.get(f"/api/v1/student/lab-sessions/{sid}/connect", headers=PRIYA).json()["url"] == url
    assert client.put("/api/v1/college/labs/cloud-sandbox", json={"url": url}, headers=ARUN).status_code == 403
    overview = client.get("/api/v1/college/overview", headers=KAVITHA).json()
    assert set(overview["labs"]) == {"hours_this_month", "quota_hours", "pct", "students_using"}
