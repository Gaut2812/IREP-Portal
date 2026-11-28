"""At-risk rule engine (Screen 13/14).

The nightly job evaluates four configurable rules per college and opens one
flag per (student, reason) that is not already open:
  - readiness score below `score_below`
  - attendance below `attendance_below`
  - `missed_sessions` or more sessions missed in the last 30 days
  - a sprint task assigned to the student that has been in progress for more
    than `project_delay_days`
Parent calls (L31) alert the parent once per flag, post in the trainer thread,
and are held in the outbox over the college's quiet hours.
"""
import datetime
import uuid
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.schema import (
    AtRiskFlag, BatchTrainer, DirectMessage, FlagAction, OutboxEvent, RulesConfig, Student, SessionAttendance, SessionItem,
    SprintTask, ParentStudent, Trainer, TrainerDirectThread, User,
)
from services.notifications import notify_user
from services.outbox import emit, handler

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


def run_rules(db: Session, college_id: str, now: Optional[datetime.datetime] = None,
              created_out: Optional[List[AtRiskFlag]] = None) -> int:
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
            flag = AtRiskFlag(
                id=f"flag_{uuid.uuid4().hex[:18]}", college_id=college_id, student_id=st.id, batch_id=st.batch_id,
                reason_key=hit["reason"], reason_text=text, severity=_severity(hit["reason"], hit["value"], cfg),
                suggested_action=_suggested_action(hit["reason"]), status="open", flagged_on=now.date(),
            )
            db.add(flag)
            if created_out is not None:
                created_out.append(flag)
            existing.add(key)
            created += 1
    db.flush()
    return created


def quiet_seconds_left(cfg: RulesConfig, now: Optional[datetime.datetime] = None) -> int:
    """Seconds until the college's quiet hours end (0 outside them)."""
    now = now or datetime.datetime.now()
    if not in_quiet_hours(cfg, now):
        return 0
    until = now.replace(hour=cfg.quiet_hours_end, minute=0, second=0, microsecond=0)
    if until <= now:
        until += datetime.timedelta(days=1)
    return int((until - now).total_seconds())


def _parent_thread(db: Session, trainer_user_id: str, parent: User, student_id: str, student_name: str) -> TrainerDirectThread:
    t = db.execute(select(TrainerDirectThread).where(
        TrainerDirectThread.college_id == parent.college_id, TrainerDirectThread.trainer_user_id == trainer_user_id,
        TrainerDirectThread.contact_user_id == parent.id)).scalars().first()
    if t is None:
        initials = "".join(w[0] for w in parent.name.replace(".", " ").split()[:2]).upper() or "P"
        t = TrainerDirectThread(id=f"th_{uuid.uuid4().hex[:16]}", college_id=parent.college_id, trainer_user_id=trainer_user_id,
                                contact_user_id=parent.id, student_id=student_id, contact_name=parent.name, contact_category="Parents",
                                contact_role_chip=f"Parent · {student_name}", avatar_initials=initials[:8],
                                pref_language="Prefers Tamil" if parent.language_pref == "ta" else "Prefers English")
        db.add(t)
        db.flush()
    return t


RENOTIFY_AFTER = datetime.timedelta(days=3)


def recently_notified(flag: AtRiskFlag, now: Optional[datetime.datetime] = None) -> bool:
    """A parent is told at most once every RENOTIFY_AFTER per flag (it used to be once per flag, ever)."""
    now = now or datetime.datetime.utcnow()
    return bool(flag.parent_notified and flag.parent_notified_at and now - flag.parent_notified_at < RENOTIFY_AFTER)


