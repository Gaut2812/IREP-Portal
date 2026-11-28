"""Screen 12: student dashboard payload assembled from rows."""
import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.security import TokenPayload
from models.schema import (
    Student, SkillScore, ReadinessSnapshot, SessionItem, SprintTask, StudentProject,
    Event, Badge, StudentBadge, Certificate, SessionAttendance, PullRequest, Team, TeamMember,
)
from services.readiness import latest_snapshot, get_config, COMPONENT_LABELS
from services.dashboard_details import best_streak, solved_recently

DAY_TA = {"Mon": "திங்", "Tue": "செவ்", "Wed": "புத", "Thu": "வியா", "Fri": "வெள்", "Sat": "சனி", "Sun": "ஞாயி"}


def _greeting(name: str, lang: str, now: Optional[datetime.datetime] = None) -> str:
    now = now or datetime.datetime.now()
    first = (name or "").split(" ")[0]
    hour = now.hour
    if lang == "ta":
        word = "காலை வணக்கம்" if hour < 12 else ("மதிய வணக்கம்" if hour < 17 else "மாலை வணக்கம்")
        return f"{word}, {first} 👋"
    word = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
    return f"{word}, {first} 👋"


def _week_sessions(db: Session, student: Student):
    """Sessions of the student's batch for the current ISO week (Mon–Sat); if the
    week is empty, the most recent week that has sessions. Classes run Mon–Sat: on a Sunday the
    week that matters is the one starting tomorrow (the seed schedules it the same way)."""
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    if today.weekday() == 6:
        monday += datetime.timedelta(days=7)
    q = select(SessionItem).where(SessionItem.college_id == student.college_id)
    if student.batch_id:
        q = q.where(SessionItem.batch_id == student.batch_id)
    rows = db.execute(q.order_by(SessionItem.scheduled_start)).scalars().all()
    if not rows:
        return [], monday
    in_week = [r for r in rows if monday <= r.scheduled_start.date() <= monday + datetime.timedelta(days=6)]
    if in_week:
        return in_week, monday
    last = rows[-1].scheduled_start.date()
    monday = last - datetime.timedelta(days=last.weekday())
    return [r for r in rows if monday <= r.scheduled_start.date() <= monday + datetime.timedelta(days=6)], monday


def _duration_label(minutes: int, lang: str) -> str:
    hrs = minutes / 60
    if hrs >= 1 and float(hrs).is_integer():
        n = int(hrs)
        if lang == "ta":
            return f"{n} மணி"
        return f"{n} hr" if n == 1 else f"{n} hrs"
    return f"{minutes} {'நிமி' if lang == 'ta' else 'min'}"


