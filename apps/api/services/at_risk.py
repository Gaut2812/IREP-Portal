"""At-risk rule engine (Screen 13/14).

The nightly job evaluates four configurable rules per college and opens one
flag per (student, reason) that is not already open:
  - readiness score below `score_below`
  - attendance below `attendance_below`
  - `missed_sessions` or more sessions missed in the last 30 days
  - a sprint task assigned to the student that has been in progress for more
    than `project_delay_days`
Parent alerts are sent once per flag and respect quiet hours.
"""
import datetime
import uuid
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.schema import (
    AtRiskFlag, FlagAction, RulesConfig, Student, SessionAttendance, SessionItem,
    SprintTask, ParentStudent, User,
)
from services.notifications import notify_user

RESOLVED_COOLDOWN_DAYS = 14

REASON_TEXT = {
    "low_score": {"en": "Score {v}", "ta": "மதிப்பெண் {v}"},
    "low_attendance": {"en": "Attendance {v}%", "ta": "வருகை {v}%"},
    "missed_sessions": {"en": "{v} sessions missed", "ta": "{v} அமர்வுகள் தவறின"},
    "project_delay": {"en": "Project delay", "ta": "புராஜெக்ட் தாமதம்"},
}
ACTION_LABEL = {
    "parent_call": {"en": "Parent call", "ta": "பெற்றோர் அழைப்பு"},
    "extra_saturday": {"en": "Extra Sat", "ta": "கூடுதல் சனி"},
    "mentor": {"en": "Mentor", "ta": "வழிகாட்டி"},
}


def get_rules(db: Session, college_id: str) -> RulesConfig:
    cfg = db.execute(select(RulesConfig).filter_by(college_id=college_id)).scalars().first()
    if not cfg:
        cfg = RulesConfig(id=f"rules_{college_id}", college_id=college_id)
        db.add(cfg)
        db.flush()
    return cfg


def in_quiet_hours(cfg: RulesConfig, now: Optional[datetime.datetime] = None) -> bool:
    hour = (now or datetime.datetime.now()).hour
    if cfg.quiet_hours_start > cfg.quiet_hours_end:   # e.g. 21 -> 8 wraps midnight
        return hour >= cfg.quiet_hours_start or hour < cfg.quiet_hours_end
    return cfg.quiet_hours_start <= hour < cfg.quiet_hours_end


def _severity(reason: str, value: int, cfg: RulesConfig) -> str:
    if reason == "low_score":
        return "high" if value < cfg.score_below - 10 else "medium"
    if reason == "low_attendance":
        return "high" if value < cfg.attendance_below - 10 else "medium"
    if reason == "missed_sessions":
        return "high" if value >= cfg.missed_sessions + 2 else "medium"
    return "medium"


def _suggested_action(reason: str) -> str:
    return {"low_attendance": "parent_call", "low_score": "extra_saturday", "missed_sessions": "parent_call", "project_delay": "mentor"}[reason]


def evaluate_student(db: Session, student: Student, cfg: RulesConfig, now: datetime.datetime) -> List[Dict]:
    """Return the list of (reason_key, value) that currently apply to a student."""
    hits = []
    if student.readiness_score < cfg.score_below:
        hits.append(("low_score", student.readiness_score))
    if student.attendance_pct < cfg.attendance_below:
        hits.append(("low_attendance", student.attendance_pct))
    since = now - datetime.timedelta(days=30)
    missed = db.execute(
        select(func.count(SessionAttendance.id))
        .join(SessionItem, SessionItem.id == SessionAttendance.session_id)
        .where(SessionAttendance.student_id == student.id, SessionAttendance.status == "Absent", SessionItem.scheduled_start >= since)
    ).scalar_one()
    if missed >= cfg.missed_sessions:
        hits.append(("missed_sessions", missed))
    initials = None
    user = db.execute(select(User).filter_by(id=student.user_id)).scalar_one_or_none()
    if user:
        initials = user.avatar_initials
    if initials:
        delayed = db.execute(
            select(func.count(SprintTask.id)).where(
                SprintTask.college_id == student.college_id,
                SprintTask.assignee_initials == initials,
                SprintTask.column_name == "in_progress",
                SprintTask.updated_at < now - datetime.timedelta(days=cfg.project_delay_days),
            )
        ).scalar_one()
        if delayed:
            hits.append(("project_delay", delayed))
    return [{"reason": r, "value": v} for r, v in hits]


def run_rules(db: Session, college_id: str, now: Optional[datetime.datetime] = None) -> int:
    """Open flags for every rule hit without an open flag. Returns new flags."""
    now = now or datetime.datetime.utcnow()
    cfg = get_rules(db, college_id)
    students = db.execute(select(Student).filter_by(college_id=college_id)).scalars().all()
    # Open flags block duplicates; a resolved flag also blocks re-flagging for a
    # cooldown period so a student is not re-flagged the night after a trainer
    # closes the case.
    cooldown = now - datetime.timedelta(days=RESOLVED_COOLDOWN_DAYS)
    rows = db.execute(
        select(AtRiskFlag.student_id, AtRiskFlag.reason_key, AtRiskFlag.status, AtRiskFlag.resolved_at)
        .where(AtRiskFlag.college_id == college_id)
    ).all()
    existing = {(s, r) for s, r, status, resolved_at in rows
                if status != "resolved" or (resolved_at is not None and resolved_at >= cooldown)}
    created = 0
    for st in students:
        for hit in evaluate_student(db, st, cfg, now):
            key = (st.id, hit["reason"])
            if key in existing:
                continue
            text = REASON_TEXT[hit["reason"]]["en"].format(v=hit["value"])
            db.add(AtRiskFlag(
                id=f"flag_{uuid.uuid4().hex[:18]}", college_id=college_id, student_id=st.id, batch_id=st.batch_id,
                reason_key=hit["reason"], reason_text=text, severity=_severity(hit["reason"], hit["value"], cfg),
                suggested_action=_suggested_action(hit["reason"]), status="open", flagged_on=now.date(),
            ))
            existing.add(key)
            created += 1
    db.flush()
    return created


def notify_parent_once(db: Session, flag: AtRiskFlag, student_name: str, cfg: Optional[RulesConfig] = None,
                       now: Optional[datetime.datetime] = None) -> bool:
    """Send the parent alert for a flag exactly once, outside quiet hours."""
    if flag.parent_notified:
        return False
    cfg = cfg or get_rules(db, flag.college_id)
    if in_quiet_hours(cfg, now):
        return False
    links = db.execute(select(ParentStudent).filter_by(student_id=flag.student_id, college_id=flag.college_id)).scalars().all()
    if not links:
        return False
    for link in links:
        notify_user(
            db, link.parent_user_id,
            f"Support plan for {student_name}",
            f"The trainer has flagged: {flag.reason_text}. Suggested next step: {ACTION_LABEL[flag.suggested_action]['en']}.",
            title_ta=f"{student_name}-க்கான ஆதரவுத் திட்டம்",
            body_ta=f"பயிற்சியாளர் குறிப்பு: {flag.reason_text}. அடுத்த படி: {ACTION_LABEL[flag.suggested_action]['ta']}.",
            kind="alert", link="/parent", channels=("in_app", "sms"), college_id=flag.college_id,
        )
    flag.parent_notified = True
    flag.parent_notified_at = now or datetime.datetime.utcnow()
    return True
