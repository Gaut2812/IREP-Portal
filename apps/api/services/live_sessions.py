"""Screen 08: live sessions, recordings and reminders.

Session times are campus-local naive datetimes. Status is always derived
from the clock and from attendance rows, never trusted from the stored
`status` column, so the page is correct whatever day the demo runs.
"""
import datetime
import hashlib
import hmac
import random
import uuid
from typing import List, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import (
    SessionItem, SessionAttendance, Recording, RecordingView, SessionReminder, Student, Batch, LiveMeeting,
)

JOIN_WINDOW_MIN = 10
DAY_TA = {"Mon": "திங்", "Tue": "செவ்", "Wed": "புத", "Thu": "வியா", "Fri": "வெள்", "Sat": "சனி", "Sun": "ஞாயி"}

# Weekly plan for the AI & DS Sem 5 batch (PDF 14): (session id, weekday, start h:m, minutes, title, type, lab)
WEEK_PLAN = [
    ("sess_mon_unionfind", 0, (9, 0), 60, "DSA: Union-Find drill", "Live", None),
    ("sess_tue_model_eval", 1, (9, 0), 60, "Track: Model evaluation lab", "Live", None),
    ("sess_wed_aptitude", 2, (9, 0), 60, "Aptitude: Data interpretation", "Live", None),
    ("sess_thu_rag", 3, (11, 0), 60, "Future Skills: LLM APIs & RAG", "Live", "AI Notebook pre-loaded"),
    ("sess_fri_quiz", 4, (9, 0), 60, "GD + weekly quiz", "Live", None),
    ("sess_sat_track_project", 5, (10, 0), 180, "Track project kick-off + RAG mini-lab", "In-lab / Hybrid", None),
]
TRAINER_TODAY = [("sess_today_cse_a", (9, 0)), ("sess_today_it_a", (14, 0)), ("sess_today_cyber", (15, 30))]


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def session_status(s: SessionItem, attendance: Optional[SessionAttendance], now: datetime.datetime,
                   meeting_ended: bool = False) -> str:
    """Attended / Missed / Excused / Completed / Live / Upcoming / Scheduled / Cancelled, worked out from the clock,
    the live meeting and attendance (the stored status only says whether the class was cancelled)."""
    if s.status == "Cancelled":                      # approved on screen 06
        return "Cancelled"
    if s.scheduled_end <= now or meeting_ended:      # the trainer may end the class early: then it is over
        if attendance is None:
            return "Completed"
        if attendance.status in ("Present", "Late"):
            return "Attended"
        return "Excused" if attendance.status == "Excused" else "Missed"
    if s.scheduled_start <= now:
        return "Live"
    if s.scheduled_start - now <= datetime.timedelta(hours=24):
        return "Upcoming"
    return "Scheduled"


def join_enabled(s: SessionItem, now: datetime.datetime) -> bool:
    if s.status == "Cancelled":
        return False
    return s.scheduled_start - datetime.timedelta(minutes=JOIN_WINDOW_MIN) <= now < s.scheduled_end