def build_student_dashboard(db: Session, student: Student, current_user: TokenPayload, lang: str = "en") -> dict:
    college_id = student.college_id
    snap = latest_snapshot(db, student)
    cfg = get_config(db, college_id)

    # previous month comparison for problems solved: use the snapshot delta semantic for score,
    # and 30-day accepted submissions for problems
    skills = db.execute(
        select(SkillScore).filter_by(student_id=student.id, college_id=college_id).order_by(SkillScore.sort_order)
    ).scalars().all()

    sessions, monday = _week_sessions(db, student)
    from services.live_sessions import session_status
    attendance_by_session = {a.session_id: a for a in db.execute(select(SessionAttendance).where(
        SessionAttendance.student_id == student.id, SessionAttendance.session_id.in_([s.id for s in sessions] or ["_"]))).scalars()}
    week_no = sessions[0].week_no if sessions and sessions[0].week_no else None

    # Current project: the in-progress project + sprint board progress
    project = db.execute(
        select(StudentProject).filter_by(student_id=student.id, college_id=college_id, status="in_progress")
        .order_by(StudentProject.is_featured.desc())
    ).scalars().first()
    # Progress and "my open tasks" come from my team's active sprint, the same numbers the board shows
    # (before, every task in the college was counted and "mine" was matched by initials).
    from services.sprint_board import active_sprint
    team = db.execute(
        select(Team).join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.student_id == student.id, Team.college_id == college_id)
    ).scalars().first()
    sprint = active_sprint(db, team) if team else None
    tasks = db.execute(
        select(SprintTask).where(SprintTask.college_id == college_id, SprintTask.team_id == team.id,
                                 SprintTask.sprint_id == (sprint.id if sprint else None))
    ).scalars().all() if team else []
    total_pts = sum(t.story_points for t in tasks)
    done_pts = sum(t.story_points for t in tasks if t.column_name == "done")
    open_mine = len([t for t in tasks if t.column_name != "done" and t.assignee_student_id == student.id])
    pending_prs = db.execute(
        select(func.count(PullRequest.id)).where(PullRequest.college_id == college_id, PullRequest.author_id == student.id, PullRequest.status == "pending")
    ).scalar_one()

    # Upcoming: personal events + batch events + college-wide, from today, next 5
    now = datetime.datetime.now()
    ev_q = select(Event).where(
        Event.college_id == college_id, Event.status == "published",
        Event.starts_at >= now - datetime.timedelta(hours=12),
        (Event.student_id == student.id) | (Event.student_id.is_(None)),
        (Event.batch_id == student.batch_id) | (Event.batch_id.is_(None)),
        Event.audience.in_(["students", "all"]),
    ).order_by(Event.starts_at).limit(5)
    events = db.execute(ev_q).scalars().all()

    badges = db.execute(
        select(Badge, StudentBadge.earned_on)
        .join(StudentBadge, StudentBadge.badge_id == Badge.id)
        .where(StudentBadge.student_id == student.id, StudentBadge.college_id == college_id)
        .order_by(StudentBadge.earned_on.desc())
    ).all()

    attended = db.execute(
        select(func.count(SessionAttendance.id)).where(SessionAttendance.student_id == student.id, SessionAttendance.status == "Present")
    ).scalar_one()
    total_sessions = db.execute(
        select(func.count(SessionAttendance.id)).where(SessionAttendance.student_id == student.id)
    ).scalar_one()

    def ev_date(e: Event) -> str:
        d = e.starts_at
        if d.date() - datetime.date.today() <= datetime.timedelta(days=6) and d.date() >= datetime.date.today():
            day = d.strftime("%a")
            label = DAY_TA.get(day, day) if lang == "ta" else day
            return f"{label} {d.strftime('%I:%M %p').lstrip('0')}" if d.hour not in (0, 9, 10) else label
        return d.strftime("%b %d")

    return {
        "student": {
            "id": student.id,
            "name": current_user.name or "",
            "greeting": _greeting(current_user.name or "", lang),
            "semester": student.semester,
            "branch": student.branch,
            "batch": student.batch_name,
            "track": student.track,
            "week_label": f"Week {week_no} of 12" if week_no else "",
            "readiness_score": snap.score if snap else student.readiness_score,
            "readiness_band": snap.band if snap else student.readiness_band,
            "readiness_delta": snap.delta if snap else student.readiness_delta,
            "has_snapshot": snap is not None,
            "snapshot_date": snap.snapshot_date.isoformat() if snap else None,
            "problems_solved": student.problems_solved,
            "problems_delta": solved_recently(db, student),          # distinct problems accepted in the last 30 days
            "attendance_pct": student.attendance_pct,
            "attendance_target": 85,
            "sessions_attended": attended,
            "sessions_total": total_sessions,
            "streak_days": student.streak_days,
            "streak_best": best_streak(db, student),
        },
        "skill_progress": [
            {"key": s.skill_key, "skill": (s.label_ta if lang == "ta" and s.label_ta else s.label_en), "percentage": s.percentage, "color": s.color}
            for s in skills
        ],
        "this_week": [
            {
                "id": s.id,
                "day": (DAY_TA.get(s.scheduled_start.strftime("%a"), s.scheduled_start.strftime("%a")) if lang == "ta" else s.scheduled_start.strftime("%a")),
                "topic": s.title,
                "duration": _duration_label(s.duration_min, lang),
                "type": s.session_type,
                "status": session_status(s, attendance_by_session.get(s.id), datetime.datetime.now()),   # from the clock, not the stored value
                "is_lab": s.duration_min >= 120 or s.session_type != "Live",
            }
            for s in sessions
        ],
        "current_project": {
            "id": project.id if project else None,
            "title": project.title if project else None,
            "subtitle": (f"{project.category.replace('_', ' ').title()} · Team of {project.team_size} · {project.team_name}" if project else None),
            "progress_pct": int(round(done_pts * 100 / total_pts)) if total_pts else 0,
            "open_tasks": open_mine,
            "pending_prs": pending_prs,
        } if project else None,
        "upcoming_events": [
            {"id": e.id, "title": (e.title_ta if lang == "ta" and e.title_ta else e.title_en), "kind": e.kind, "date": ev_date(e), "starts_at": e.starts_at.isoformat()}
            for e in events
        ],
        "badges": [
            {"id": b.id, "name": (b.name_ta if lang == "ta" and b.name_ta else b.name_en),
             "description": (b.description_ta if lang == "ta" and b.description_ta else b.description_en),
             "icon": b.icon, "earned_on": earned.isoformat() if earned else None}
            for b, earned in badges
        ],
        "config": {"ready_min": cfg.band_ready_min, "nearly_min": cfg.band_nearly_min},
    }


def build_why_score(db: Session, student: Student, lang: str = "en") -> dict:
    snap = latest_snapshot(db, student)
    cfg = get_config(db, student.college_id)
    rows = (snap.breakdown if snap and snap.breakdown else [])
    return {
        "score": snap.score if snap else student.readiness_score,
        "band": snap.band if snap else student.readiness_band,
        "snapshot_date": snap.snapshot_date.isoformat() if snap else None,
        "thresholds": {"ready_min": cfg.band_ready_min, "nearly_min": cfg.band_nearly_min},
        "components": [
            {
                "key": r["key"],
                "label": (r.get("label_ta") if lang == "ta" and r.get("label_ta") else r.get("label_en", r["key"])),
                "value": r["value"],
                "weight": r["weight"],
                "contribution": r["contribution"],
            }
            for r in rows
        ],
        "history": [
            {"date": h.snapshot_date.isoformat(), "score": h.score}
            for h in db.execute(
                select(ReadinessSnapshot).filter_by(student_id=student.id, college_id=student.college_id)
                .order_by(ReadinessSnapshot.snapshot_date.asc()).limit(12)
            ).scalars().all()
        ],
    }
