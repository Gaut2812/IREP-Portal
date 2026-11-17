"""Screen 13: trainer dashboard computed from rows."""
import datetime
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.security import TokenPayload
from models.schema import (
    Batch, BatchTrainer, Student, SessionItem, SessionAttendance, PullRequest, AtRiskFlag, User, Trainer,
)
from services.at_risk import ACTION_LABEL, get_rules

STATUS_TA = {"Done": "முடிந்தது", "Next": "அடுத்து", "Later": "பின்னர்", "Live": "நேரலை"}


def trainer_batches(db: Session, trainer: Trainer) -> List[Batch]:
    return list(db.execute(
        select(Batch).join(BatchTrainer, BatchTrainer.batch_id == Batch.id)
        .where(BatchTrainer.trainer_id == trainer.id, Batch.college_id == trainer.college_id, Batch.is_active.is_(True))
        .order_by(Batch.short_name)
    ).scalars().all())


def _schedule_day(db: Session, batch_ids: List[str], today: datetime.date) -> datetime.date:
    """Today if the trainer has sessions today, else the nearest day that has."""
    rows = db.execute(
        select(SessionItem.scheduled_start).where(SessionItem.batch_id.in_(batch_ids)).order_by(SessionItem.scheduled_start)
    ).scalars().all()
    days = sorted({r.date() for r in rows})
    if not days:
        return today
    if today in days:
        return today
    future = [d for d in days if d > today]
    return future[0] if future else days[-1]


def _attendance_for_day(db: Session, batch_ids: List[str], day: datetime.date):
    sessions = db.execute(
        select(SessionItem).where(SessionItem.batch_id.in_(batch_ids), func.date(SessionItem.scheduled_start) == day.isoformat())
    ).scalars().all()
    if not sessions:
        return None, 0
    ids = [s.id for s in sessions]
    total = db.execute(select(func.count(SessionAttendance.id)).where(SessionAttendance.session_id.in_(ids))).scalar_one()
    present = db.execute(
        select(func.count(SessionAttendance.id)).where(SessionAttendance.session_id.in_(ids), SessionAttendance.status == "Present")
    ).scalar_one()
    if total == 0:
        return None, len(sessions)
    return round(present * 100 / total), len(sessions)


