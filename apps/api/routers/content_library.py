"""Screens 46 · Content library (IREP staff) and 11 · My courses (student): links L12, L33, L37.
Spec: docs/screens/46-11-content-and-courses.md
"""
import datetime
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import PLATFORM_TENANT, TokenPayload, require_role
from core.tenant import get_student_for_user
from models.schema import Course, Lesson, LessonProgress, NotificationTemplate, Student
from services.audit import record_audit
from services.courses import feed_skill_bar, visible_courses
from services.notifications import notify_users

router = APIRouter(tags=["Screens 46/11 · Content library and My courses"])
STAFF = require_role(["irep_admin"])
STUDENT = require_role(["student"])
SKILLS = ("dsa", "aptitude", "cloud", "track", "future_skills", "communication")


class CourseIn(BaseModel):
    title_en: str = Field(min_length=3, max_length=255)
    title_ta: Optional[str] = Field(default=None, max_length=255)
    track: str = Field(default="All", max_length=64)
    semester: int = Field(ge=2, le=7)
    skill_key: str


class LessonIn(BaseModel):
    title_en: str = Field(min_length=2, max_length=255)
    title_ta: Optional[str] = Field(default=None, max_length=255)
    body_en: str = Field(default="", max_length=20000)
    body_ta: Optional[str] = Field(default=None, max_length=20000)
    duration_min: int = Field(default=20, ge=1, le=240)
    position: Optional[int] = Field(default=None, ge=1, le=500)


class TemplateIn(BaseModel):
    title_en: str = Field(min_length=2, max_length=255)
    title_ta: Optional[str] = Field(default=None, max_length=255)
    body_en: Optional[str] = Field(default=None, max_length=2000)
    body_ta: Optional[str] = Field(default=None, max_length=2000)


def _course(db: Session, course_id: str) -> Course:
    c = db.execute(select(Course).where(Course.id == course_id, Course.college_id == PLATFORM_TENANT)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return c


def _lessons(db: Session, course_id: str) -> List[Lesson]:
    return db.execute(select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.position, Lesson.id)).scalars().all()


def _course_out(c: Course, lessons: int) -> dict:
    return {"id": c.id, "title_en": c.title_en, "title_ta": c.title_ta, "track": c.track, "semester": c.semester,
            "skill_key": c.skill_key, "status": c.status, "published_at": c.published_at.isoformat() if c.published_at else None,
            "lessons": lessons}


def _lesson_out(l: Lesson) -> dict:
    return {"id": l.id, "position": l.position, "title_en": l.title_en, "title_ta": l.title_ta, "body_en": l.body_en,
            "body_ta": l.body_ta, "duration_min": l.duration_min}


# ---------------------------------------------------------------------------
# 46 · staff
# ---------------------------------------------------------------------------

@router.get("/admin/content/courses")
def list_courses(current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Lesson.course_id, func.count(Lesson.id)).group_by(Lesson.course_id)).all())
    rows = db.execute(select(Course).where(Course.college_id == PLATFORM_TENANT).order_by(Course.semester, Course.title_en)).scalars().all()
    return {"courses": [_course_out(c, counts.get(c.id, 0)) for c in rows], "skills": list(SKILLS)}