def sign_url(storage_key: str, expires_at: datetime.datetime) -> str:
    """Presigned-URL stand-in: HMAC over key + expiry (S3/R2 presign in production)."""
    exp = int(expires_at.timestamp())
    sig = hmac.new(settings.JWT_SECRET_KEY.encode(), f"{storage_key}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"/media/{storage_key}?exp={exp}&sig={sig}"


def verify_signed(storage_key: str, exp: int, sig: str, now: Optional[datetime.datetime] = None) -> bool:
    now = now or _now()
    if exp < int(now.timestamp()):
        return False
    expected = hmac.new(settings.JWT_SECRET_KEY.encode(), f"{storage_key}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(expected, sig)


def rebase_week_sessions(db: Session, college_id: str = "col_demo_001", now: Optional[datetime.datetime] = None) -> int:
    """Re-anchor the demo AI&DS week (Mon–Sat of the current week) and Arun's
    'today' sessions to the current date, then make attendance consistent:
    past sessions get attendance rows, future sessions have none."""
    now = now or _now()
    monday = (now - datetime.timedelta(days=now.weekday())).date()
    # Once the week's last demo class has ended (Saturday afternoon) or on
    # Sunday, show the coming week, so the demo always has classes ahead.
    sid, wd, (hh, mm), minutes, *_ = WEEK_PLAN[-1]
    last_end = datetime.datetime.combine(monday + datetime.timedelta(days=wd), datetime.time(hh, mm)) + datetime.timedelta(minutes=minutes)
    if now.weekday() == 6 or now >= last_end:
        monday = monday + datetime.timedelta(days=7)
    changed = 0
    for sid, wd, (hh, mm), minutes, title, stype, lab in WEEK_PLAN:
        s = db.execute(select(SessionItem).filter_by(id=sid, college_id=college_id)).scalar_one_or_none()
        if not s:
            continue
        day = monday + datetime.timedelta(days=wd)
        start = datetime.datetime(day.year, day.month, day.day, hh, mm)
        if s.scheduled_start != start:
            s.scheduled_start, s.scheduled_end, s.duration_min = start, start + datetime.timedelta(minutes=minutes), minutes
            changed += 1
        s.title, s.session_type = title, stype
        s.has_lab_preload, s.lab_name = bool(lab), lab
    for sid, (hh, mm) in TRAINER_TODAY:
        s = db.execute(select(SessionItem).filter_by(id=sid, college_id=college_id)).scalar_one_or_none()
        if s:
            start = datetime.datetime(now.year, now.month, now.day, hh, mm)
            if s.scheduled_start != start:
                s.scheduled_start, s.scheduled_end = start, start + datetime.timedelta(minutes=s.duration_min)
                changed += 1
    db.flush()

    # demo hygiene: a demo class that was started/ended before its scheduled end
    # (e.g. by an end-to-end test) is reset so the room can be opened again
    from models.schema import LiveMeeting, JoinEvent
    for sid, *_ in WEEK_PLAN:
        s_item = db.execute(select(SessionItem).filter_by(id=sid, college_id=college_id)).scalar_one_or_none()
        meeting = db.execute(select(LiveMeeting).filter_by(session_id=sid)).scalar_one_or_none()
        if s_item and meeting and meeting.started_at and s_item.scheduled_end > now:
            from models.schema import LivePoll, LivePollVote, QaQuestion, QaUpvote
            # rows carry UTC created_at; meeting times are campus-local
            since = meeting.started_at - (datetime.datetime.now() - datetime.datetime.utcnow()) - datetime.timedelta(seconds=5)
            poll_ids = db.execute(select(LivePoll.id).where(LivePoll.session_id == sid)).scalars().all()
            q_ids = db.execute(select(QaQuestion.id).where(QaQuestion.session_id == sid)).scalars().all()
            db.execute(delete(LivePollVote).where(LivePollVote.poll_id.in_(poll_ids or ["_"]), LivePollVote.created_at >= since))
            db.execute(delete(QaUpvote).where(QaUpvote.question_id.in_(q_ids or ["_"]), QaUpvote.created_at >= since))
            new_q = db.execute(select(QaQuestion.id).where(QaQuestion.session_id == sid, QaQuestion.created_at >= since)).scalars().all()
            db.execute(delete(QaUpvote).where(QaUpvote.question_id.in_(new_q or ["_"])))
            db.execute(delete(QaQuestion).where(QaQuestion.id.in_(new_q or ["_"])))
            new_polls = db.execute(select(LivePoll.id).where(LivePoll.session_id == sid, LivePoll.created_at >= since)).scalars().all()
            db.execute(delete(LivePollVote).where(LivePollVote.poll_id.in_(new_polls or ["_"])))
            db.execute(delete(LivePoll).where(LivePoll.id.in_(new_polls or ["_"])))
            for p_ in db.execute(select(LivePoll).where(LivePoll.session_id == sid)).scalars().all():
                p_.is_open = True
            meeting.started_at = meeting.ended_at = None
            meeting.finalized = False
            db.execute(delete(JoinEvent).where(JoinEvent.session_id == sid))
            changed += 1

    # attendance consistency
    ids = [p[0] for p in WEEK_PLAN] + [t[0] for t in TRAINER_TODAY]
    sessions = db.execute(select(SessionItem).where(SessionItem.id.in_(ids), SessionItem.college_id == college_id)).scalars().all()
    rng = random.Random(808)
    for s in sessions:
        if s.scheduled_end > now:
            db.execute(delete(SessionAttendance).where(SessionAttendance.session_id == s.id))
            continue
        rows = {a.student_id: a for a in db.execute(select(SessionAttendance).filter_by(session_id=s.id)).scalars().all()}
        students = db.execute(select(Student).filter_by(batch_id=s.batch_id, college_id=college_id)).scalars().all()
        for st in students:
            if st.id == "std_priya_01":
                present = s.id != "sess_wed_aptitude"     # PDF 14: Wednesday missed, the rest attended
                existing = rows.get(st.id)
                if existing:
                    existing.status = "Present" if present else "Absent"
                    existing.minutes_present = s.duration_min if present else 12
                    continue
            elif st.id in rows:
                continue
            else:
                present = rng.random() * 100 < st.attendance_pct
            db.add(SessionAttendance(
                id=("att_" + s.id + "_" + st.id)[:64], college_id=college_id, session_id=s.id, student_id=st.id,
                minutes_present=s.duration_min if present else rng.randint(0, int(s.duration_min * 0.5)),
                status="Present" if present else "Absent", marked_at=s.scheduled_end,
            ))
    db.flush()
    return changed


def _fmt_range(s: SessionItem) -> str:
    a = s.scheduled_start.strftime("%I:%M").lstrip("0")
    b = s.scheduled_end.strftime("%I:%M %p").lstrip("0")
    return f"{a}–{b}"


def build_student_live(db: Session, student: Student, lang: str = "en", now: Optional[datetime.datetime] = None) -> dict:
    now = now or _now()
    college_id = student.college_id
    sessions: List[SessionItem] = db.execute(
        select(SessionItem).where(SessionItem.college_id == college_id, SessionItem.batch_id == student.batch_id)
        .order_by(SessionItem.scheduled_start)
    ).scalars().all()
    att = {a.session_id: a for a in db.execute(
        select(SessionAttendance).where(SessionAttendance.student_id == student.id)
    ).scalars().all()}
    reminders = set(db.execute(
        select(SessionReminder.session_id).where(SessionReminder.user_id == student.user_id, SessionReminder.college_id == college_id)
    ).scalars().all())
    recs = db.execute(select(Recording).where(Recording.college_id == college_id, Recording.status == "ready")).scalars().all()
    rec_by_session = {r.session_id: r for r in recs if r.session_id}
    views = {v.recording_id: v for v in db.execute(select(RecordingView).filter_by(student_id=student.id)).scalars().all()}
    # the trainer has started the class (screen 07): students may join even before the clock window opens
    started = set(db.execute(select(LiveMeeting.session_id).where(
        LiveMeeting.college_id == college_id, LiveMeeting.started_at.is_not(None), LiveMeeting.ended_at.is_(None),
        LiveMeeting.session_id.in_([x.id for x in sessions] or ["_"]))).scalars().all())

    ended = set(db.execute(select(LiveMeeting.session_id).where(
        LiveMeeting.college_id == college_id, LiveMeeting.ended_at.is_not(None),
        LiveMeeting.session_id.in_([x.id for x in sessions] or ["_"]))).scalars().all())

    def can_join(s: SessionItem) -> bool:
        return s.status != "Cancelled" and s.id not in ended and (s.id in started or join_enabled(s, now))

    # current week (Mon-Sat containing the first upcoming session, else the latest)
    monday = (now - datetime.timedelta(days=now.weekday())).date()
    week = [s for s in sessions if monday <= s.scheduled_start.date() <= monday + datetime.timedelta(days=6)]
    ahead = [s for s in sessions if s.scheduled_end > now and s.status != "Cancelled"]
    if ahead and not any(s.scheduled_end > now and s.status != "Cancelled" for s in week):
        nxt = min(ahead, key=lambda s: s.scheduled_start).scheduled_start.date()
        monday = nxt - datetime.timedelta(days=nxt.weekday())          # this week is over: show the next class's week
        week = [s for s in sessions if monday <= s.scheduled_start.date() <= monday + datetime.timedelta(days=6)]
    if not week and sessions:
        last = sessions[-1].scheduled_start.date()
        monday = last - datetime.timedelta(days=last.weekday())
        week = [s for s in sessions if monday <= s.scheduled_start.date() <= monday + datetime.timedelta(days=6)]

    def row(s: SessionItem) -> dict:
        status = session_status(s, att.get(s.id), now, meeting_ended=s.id in ended)
        rec = rec_by_session.get(s.id)
        if s.id in started and status in ("Upcoming", "Scheduled", "Live"):
            status = "Live"
        if status == "Live" or (status == "Upcoming" and can_join(s)):
            action = "join"
        elif status == "Missed" and rec:
            action = "watch_now"
        elif status in ("Attended", "Completed", "Excused") and rec:
            action = "recording"
        elif status in ("Upcoming", "Scheduled"):
            action = "remind_me"
        else:
            action = "none"
        day = s.scheduled_start.strftime("%a")
        return {
            "id": s.id, "day": DAY_TA.get(day, day) if lang == "ta" else day, "time": _fmt_range(s),
            "date": s.scheduled_start.date().isoformat(), "title": s.title, "type": s.session_type,
            "status": status, "action": action, "join_enabled": can_join(s),
            "recording_id": rec.id if rec else None, "reminder_set": s.id in reminders,
            "starts_at": s.scheduled_start.isoformat(), "ends_at": s.scheduled_end.isoformat(),
        }

    upcoming = [s for s in sessions if s.scheduled_end > now and s.id not in ended and s.status != "Cancelled"]
    hero = upcoming[0] if upcoming else None
    hero_payload = None
    if hero:
        mins = int((hero.scheduled_start - now).total_seconds() // 60)
        hero_payload = {
            "id": hero.id, "title": hero.title, "trainer": hero.trainer_name,
            "date_label": hero.scheduled_start.strftime("%a, %b %d").replace(" 0", " "),
            "time_label": f"{hero.scheduled_start.strftime('%I:%M %p').lstrip('0')} to {hero.scheduled_end.strftime('%I:%M %p').lstrip('0')}",
            "lab": hero.lab_name, "starts_in_min": max(0, mins), "is_live": hero.scheduled_start <= now or hero.id in started,
            "join_enabled": can_join(hero), "room": f"/live/{hero.id}", "reminder_set": hero.id in reminders,
            "starts_at": hero.scheduled_start.isoformat(),
        }

    # attendance summary across the semester (all sessions with attendance rows)
    past_rows = [(s, att[s.id]) for s in sessions if s.id in att]
    present = [s for s, a in past_rows if a.status == "Present"]
    weekday = [(s, a) for s, a in past_rows if s.scheduled_start.weekday() < 5]
    saturday = [(s, a) for s, a in past_rows if s.scheduled_start.weekday() == 5]
    pct = lambda rows: int(round(100 * sum(1 for _, a in rows if a.status == "Present") / len(rows))) if rows else None
    missed_with_rec = [s for s, a in past_rows if a.status != "Present" and s.id in rec_by_session]
    watched_missed = [s for s in missed_with_rec if rec_by_session[s.id].id in views]

    week_ids = {w.id for w in week}
    library = sorted(
        [r for r in recs if r.batch_id in (None, student.batch_id) and (r.session_id is None or r.session_id in week_ids)],
        key=lambda r: (r.session_id is None, r.recorded_on or datetime.date.min), reverse=True,
    )

    def dur(m: int) -> str:
        return f"{m // 60} hr {m % 60} min" if m >= 60 and m % 60 else (f"{m // 60} hr" if m >= 60 else f"{m} min")

    return {
        "hero_session": hero_payload,
        "week_label": f"Week {week[0].week_no}" if week and week[0].week_no else "",
        "week_sessions": [row(s) for s in week],
        "attendance_summary": {
            "overall_pct": pct(past_rows) if past_rows else student.attendance_pct,
            "profile_pct": student.attendance_pct,
            "sessions_attended": len(present), "sessions_total": len(past_rows),
            "weekday_pct": pct(weekday), "saturday_pct": pct(saturday),
            "recordings_watched_for_missed": len(watched_missed), "missed_with_recording": len(missed_with_rec),
            "threshold_pct": 75,
        },
        "recording_library": [
            {"id": r.id, "title": r.title, "duration": dur(r.duration_min), "duration_min": r.duration_min,
             "recorded_on": r.recorded_on.isoformat() if r.recorded_on else None, "chapters": len(r.chapters or []),
             "has_transcript": r.has_transcript, "has_summary": r.has_summary, "watched": r.id in views}
            for r in library[:8]
        ],
        "join_window_min": JOIN_WINDOW_MIN,
        "server_time": now.isoformat(),
    }
