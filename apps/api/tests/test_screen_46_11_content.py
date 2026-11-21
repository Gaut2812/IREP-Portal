"""Screens 46 (content library) and 11 (my courses): links L12, L33, L37.
Spec: docs/screens/46-11-content-and-courses.md"""
import sys
import uuid
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
from models.schema import Course, Lesson, LessonProgress, Notification, NotificationTemplate, SkillScore
from services.templates import render

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
PRIYA, KAVITHA, ARUN = _h("usr_priya_01", "student"), _h("usr_kavitha_01", "college_admin"), _h("usr_arun_01", "trainer")


@pytest.fixture
def course():
    db = SessionLocal()
    try:
        skill_before = db.execute(select(SkillScore.percentage).where(SkillScore.student_id == "std_priya_01",
                                                                      SkillScore.skill_key == "communication")).scalar_one()
    finally:
        db.close()
    cid = client.post("/api/v1/admin/content/courses", json={"title_en": "RAG systems " + uuid.uuid4().hex[:4], "title_ta": "RAG அமைப்புகள்",
                                                              "semester": 5, "track": "All", "skill_key": "communication"}, headers=STAFF).json()["id"]
    yield cid
    db = SessionLocal()
    try:
        lids = list(db.execute(select(Lesson.id).where(Lesson.course_id == cid)).scalars())
        db.execute(delete(LessonProgress).where(LessonProgress.lesson_id.in_(lids or ["_"])))
        db.execute(delete(Lesson).where(Lesson.course_id == cid))
        db.execute(delete(Course).where(Course.id == cid))
        db.execute(delete(Notification).where(Notification.link == f"/student/courses/{cid}"))
        db.execute(delete(NotificationTemplate).where(NotificationTemplate.key.like("test.%")))
        s = db.execute(select(SkillScore).where(SkillScore.student_id == "std_priya_01", SkillScore.skill_key == "communication")).scalar_one()
        s.percentage = skill_before
        db.commit()
    finally:
        db.close()


def _lesson(cid, n, ta=True):
    body = {"title_en": f"Lesson {n}", "body_en": f"Chunking and retrieval, part {n}.", "duration_min": 15}
    if ta:
        body.update({"title_ta": f"பாடம் {n}", "body_ta": f"பிரித்தலும் மீட்டெடுப்பும், பகுதி {n}."})
    return client.post(f"/api/v1/admin/content/courses/{cid}/lessons", json=body, headers=STAFF).json()["id"]


@pytest.mark.link("L12")
def test_published_course_reaches_matching_students_only(course):
    _lesson(course, 1)
    assert all(c["id"] != course for c in client.get("/api/v1/student/courses", headers=PRIYA).json()["courses"])   # draft: hidden
    pub = client.post(f"/api/v1/admin/content/courses/{course}/publish", headers=STAFF)
    assert pub.status_code == 200 and pub.json()["status"] == "published"
    mine = client.get("/api/v1/student/courses?lang=ta", headers=PRIYA).json()["courses"]
    row = next(c for c in mine if c["id"] == course)
    assert row["title"] == "RAG அமைப்புகள்" and row["lessons"] == 1 and row["pct"] == 0
    detail = client.get(f"/api/v1/student/courses/{course}?lang=ta", headers=PRIYA).json()
    assert detail["lessons"][0]["body"].startswith("பிரித்தலும்")
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_priya_01", Notification.link == f"/student/courses/{course}")).first()
    finally:
        db.close()
    # another semester's student does not see it
    db = SessionLocal()
    try:
        from models.schema import Student
        other = db.execute(select(Student).where(Student.college_id == "col_demo_001", Student.semester != 5)).scalars().first()
    finally:
        db.close()
    other_courses = client.get("/api/v1/student/courses", headers=_h(other.user_id, "student")).json()["courses"]
    assert all(c["id"] != course for c in other_courses)
    assert client.get(f"/api/v1/student/courses/{course}", headers=_h(other.user_id, "student")).status_code == 404


def test_publishing_needs_tamil_and_a_lesson(course):
    assert client.post(f"/api/v1/admin/content/courses/{course}/publish", headers=STAFF).status_code == 422       # no lessons
    _lesson(course, 1, ta=False)
    r = client.post(f"/api/v1/admin/content/courses/{course}/publish", headers=STAFF)
    assert r.status_code == 422 and "Tamil" in r.json()["detail"]


@pytest.mark.link("L33")
def test_course_progress_raises_the_skill_bar_and_never_lowers_it(course):
    l1, l2 = _lesson(course, 1), _lesson(course, 2)
    client.post(f"/api/v1/admin/content/courses/{course}/publish", headers=STAFF)
    db = SessionLocal()
    try:
        before = db.execute(select(SkillScore.percentage).where(SkillScore.student_id == "std_priya_01", SkillScore.skill_key == "communication")).scalar_one()
    finally:
        db.close()
    first = client.post(f"/api/v1/student/lessons/{l1}/complete", headers=PRIYA).json()
    assert first["completed"] and first["skill_pct"] == max(before, 50)                 # never below what it was
    again = client.post(f"/api/v1/student/lessons/{l1}/complete", headers=PRIYA).json()
    assert again["already"] is True
    done = client.post(f"/api/v1/student/lessons/{l2}/complete", headers=PRIYA).json()
    assert done["skill_pct"] == 100
    bars = {s["key"]: s["percentage"] for s in client.get("/api/v1/student/dashboard", headers=PRIYA).json()["skill_progress"]}
    assert bars["communication"] == 100                                                  # 12 shows it
    assert next(c for c in client.get("/api/v1/student/courses", headers=PRIYA).json()["courses"] if c["id"] == course)["pct"] == 100


def test_templates_render_with_fallback(course):
    r = client.put("/api/v1/admin/content/templates/test.leave", json={"title_en": "Leave for {student}", "title_ta": "{student} விடுப்பு",
                                                                       "body_en": "{dates} ({unknown})"}, headers=STAFF)
    assert r.status_code == 200
    db = SessionLocal()
    try:
        out = render(db, "test.leave", {"title_en": "fallback"}, student="Priya R", dates="1-2 Dec")
        assert out["title_en"] == "Leave for Priya R" and out["title_ta"] == "Priya R விடுப்பு" and out["body_en"] == "1-2 Dec ({unknown})"
        assert render(db, "test.none", {"title_en": "fallback", "title_ta": None, "body_en": None, "body_ta": None})["title_en"] == "fallback"
    finally:
        db.close()
    assert client.put("/api/v1/admin/content/templates/bad key!", json={"title_en": "x y"}, headers=STAFF).status_code == 422


@pytest.mark.parametrize("headers", [PRIYA, KAVITHA, ARUN])
def test_only_staff_edit_the_library(headers):
    assert client.get("/api/v1/admin/content/courses", headers=headers).status_code == 403
    assert client.post("/api/v1/admin/content/courses", json={"title_en": "Nope", "semester": 5, "skill_key": "dsa"}, headers=headers).status_code == 403


def test_students_cannot_complete_hidden_lessons(course):
    l1 = _lesson(course, 1)                                       # still a draft
    assert client.post(f"/api/v1/student/lessons/{l1}/complete", headers=PRIYA).status_code == 404