def build_trainer_dashboard(db: Session, trainer: Trainer, current_user: TokenPayload, lang: str = "en",
                            now: Optional[datetime.datetime] = None) -> dict:
    now = now or datetime.datetime.now()   # session times are stored as campus-local naive datetimes
    today = now.date()
    college_id = trainer.college_id
    batches = trainer_batches(db, trainer)
    batch_ids = [b.id for b in batches] or ["__none__"]

    student_count = db.execute(select(func.count(Student.id)).where(Student.batch_id.in_(batch_ids))).scalar_one()
    college_count = db.execute(select(func.count(func.distinct(Batch.college_id))).where(Batch.id.in_(batch_ids))).scalar_one()

    # Attendance today vs the same weekday last week
    att_day = _schedule_day(db, batch_ids, today)
    att_pct, sessions_today = _attendance_for_day(db, batch_ids, att_day)
    last_week_pct, _ = _attendance_for_day(db, batch_ids, att_day - datetime.timedelta(days=7))
    delta = (att_pct - last_week_pct) if (att_pct is not None and last_week_pct is not None) else None

    # Pending reviews (college-wide queue) and ageing
    pending = db.execute(select(PullRequest).where(PullRequest.college_id == college_id, PullRequest.status == "pending")).scalars().all()
    older = len([p for p in pending if p.created_at and (now - p.created_at) > datetime.timedelta(days=2)])

    # At-risk flags in the trainer's batches
    flags = db.execute(
        select(AtRiskFlag).where(AtRiskFlag.college_id == college_id, AtRiskFlag.batch_id.in_(batch_ids), AtRiskFlag.status != "resolved")
    ).scalars().all()
    flagged_students = {f.student_id for f in flags}
    parents_notified = len({f.student_id for f in flags if f.parent_notified})

    # Batch readiness averages
    readiness_rows = db.execute(
        select(Batch.short_name, func.avg(Student.readiness_score)).join(Student, Student.batch_id == Batch.id)
        .where(Batch.id.in_(batch_ids)).group_by(Batch.short_name)
    ).all()
    by_short = {r[0]: int(round(r[1] or 0)) for r in readiness_rows}
    batch_readiness = [
        {"batch_id": b.id, "batch": b.short_name, "score": by_short.get(b.short_name, 0), "students": None,
         "color": "teal" if by_short.get(b.short_name, 0) >= 75 else "blue"}
        for b in batches
    ]

    # Schedule for the dashboard day
    sched_day = _schedule_day(db, batch_ids, today)
    sessions = db.execute(
        select(SessionItem).where(SessionItem.batch_id.in_(batch_ids), func.date(SessionItem.scheduled_start) == sched_day.isoformat())
        .order_by(SessionItem.scheduled_start)
    ).scalars().all()
    batch_name = {b.id: b.short_name + " · Sem " + str(b.semester) for b in batches}
    schedule = []
    next_assigned = False
    for s in sessions:
        if s.scheduled_end <= now or s.status == "Attended":
            status = "Done"
        elif s.scheduled_start <= now <= s.scheduled_end:
            status = "Live"
        elif not next_assigned:
            status, next_assigned = "Next", True
        else:
            status = "Later"
        schedule.append({
            "id": s.id, "time": s.scheduled_start.strftime("%I:%M %p").lstrip("0"),
            "batch": batch_name.get(s.batch_id, s.track), "topic": s.title, "status": status,
            "status_label": STATUS_TA.get(status, status) if lang == "ta" else status,
            "can_enter": status in ("Next", "Live"), "room": f"/live/{s.id}",
        })

    # Students needing support: open flags below the score threshold, lowest first
    rules = get_rules(db, college_id)
    support_rows = []
    if flags:
        student_rows = db.execute(
            select(Student, User.name).join(User, User.id == Student.user_id).where(Student.id.in_(list(flagged_students)))
        ).all()
        name_of = {st.id: nm for st, nm in student_rows}
        by_student = {st.id: st for st, _ in student_rows}
        primary = {}
        severity_rank = {"high": 0, "medium": 1, "low": 2}
        for f in sorted(flags, key=lambda f: (severity_rank.get(f.severity, 9), f.flagged_on)):
            primary.setdefault(f.student_id, f)
        for sid, f in primary.items():
            st = by_student.get(sid)
            if not st or st.readiness_score >= rules.score_below:
                continue
            support_rows.append({
                "flag_id": f.id, "student_id": sid, "name": name_of.get(sid, "Student"),
                "batch": next((b.short_name for b in batches if b.id == st.batch_id), ""),
                "score": st.readiness_score, "issue": f.reason_text, "reason_key": f.reason_key, "severity": f.severity,
                "action": f.suggested_action, "action_label": ACTION_LABEL[f.suggested_action][lang if lang in ("en", "ta") else "en"],
                "parent_notified": f.parent_notified, "status": f.status,
            })
        support_rows.sort(key=lambda r: (r["score"], r["name"]))

    return {
        "trainer": {"name": current_user.name or "", "designation": trainer.designation},
        "kpis": {
            "active_batches": {"value": len(batches), "students": student_count, "colleges": college_count},
            "today_attendance": {"value": att_pct, "delta_vs_last_week": delta, "sessions": sessions_today, "day": att_day.isoformat()},
            "pending_code_reviews": {"value": len(pending), "older_than_2_days": older},
            "at_risk_students": {"value": len(flagged_students), "parents_notified": parents_notified, "open_flags": len(flags)},
        },
        "batch_readiness": batch_readiness,
        "today_schedule": {"date": sched_day.isoformat(), "label": sched_day.strftime("%a, %b %d"), "is_today": sched_day == today, "items": schedule},
        "students_needing_support": support_rows[:8],
        "thresholds": {"score_below": rules.score_below, "attendance_below": rules.attendance_below},
        "quick_actions": [
            {"key": "mark_attendance", "href": "/trainer/attendance", "variant": "blue"},
            {"key": "create_test", "href": "/trainer/assessments", "variant": "outline"},
            {"key": "review_prs", "href": "/trainer/reviews", "variant": "outline"},
            {"key": "send_parent_update", "href": "/trainer/messages", "variant": "outline"},
            {"key": "schedule_mock", "href": "/trainer/interviews", "variant": "outline"},
            {"key": "monthly_report", "href": "/trainer/reports", "variant": "teal"},
        ],
    }
