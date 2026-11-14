"""
Screen 11 – My Courses
pytest unit tests: tenant scoping, progress counts, idempotency, role guard.
"""
import sys
from pathlib import Path

# Make sure the api root is importable
repo_root = str(Path(__file__).resolve().parents[3])
api_root = str(Path(__file__).resolve().parents[1])
for p in (repo_root, api_root):
    if p not in sys.path:
        sys.path.insert(0, p)

import datetime
import pytest
from fastapi import HTTPException

from core.database import SessionLocal, engine, Base
from core.security import TokenPayload
from models.schema import Course, Module, Lesson, LessonProgress, Student
from routers import student as student_router
from seed.seed_data import init_db_and_seed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def seed_once():
    """Ensure tables and seed data exist before any test in this module."""
    Base.metadata.create_all(engine)
    init_db_and_seed()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def student_user():
    return TokenPayload(
        sub="usr_priya_01",
        email="priya.r@demo.edu",
        role="student",
        college_id="col_demo_001",
        name="Priya R",
    )


@pytest.fixture()
def parent_user():
    return TokenPayload(
        sub="usr_ramesh_01",
        email="ramesh.k@example.com",
        role="parent",
        college_id="col_demo_001",
        name="Mr. Ramesh K",
    )


@pytest.fixture()
def trainer_user():
    return TokenPayload(
        sub="usr_arun_01",
        email="arun.k@demo.edu",
        role="trainer",
        college_id="col_demo_001",
        name="Arun Kumar",
    )


# ---------------------------------------------------------------------------
# Test 1: courses are tenant-scoped
# ---------------------------------------------------------------------------

def test_get_courses_tenant_scoped(db, student_user):
    """Only courses whose college_id matches the JWT tenant are returned."""
    result = student_router.list_courses(
        track=None, semester=None, current_user=student_user, db=db
    )
    assert "courses" in result
    courses = result["courses"]
    # Every returned course must belong to the demo college (checked via DB fixture)
    assert len(courses) >= 3  # at least the 3 seeded courses
    for c in courses:
        # Verify the row in DB actually has the right college_id
        db_row = db.get(Course, c["id"])
        assert db_row is not None
        assert db_row.college_id == student_user.college_id


# ---------------------------------------------------------------------------
# Test 2: progress fields are well-formed integers in [0, 100]
# ---------------------------------------------------------------------------

def test_get_courses_progress_counts(db, student_user):
    result = student_router.list_courses(
        track=None, semester=None, current_user=student_user, db=db
    )
    for c in result["courses"]:
        assert isinstance(c["completed_lessons"], int)
        assert isinstance(c["total_lessons"], int)
        assert isinstance(c["progress_pct"], int)
        assert 0 <= c["progress_pct"] <= 100
        assert c["completed_lessons"] <= c["total_lessons"]


# ---------------------------------------------------------------------------
# Test 3: course detail includes modules and per-lesson completed flag
# ---------------------------------------------------------------------------

def test_get_course_detail_with_modules(db, student_user):
    result = student_router.get_course_detail(
        course_id="crs_dsa_patterns", current_user=student_user, db=db
    )
    assert result["course"]["id"] == "crs_dsa_patterns"
    assert len(result["modules"]) >= 3  # 3 seeded modules

    for mod in result["modules"]:
        assert "lessons" in mod
        for les in mod["lessons"]:
            assert "completed" in les
            assert isinstance(les["completed"], bool)
            assert les["type"] in ("video", "slides", "notes", "assignment")


# ---------------------------------------------------------------------------
# Test 4: mark_lesson_progress is idempotent (no duplicate rows)
# ---------------------------------------------------------------------------

def test_mark_lesson_progress_idempotent(db, student_user):
    lesson_id = "les_dsa_02_02"   # not seeded as completed initially
    course_id = "crs_dsa_patterns"

    # First call
    r1 = student_router.mark_lesson_progress(
        course_id=course_id, lesson_id=lesson_id,
        current_user=student_user, db=db
    )
    assert r1["success"] is True

    # Second call — must NOT raise and must NOT create a duplicate row
    r2 = student_router.mark_lesson_progress(
        course_id=course_id, lesson_id=lesson_id,
        current_user=student_user, db=db
    )
    assert r2["success"] is True

    from sqlalchemy import select
    rows = db.execute(
        select(LessonProgress).filter_by(lesson_id=lesson_id)
    ).scalars().all()
    assert len(rows) == 1  # exactly one row despite two POSTs


# ---------------------------------------------------------------------------
# Test 5: resume endpoint returns a valid incomplete lesson
# ---------------------------------------------------------------------------

def test_get_resume_lesson(db, student_user):
    result = student_router.get_resume_lesson(current_user=student_user, db=db)
    # There are incomplete lessons, so result must not be None
    assert result is not None
    assert "lesson_id" in result
    assert "course_id" in result
    # The returned lesson must exist in DB
    db_lesson = db.get(Lesson, result["lesson_id"])
    assert db_lesson is not None


# ---------------------------------------------------------------------------
# Test 6: non-student roles receive 403 Forbidden
# ---------------------------------------------------------------------------

def test_non_student_role_forbidden(db, parent_user, trainer_user):
    for user in (parent_user, trainer_user):
        with pytest.raises(HTTPException) as exc_info:
            # require_role dependency is baked in; call the guard explicitly
            from core.security import require_role
            checker = require_role(["student", "super_admin"])
            checker(current_user=user)
        assert exc_info.value.status_code == 403

