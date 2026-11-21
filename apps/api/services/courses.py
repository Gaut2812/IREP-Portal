"""My courses (screen 11) and its effect on the dashboard skill bars (link L33)."""
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.security import PLATFORM_TENANT
from models.schema import Course, Lesson, LessonProgress, SkillScore, Student


def visible_courses(db: Session, student: Student) -> List[Course]:
    """Published library courses for the student's semester and track (platform tenant, read-only)."""
    return db.execute(select(Course).where(
        Course.college_id == PLATFORM_TENANT, Course.status == "published", Course.semester == student.semester,
        Course.track.in_([student.track, "All"])).order_by(Course.title_en)).scalars().all()


def skill_progress(db: Session, student: Student, skill_key: str) -> int:
    """Completion % over the student's visible published courses that feed this skill."""
    course_ids = [c.id for c in visible_courses(db, student) if c.skill_key == skill_key]
    if not course_ids:
        return 0
    total = db.execute(select(func.count(Lesson.id)).where(Lesson.course_id.in_(course_ids))).scalar_one()
    done = db.execute(select(func.count(LessonProgress.id)).join(Lesson, Lesson.id == LessonProgress.lesson_id)
                      .where(LessonProgress.student_id == student.id, Lesson.course_id.in_(course_ids))).scalar_one()
    return round(100 * done / total) if total else 0


def feed_skill_bar(db: Session, student: Student, skill_key: str) -> int:
    """L33: the skill bar never drops below course completion for that skill."""
    pct = skill_progress(db, student, skill_key)
    row = db.execute(select(SkillScore).where(SkillScore.student_id == student.id, SkillScore.skill_key == skill_key)).scalar_one_or_none()
    if row is not None and pct > row.percentage:
        row.percentage = pct
    return row.percentage if row is not None else pct