@router.post("/admin/content/courses", status_code=status.HTTP_201_CREATED)
def create_course(req: CourseIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    if req.skill_key not in SKILLS:
        raise HTTPException(status_code=422, detail=f"skill_key must be one of {', '.join(SKILLS)}")
    c = Course(id=f"crs_{uuid.uuid4().hex[:16]}", college_id=PLATFORM_TENANT, title_en=req.title_en.strip(),
               title_ta=(req.title_ta or "").strip() or None, track=req.track.strip() or "All", semester=req.semester,
               skill_key=req.skill_key, status="draft")
    db.add(c)
    record_audit(db, current_user, "content.course_created", "course", c.id, {"semester": c.semester, "track": c.track}, college_id=PLATFORM_TENANT)
    db.commit()
    return _course_out(c, 0)


@router.get("/admin/content/courses/{course_id}")
def course_detail(course_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _course(db, course_id)
    lessons = _lessons(db, c.id)
    return {"course": _course_out(c, len(lessons)), "lessons": [_lesson_out(l) for l in lessons]}


@router.put("/admin/content/courses/{course_id}")
def update_course(course_id: str, req: CourseIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _course(db, course_id)
    if req.skill_key not in SKILLS:
        raise HTTPException(status_code=422, detail=f"skill_key must be one of {', '.join(SKILLS)}")
    c.title_en, c.title_ta, c.track, c.semester, c.skill_key = req.title_en.strip(), (req.title_ta or "").strip() or None, req.track.strip() or "All", req.semester, req.skill_key
    record_audit(db, current_user, "content.course_updated", "course", c.id, None, college_id=PLATFORM_TENANT)
    db.commit()
    return _course_out(c, len(_lessons(db, c.id)))


@router.post("/admin/content/courses/{course_id}/lessons", status_code=status.HTTP_201_CREATED)
def add_lesson(course_id: str, req: LessonIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _course(db, course_id)
    pos = req.position or (db.execute(select(func.max(Lesson.position)).where(Lesson.course_id == c.id)).scalar() or 0) + 1
    l = Lesson(id=f"lsn_{uuid.uuid4().hex[:16]}", college_id=PLATFORM_TENANT, course_id=c.id, position=pos, title_en=req.title_en.strip(),
               title_ta=(req.title_ta or "").strip() or None, body_en=req.body_en, body_ta=req.body_ta, duration_min=req.duration_min)
    db.add(l)
    record_audit(db, current_user, "content.lesson_added", "course", c.id, {"lesson_id": l.id}, college_id=PLATFORM_TENANT)
    db.commit()
    return _lesson_out(l)


@router.put("/admin/content/lessons/{lesson_id}")
def update_lesson(lesson_id: str, req: LessonIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    l = db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.college_id == PLATFORM_TENANT)).scalar_one_or_none()
    if l is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    l.title_en, l.title_ta, l.body_en, l.body_ta, l.duration_min = req.title_en.strip(), (req.title_ta or "").strip() or None, req.body_en, req.body_ta, req.duration_min
    if req.position:
        l.position = req.position
    record_audit(db, current_user, "content.lesson_updated", "course", l.course_id, {"lesson_id": l.id}, college_id=PLATFORM_TENANT)
    db.commit()
    return _lesson_out(l)


@router.delete("/admin/content/lessons/{lesson_id}")
def delete_lesson(lesson_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    l = db.execute(select(Lesson).where(Lesson.id == lesson_id, Lesson.college_id == PLATFORM_TENANT)).scalar_one_or_none()
    if l is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if db.execute(select(LessonProgress.id).where(LessonProgress.lesson_id == l.id)).first():
        raise HTTPException(status_code=409, detail="Students have completed this lesson; edit it instead of deleting")
    db.delete(l)
    record_audit(db, current_user, "content.lesson_deleted", "course", l.course_id, {"lesson_id": l.id}, college_id=PLATFORM_TENANT)
    db.commit()
    return {"success": True}


@router.post("/admin/content/courses/{course_id}/publish")
def publish(course_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _course(db, course_id)
    lessons = _lessons(db, c.id)
    if not lessons:
        raise HTTPException(status_code=422, detail="Add at least one lesson before publishing")
    missing = [l.position for l in lessons if not (l.title_ta and (l.body_ta or "").strip() and (l.body_en or "").strip())]
    if not c.title_ta or missing:
        raise HTTPException(status_code=422, detail=f"English and Tamil text are required (course title{'' if c.title_ta else ' missing'}; lessons {missing})")
    first = c.status != "published"
    c.status, c.published_at = "published", datetime.datetime.utcnow()
    record_audit(db, current_user, "content.course_published", "course", c.id, {"lessons": len(lessons)}, college_id=PLATFORM_TENANT)
    if first:   # flow step 2 + 7: students of that semester and track are told
        students = db.execute(select(Student).where(Student.semester == c.semester)).scalars().all()
        targets = {}
        for s in students:
            if c.track in ("All", s.track):
                targets.setdefault(s.college_id, []).append(s.user_id)
        for college_id, user_ids in targets.items():
            notify_users(db, user_ids, f"New course: {c.title_en}", None, title_ta=f"புதிய பாடநெறி: {c.title_ta}", kind="info",
                         link=f"/student/courses/{c.id}", college_id=college_id)
    db.commit()
    return _course_out(c, len(lessons))


@router.post("/admin/content/courses/{course_id}/unpublish")
def unpublish(course_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _course(db, course_id)
    c.status = "draft"
    record_audit(db, current_user, "content.course_unpublished", "course", c.id, None, college_id=PLATFORM_TENANT)
    db.commit()
    return _course_out(c, len(_lessons(db, c.id)))


@router.get("/admin/content/templates")
def list_templates(current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    rows = db.execute(select(NotificationTemplate).order_by(NotificationTemplate.key)).scalars().all()
    return {"templates": [{"key": t.key, "title_en": t.title_en, "title_ta": t.title_ta, "body_en": t.body_en, "body_ta": t.body_ta} for t in rows]}


@router.put("/admin/content/templates/{key}")
def save_template(key: str, req: TemplateIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    if not key.replace(".", "").replace("_", "").isalnum() or len(key) > 64:
        raise HTTPException(status_code=422, detail="Template keys look like leave.approved")
    t = db.execute(select(NotificationTemplate).where(NotificationTemplate.key == key)).scalar_one_or_none()
    if t is None:
        t = NotificationTemplate(id=f"tpl_{uuid.uuid4().hex[:16]}", college_id=PLATFORM_TENANT, key=key, title_en=req.title_en)
        db.add(t)
    t.title_en, t.title_ta, t.body_en, t.body_ta = req.title_en, req.title_ta, req.body_en, req.body_ta
    record_audit(db, current_user, "content.template_saved", "template", key, None, college_id=PLATFORM_TENANT)
    db.commit()
    return {"key": t.key, "title_en": t.title_en, "title_ta": t.title_ta, "body_en": t.body_en, "body_ta": t.body_ta}


# ---------------------------------------------------------------------------
# 11 · student
# ---------------------------------------------------------------------------

def _pick(en: Optional[str], ta: Optional[str], lang: str) -> Optional[str]:
    return ta if lang == "ta" and ta else en


@router.get("/student/courses")
def my_courses(lang: str = "en", current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    st = get_student_for_user(current_user, db)
    courses = visible_courses(db, st)
    totals = dict(db.execute(select(Lesson.course_id, func.count(Lesson.id)).where(Lesson.course_id.in_([c.id for c in courses] or ["_"]))
                             .group_by(Lesson.course_id)).all())
    done = dict(db.execute(select(Lesson.course_id, func.count(LessonProgress.id)).join(Lesson, Lesson.id == LessonProgress.lesson_id)
                           .where(LessonProgress.student_id == st.id).group_by(Lesson.course_id)).all())
    return {"semester": st.semester, "track": st.track, "courses": [{
        "id": c.id, "title": _pick(c.title_en, c.title_ta, lang), "track": c.track, "skill_key": c.skill_key,
        "lessons": totals.get(c.id, 0), "completed": done.get(c.id, 0),
        "pct": round(100 * done.get(c.id, 0) / totals[c.id]) if totals.get(c.id) else 0} for c in courses]}


def _visible_course(db: Session, st: Student, course_id: str) -> Course:
    c = next((c for c in visible_courses(db, st) if c.id == course_id), None)
    if c is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return c


@router.get("/student/courses/{course_id}")
def course_for_student(course_id: str, lang: str = "en", current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    st = get_student_for_user(current_user, db)
    c = _visible_course(db, st, course_id)
    lessons = _lessons(db, c.id)
    done = set(db.execute(select(LessonProgress.lesson_id).where(LessonProgress.student_id == st.id,
                                                                 LessonProgress.lesson_id.in_([l.id for l in lessons] or ["_"]))).scalars())
    return {"course": {"id": c.id, "title": _pick(c.title_en, c.title_ta, lang), "skill_key": c.skill_key},
            "lessons": [{"id": l.id, "position": l.position, "title": _pick(l.title_en, l.title_ta, lang),
                         "body": _pick(l.body_en, l.body_ta, lang), "duration_min": l.duration_min, "completed": l.id in done} for l in lessons]}


@router.post("/student/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: str, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    st = get_student_for_user(current_user, db)
    l = db.execute(select(Lesson).where(Lesson.id == lesson_id)).scalar_one_or_none()
    if l is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    c = _visible_course(db, st, l.course_id)
    existing = db.execute(select(LessonProgress).where(LessonProgress.student_id == st.id, LessonProgress.lesson_id == l.id)).scalar_one_or_none()
    if existing is None:
        db.add(LessonProgress(id=f"lp_{uuid.uuid4().hex[:16]}", college_id=st.college_id, student_id=st.id, lesson_id=l.id))
        db.flush()
    skill = feed_skill_bar(db, st, c.skill_key)                     # L33: course progress -> dashboard skill bar
    db.commit()
    return {"lesson_id": l.id, "completed": True, "already": existing is not None, "skill_key": c.skill_key, "skill_pct": skill}
