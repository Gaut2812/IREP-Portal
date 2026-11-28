"""Student dashboard (screen 12), Phase 2: what is behind each tile.

- problems: solved problems by topic, from accepted coding-lab submissions
- activity: a 12-week heat map of practice days (coding submissions, lessons completed, tests submitted) and the
  current and best streak worked out from it
- badges: every badge of the college, earned or locked, with how to earn it
- skills: what raises each skill bar
"""
import datetime
from typing import Dict, List, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.schema import (Badge, CodingProblem, CodingSubmission, LessonProgress, SkillScore, Student, StudentBadge,
                           TestAttempt)

HEATMAP_DAYS = 84

SKILL_HOW: Dict[str, Dict[str, str]] = {
    "dsa": {"en": "Solve coding-lab problems (Submit, all tests passing) and finish DSA lessons in My courses.",
            "ta": "கோடிங் லேப் கேள்விகளைத் தீர்க்கவும் (எல்லாச் சோதனைகளும் தேர்ச்சி) மற்றும் என் பாடங்களில் DSA பாடங்களை முடிக்கவும்."},
    "aptitude": {"en": "Take practice tests: your best score in each counts.",
                 "ta": "பயிற்சித் தேர்வுகளை எழுதுங்கள்: ஒவ்வொன்றிலும் உங்கள் சிறந்த மதிப்பெண் கணக்கில் வரும்."},
    "cloud": {"en": "Finish cloud lessons and virtual labs, and earn a cloud certificate.",
              "ta": "கிளவுட் பாடங்களையும் மெய்நிகர் லேப்களையும் முடித்து, கிளவுட் சான்றிதழ் பெறுங்கள்."},
    "track": {"en": "Work on your track: Sprint Board cards done, code reviews approved and track courses finished.",
              "ta": "உங்கள் டிராக்கில் வேலை செய்யுங்கள்: ஸ்பிரிண்ட் போர்டு அட்டைகள், ஏற்கப்பட்ட கோடு மதிப்பாய்வுகள், டிராக் பாடங்கள்."},
    "future_skills": {"en": "Finish AI and future-skills courses (for example Generative AI foundations).",
                      "ta": "AI மற்றும் எதிர்காலத் திறன் பாடங்களை முடிக்கவும் (எ.கா. ஜெனரேட்டிவ் AI அடிப்படைகள்)."},
    "communication": {"en": "Mock interviews: your trainer's rubric scores for communication count here.",
                      "ta": "மாதிரி நேர்காணல்கள்: தொடர்புத் திறனுக்கான பயிற்சியாளரின் மதிப்பெண்கள் இங்கே கணக்கில் வரும்."},
}


def activity_days(db: Session, student: Student, since: datetime.date) -> Dict[datetime.date, int]:
    """Practice actions per day: coding submissions, lessons completed, tests submitted."""
    start = datetime.datetime.combine(since, datetime.time.min)
    days: Dict[datetime.date, int] = {}
    for (at,) in db.execute(select(CodingSubmission.created_at).where(CodingSubmission.student_id == student.id, CodingSubmission.created_at >= start)):
        days[at.date()] = days.get(at.date(), 0) + 1
    for (at,) in db.execute(select(LessonProgress.completed_at).where(LessonProgress.student_id == student.id, LessonProgress.completed_at >= start)):
        days[at.date()] = days.get(at.date(), 0) + 1
    for (at,) in db.execute(select(TestAttempt.submitted_at).where(TestAttempt.student_id == student.id, TestAttempt.submitted_at.is_not(None),
                                                                   TestAttempt.submitted_at >= start)):
        days[at.date()] = days.get(at.date(), 0) + 1
    return days


