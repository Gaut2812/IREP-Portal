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
    SessionItem, SessionAttendance, Recording, RecordingView, SessionReminder, Student, Batch,
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


def session_status(s: SessionItem, attendance: Optional[SessionAttendance], now: datetime.datetime) -> str:
    """Attended / Missed / Live / Upcoming / Scheduled."""
    if s.scheduled_end <= now:
        if attendance is None:
            return "Completed"
        return "Attended" if attendance.status == "Present" else "Missed"
    if s.scheduled_start <= now:
        return "Live"
    if s.scheduled_start - now <= datetime.timedelta(hours=24):
        return "Upcoming"
    return "Scheduled"


def join_enabled(s: SessionItem, now: datetime.datetime) -> bool:
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
    if now.weekday() == 6:   # Sunday: show the coming week
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

    # current week (Mon-Sat containing the first upcoming session, else the latest)
    monday = (now - datetime.timedelta(days=now.weekday())).date()
    week = [s for s in sessions if monday <= s.scheduled_start.date() <= monday + datetime.timedelta(days=6)]
    if not week and sessions:
        last = sessions[-1].scheduled_start.date()
        monday = last - datetime.timedelta(days=last.weekday())
        week = [s for s in sessions if monday <= s.scheduled_start.date() <= monday + datetime.timedelta(days=6)]

    def row(s: SessionItem) -> dict:
        status = session_status(s, att.get(s.id), now)
        rec = rec_by_session.get(s.id)
        if status == "Live" or (status == "Upcoming" and join_enabled(s, now)):
            action = "join"
        elif status == "Missed" and rec:
            action = "watch_now"
        elif status in ("Attended", "Completed") and rec:
            action = "recording"
        elif status in ("Upcoming", "Scheduled"):
            action = "remind_me"
        else:
            action = "none"
        day = s.scheduled_start.strftime("%a")
        return {
            "id": s.id, "day": DAY_TA.get(day, day) if lang == "ta" else day, "time": _fmt_range(s),
            "date": s.scheduled_start.date().isoformat(), "title": s.title, "type": s.session_type,
            "status": status, "action": action, "join_enabled": join_enabled(s, now),
            "recording_id": rec.id if rec else None, "reminder_set": s.id in reminders,
            "starts_at": s.scheduled_start.isoformat(), "ends_at": s.scheduled_end.isoformat(),
        }

    upcoming = [s for s in sessions if s.scheduled_end > now]
    hero = upcoming[0] if upcoming else None
    hero_payload = None
    if hero:
        mins = int((hero.scheduled_start - now).total_seconds() // 60)
        hero_payload = {
            "id": hero.id, "title": hero.title, "trainer": hero.trainer_name,
            "date_label": hero.scheduled_start.strftime("%a, %b %d").replace(" 0", " "),
            "time_label": f"{hero.scheduled_start.strftime('%I:%M %p').lstrip('0')} to {hero.scheduled_end.strftime('%I:%M %p').lstrip('0')}",
            "lab": hero.lab_name, "starts_in_min": max(0, mins), "is_live": hero.scheduled_start <= now,
            "join_enabled": join_enabled(hero, now), "room": f"/live/{hero.id}", "reminder_set": hero.id in reminders,
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
