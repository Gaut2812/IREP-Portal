"""Courses (screens 46 and 11), Phase 2: IREP staff add a thumbnail, an intro video and lesson videos; students see
them through signed links and get "continue where you left off"."""
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import Course, Lesson, OutboxEvent

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, STAFF = _h("usr_priya_01", "student"), _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


@pytest.fixture
def course():
    mine = client.get("/api/v1/student/courses", headers=PRIYA).json()["courses"]
    if not mine:
        pytest.skip("demo state: no course visible to Priya")
    cid = mine[0]["id"]
    with SessionLocal() as db:
        lesson = db.execute(select(Lesson.id).where(Lesson.course_id == cid).order_by(Lesson.position)).scalars().first()
    yield cid, lesson
    with SessionLocal() as db:   # leave the demo course without the test files
        c = db.get(Course, cid)
        c.thumbnail_key = c.intro_video_key = None
        for l in db.execute(select(Lesson).where(Lesson.course_id == cid)).scalars():
            l.video_key = None
        db.commit()


def test_staff_add_media_and_students_see_it(course):
    cid, lesson = course
    r = client.post(f"/api/v1/admin/content/courses/{cid}/media/thumbnail", headers=STAFF, files={"file": ("cover.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["thumbnail_url"].startswith("/media/courses/")
    assert client.post(f"/api/v1/admin/content/courses/{cid}/media/intro_video", headers=STAFF,
                       files={"file": ("intro.mp4", MP4, "video/mp4")}).json()["intro_video_url"]
    assert client.post(f"/api/v1/admin/content/lessons/{lesson}/video", headers=STAFF,
                       files={"file": ("l1.mp4", MP4, "video/mp4")}).json()["video_url"]

    card = next(c for c in client.get("/api/v1/student/courses", headers=PRIYA).json()["courses"] if c["id"] == cid)
    img = client.get(card["thumbnail_url"])                                           # the signed link serves the file
    assert img.status_code == 200 and img.content == PNG
    detail = client.get(f"/api/v1/student/courses/{cid}", headers=PRIYA).json()
    assert detail["course"]["intro_video_url"] and detail["lessons"][0]["video_url"]
    assert client.get(card["thumbnail_url"].replace("sig=", "sig=x")).status_code == 403   # tampered link


def test_replacing_and_deleting_media_removes_the_old_file(course):
    cid, _ = course
    client.post(f"/api/v1/admin/content/courses/{cid}/media/thumbnail", headers=STAFF, files={"file": ("a.png", PNG, "image/png")})
    client.post(f"/api/v1/admin/content/courses/{cid}/media/thumbnail", headers=STAFF, files={"file": ("b.jpg", b"\xff\xd8\xff" + b"\x00" * 32, "image/jpeg")})
    with SessionLocal() as db:
        assert db.get(Course, cid).thumbnail_key.endswith(".jpg")
        assert db.execute(select(OutboxEvent.id).where(OutboxEvent.event_type == "storage.delete",
                                                       OutboxEvent.payload["key"].as_string() == f"courses/{cid}/thumbnail.png")).first()
    assert client.delete(f"/api/v1/admin/content/courses/{cid}/media/thumbnail", headers=STAFF).json()["thumbnail_url"] is None
    assert client.delete(f"/api/v1/admin/content/courses/{cid}/media/thumbnail", headers=STAFF).status_code == 404


def test_media_rules_and_guards(course):
    cid, _ = course
    assert client.post(f"/api/v1/admin/content/courses/{cid}/media/thumbnail", headers=STAFF,
                       files={"file": ("x.gif", b"GIF89a", "image/gif")}).status_code == 415
    assert client.post(f"/api/v1/admin/content/courses/{cid}/media/poster", headers=STAFF,
                       files={"file": ("x.png", PNG, "image/png")}).status_code == 404
    assert client.post(f"/api/v1/admin/content/courses/{cid}/media/thumbnail", headers=PRIYA,
                       files={"file": ("x.png", PNG, "image/png")}).status_code == 403


def test_continue_where_you_left_off(course):
    cid, _ = course
    data = client.get("/api/v1/student/courses", headers=PRIYA).json()
    card = next(c for c in data["courses"] if c["id"] == cid)
    detail = client.get(f"/api/v1/student/courses/{cid}", headers=PRIYA).json()
    first_open = next((l for l in detail["lessons"] if not l["completed"]), None)
    if first_open is None:
        assert card["next_lesson"] is None and detail["next_lesson_id"] is None
    else:
        assert card["next_lesson"]["id"] == first_open["id"] == detail["next_lesson_id"]
    assert "continue_course_id" in data