def streaks(active: Set[datetime.date], today: datetime.date) -> tuple:
    """(current, best) runs of consecutive active days; today not done yet does not break the current run."""
    current, d = 0, today if today in active else today - datetime.timedelta(days=1)
    while d in active:
        current += 1
        d -= datetime.timedelta(days=1)
    best = run = 0
    prev: Optional[datetime.date] = None
    for day in sorted(active):
        run = run + 1 if prev and (day - prev).days == 1 else 1
        best, prev = max(best, run), day
    return current, best


def solved_recently(db: Session, student: Student, days: int = 30) -> int:
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    return db.execute(select(func.count(func.distinct(CodingSubmission.problem_id))).where(
        CodingSubmission.student_id == student.id, CodingSubmission.status == "Accepted", CodingSubmission.created_at >= since)).scalar_one()


def best_streak(db: Session, student: Student) -> int:
    today = datetime.date.today()
    _, best = streaks(set(activity_days(db, student, today - datetime.timedelta(days=365))), today)
    return max(best, student.streak_days or 0)


def build_details(db: Session, student: Student, lang: str = "en") -> dict:
    lg = "ta" if lang == "ta" else "en"
    today = datetime.date.today()

    # problems solved, by topic (distinct problems with an accepted submission)
    rows = db.execute(select(CodingProblem.topic, CodingProblem.title, func.max(CodingSubmission.created_at))
                      .join(CodingSubmission, CodingSubmission.problem_id == CodingProblem.id)
                      .where(CodingSubmission.student_id == student.id, CodingSubmission.status == "Accepted")
                      .group_by(CodingProblem.id, CodingProblem.topic, CodingProblem.title)).all()
    by_topic: Dict[str, int] = {}
    for topic, _, _ in rows:
        by_topic[topic or "Other"] = by_topic.get(topic or "Other", 0) + 1
    recent = sorted(rows, key=lambda r: r[2], reverse=True)[:5]

    # activity heat map and streaks
    since = today - datetime.timedelta(days=HEATMAP_DAYS - 1)
    days = activity_days(db, student, since)
    current, best = streaks(set(activity_days(db, student, today - datetime.timedelta(days=365))), today)

    # badges: earned first, then locked with how to earn them
    earned = dict(db.execute(select(StudentBadge.badge_id, StudentBadge.earned_on).where(StudentBadge.student_id == student.id)).all())
    badges = db.execute(select(Badge).where(Badge.college_id == student.college_id).order_by(Badge.name_en)).scalars().all()

    skills = db.execute(select(SkillScore).where(SkillScore.student_id == student.id).order_by(SkillScore.sort_order)).scalars().all()
    return {
        "problems": {
            "total": student.problems_solved, "in_lab": len(rows), "this_month": solved_recently(db, student),
            "by_topic": [{"topic": t, "solved": n} for t, n in sorted(by_topic.items(), key=lambda x: -x[1])],
            "recent": [{"title": title, "solved_on": at.date().isoformat()} for _, title, at in recent],
        },
        "activity": {
            "days": [{"date": (since + datetime.timedelta(days=i)).isoformat(), "count": days.get(since + datetime.timedelta(days=i), 0)}
                     for i in range(HEATMAP_DAYS)],
            # the recorded streak also counts practice from before these records; show whichever is longer
            "current": max(current, student.streak_days or 0), "best": max(best, student.streak_days or 0),
        },
        "badges": [{"id": b.id, "name": (b.name_ta if lg == "ta" and b.name_ta else b.name_en),
                    "description": (b.description_ta if lg == "ta" and b.description_ta else b.description_en),
                    "icon": b.icon, "earned": b.id in earned, "earned_on": earned[b.id].isoformat() if earned.get(b.id) else None}
                   for b in sorted(badges, key=lambda b: (b.id not in earned, b.name_en))],
        "skills": [{"key": s.skill_key, "skill": (s.label_ta if lg == "ta" and s.label_ta else s.label_en), "percentage": s.percentage,
                    "how": SKILL_HOW.get(s.skill_key, {}).get(lg, "")} for s in skills],
    }