def _deliver_parent_call(db: Session, flag: AtRiskFlag, trainer_user_id: Optional[str],
                         now: Optional[datetime.datetime] = None) -> int:
    """L31: alert each linked parent (in-app and SMS) and open the call in the trainer thread (18)."""
    if recently_notified(flag):
        return 0
    student = db.execute(select(Student).where(Student.id == flag.student_id)).scalar_one()
    student_name = db.execute(select(User.name).where(User.id == student.user_id)).scalar_one_or_none() or "your child"
    trainer = db.execute(select(User).where(User.id == trainer_user_id)).scalar_one_or_none() if trainer_user_id else None
    step_en, step_ta = ACTION_LABEL[flag.suggested_action]["en"], ACTION_LABEL[flag.suggested_action]["ta"]
    links = db.execute(select(ParentStudent).filter_by(student_id=flag.student_id, college_id=flag.college_id)).scalars().all()
    sent = 0
    for link in links:
        notify_user(
            db, link.parent_user_id,
            f"Support plan for {student_name}",
            f"The trainer has flagged: {flag.reason_text}. Suggested next step: {step_en}.",
            title_ta=f"{student_name}-க்கான ஆதரவுத் திட்டம்",
            body_ta=f"பயிற்சியாளர் குறிப்பு: {flag.reason_text}. அடுத்த படி: {step_ta}.",
            kind="alert", link="/parent/messages", channels=("in_app", "sms"), college_id=flag.college_id,
        )
        parent = db.execute(select(User).where(User.id == link.parent_user_id)).scalar_one_or_none()
        if trainer is not None and parent is not None:
            t = _parent_thread(db, trainer.id, parent, student.id, student_name)
            stamp = (now or datetime.datetime.now()).strftime("%I:%M %p").lstrip("0")
            text_en = (f"Hello, this is {trainer.name}. I would like a short call about {student_name}: {flag.reason_text}. "
                       f"Suggested next step: {step_en}. Please reply with a good time to talk.")
            text_ta = (f"வணக்கம், நான் {trainer.name}. {student_name} பற்றி ஒரு சிறிய அழைப்பு தேவை: {flag.reason_text}. "
                       f"அடுத்த படி: {step_ta}. பேச வசதியான நேரத்தைத் தெரிவிக்கவும்.")
            db.add(DirectMessage(id=f"dm_{uuid.uuid4().hex[:16]}", college_id=flag.college_id, thread_id=t.id, is_incoming=False,
                                 sender_user_id=trainer.id, sender_name=trainer.name, text_en=text_en, text_ta=text_ta,
                                 original_lang="en", timestamp_str=stamp))
            t.last_message_preview, t.last_message_time = text_en[:255], stamp
        sent += 1
    if sent:
        flag.parent_notified = True
        flag.parent_notified_at = datetime.datetime.utcnow()
    return sent


def request_parent_call(db: Session, flag: AtRiskFlag, trainer_user_id: Optional[str],
                        now: Optional[datetime.datetime] = None) -> str:
    """L31. Returns sent, held (quiet hours: queued in the outbox until they end), already (told in the last
    RENOTIFY_AFTER) or no_parent."""
    if recently_notified(flag):
        return "already"
    if not db.execute(select(ParentStudent.id).filter_by(student_id=flag.student_id, college_id=flag.college_id)).first():
        return "no_parent"
    wait = quiet_seconds_left(get_rules(db, flag.college_id), now)
    if wait:
        pending = db.execute(select(OutboxEvent.id).where(OutboxEvent.event_type == "at_risk.parent_call",
                                                          OutboxEvent.entity_id == flag.id, OutboxEvent.status == "pending")).first()
        if not pending:
            emit(db, "at_risk.parent_call", {"flag_id": flag.id, "trainer_user_id": trainer_user_id,
                                             "requested_at": datetime.datetime.utcnow().isoformat()}, college_id=flag.college_id,
                 entity_type="at_risk_flag", entity_id=flag.id, delay_seconds=wait)
            db.flush()                                           # a second call in this transaction sees it
        return "held"
    return "sent" if _deliver_parent_call(db, flag, trainer_user_id, now) else "no_parent"


@handler("at_risk.parent_call")
def _held_parent_call(db: Session, ev: OutboxEvent) -> None:
    """Deliver a call held over quiet hours. Idempotent: parent_notified guards a re-run."""
    flag = db.get(AtRiskFlag, (ev.payload or {}).get("flag_id"))
    if flag is None or flag.status == "resolved":
        return
    # idempotent: a notice that went out after this request was made covers it (recently_notified guards too)
    requested = (ev.payload or {}).get("requested_at")
    if requested and flag.parent_notified_at and flag.parent_notified_at >= datetime.datetime.fromisoformat(requested):
        return
    _deliver_parent_call(db, flag, (ev.payload or {}).get("trainer_user_id"))


def notify_batch_trainers(db: Session, flags: List[AtRiskFlag]) -> int:
    """`at_risk.flagged`: each new flag reaches the batch's trainers in-app (13 and 14)."""
    sent = 0
    for flag in flags:
        trainer_users = db.execute(select(Trainer.user_id).join(BatchTrainer, BatchTrainer.trainer_id == Trainer.id)
                                   .where(BatchTrainer.batch_id == flag.batch_id, Trainer.college_id == flag.college_id)).scalars().all()
        name = db.execute(select(User.name).join(Student, Student.user_id == User.id)
                          .where(Student.id == flag.student_id)).scalar_one_or_none() or "A student"
        for uid in trainer_users:
            notify_user(db, uid, f"At risk: {name}", flag.reason_text, title_ta=f"கவனம் தேவை: {name}",
                        body_ta=reason_text(flag.reason_key, flag.reason_text, "ta"),
                        kind="alert", link="/trainer/at-risk", college_id=flag.college_id)
            sent += 1
    return sent


def reason_text(reason_key: str, stored_en: str, lang: str) -> str:
    """The flag's reason in the viewer's language (stored text is English, e.g. 'Attendance 68%')."""
    if lang != "ta" or reason_key not in REASON_TEXT:
        return stored_en
    digits = "".join(ch for ch in stored_en if ch.isdigit())
    return REASON_TEXT[reason_key]["ta"].format(v=digits) if "{v}" in REASON_TEXT[reason_key]["ta"] else REASON_TEXT[reason_key]["ta"]

