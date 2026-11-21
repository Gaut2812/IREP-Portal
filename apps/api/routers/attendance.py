"""Screen 09 · Attendance (trainer) and the student check-in. Spec: docs/screens/09-trainer-attendance.md

Link L06: the 75% rule (services/live_class.finalize_session) writes `auto`
rows when a class ends; this screen reviews them, overrides with a reason,
and runs code check-in for in-lab / hybrid classes.
"""
import base64
import datetime
import hashlib
import hmac
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_student_for_user, get_trainer_batch_ids, get_trainer_for_user
from models.schema import Batch, SessionAttendance, SessionItem, Student, User
from services.audit import record_audit

router = APIRouter(tags=["Screen 09 · Attendance"])
TRAINER = require_role(["trainer"])
STUDENT = require_role(["student"])
CHECKIN_EARLY_MIN = 15
CODE_ALPHABET_LEN = 6


class OverrideIn(BaseModel):
    student_id: str
    status: str = Field(pattern="^(Present|Absent)$")
    reason: str = Field(min_length=5, max_length=500)


class CheckinIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)


# ---- helpers ----
def _trainer_session(db: Session, user: TokenPayload, session_id: str):
    trainer = get_trainer_for_user(user, db)
    batch_ids = set(get_trainer_batch_ids(trainer, db))
    s = db.execute(select(SessionItem).where(SessionItem.id == session_id, SessionItem.college_id == user.college_id)).scalar_one_or_none()
    if s is None or not (s.batch_id in batch_ids or s.substitute_trainer_id == trainer.id):
        raise HTTPException(status_code=404, detail="Session not found in your batches")
    return trainer, s


def _code(session_id: str, window: int) -> str:
    """Rotating check-in code: HMAC(secret, session:minute), base32, 6 characters."""
    mac = hmac.new(settings.JWT_SECRET_KEY.encode(), f"checkin:{session_id}:{window}".encode(), hashlib.sha256).digest()
    return base64.b32encode(mac).decode()[:CODE_ALPHABET_LEN].replace("0", "8").replace("1", "9")


def _window(now_ts: Optional[float] = None) -> int:
    return int((now_ts if now_ts is not None else time.time()) // 60)


def _checkin_open(s: SessionItem, now: datetime.datetime) -> bool:
    return s.status != "Cancelled" and s.scheduled_start - datetime.timedelta(minutes=CHECKIN_EARLY_MIN) <= now < s.scheduled_end


def _counts(db: Session, s: SessionItem) -> dict:
    total = db.execute(select(func.count(Student.id)).where(Student.batch_id == s.batch_id)).scalar_one() if s.batch_id else 0
    rows = dict(db.execute(select(SessionAttendance.status, func.count(SessionAttendance.id))
                           .where(SessionAttendance.session_id == s.id).group_by(SessionAttendance.status)).all())
    present = rows.get("Present", 0)
    absent = rows.get("Absent", 0) + rows.get("Partial", 0)
    return {"students": total, "present": present, "absent": absent, "unmarked": max(0, total - present - absent)}


# ---- trainer ----
@router.get("/trainer/attendance/sessions")
def recent_sessions(days: int = Query(14, ge=1, le=90), current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = get_trainer_batch_ids(trainer, db)
    now = datetime.datetime.now()
    rows = db.execute(select(SessionItem).where(
        SessionItem.college_id == current_user.college_id, SessionItem.status != "Cancelled",
        SessionItem.scheduled_start >= now - datetime.timedelta(days=days), SessionItem.scheduled_start <= now + datetime.timedelta(days=1),
        or_(SessionItem.batch_id.in_(batch_ids or ["_"]), SessionItem.substitute_trainer_id == trainer.id))
        .order_by(SessionItem.scheduled_start.desc())).scalars().all()
    batches = dict(db.execute(select(Batch.id, Batch.short_name).where(Batch.college_id == current_user.college_id)).all())
    return {"sessions": [{"id": s.id, "title": s.title, "batch": batches.get(s.batch_id), "start": s.scheduled_start.isoformat(),
                          "end": s.scheduled_end.isoformat(), "session_type": s.session_type, "checkin_open": _checkin_open(s, now),
                          "past": s.scheduled_end <= now, **_counts(db, s)} for s in rows]}


@router.get("/trainer/attendance/{session_id}")
def session_roster(session_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    _, s = _trainer_session(db, current_user, session_id)
    students = db.execute(select(Student, User.name).join(User, User.id == Student.user_id)
                          .where(Student.batch_id == s.batch_id).order_by(User.name)).all()
    att = {a.student_id: a for a in db.execute(select(SessionAttendance).where(SessionAttendance.session_id == s.id)).scalars()}
    return {"session": {"id": s.id, "title": s.title, "start": s.scheduled_start.isoformat(), "end": s.scheduled_end.isoformat(),
                        "duration_min": s.duration_min, "checkin_open": _checkin_open(s, datetime.datetime.now()), **_counts(db, s)},
            "roster": [{"student_id": st.id, "name": name, "register_no": st.register_no,
                        "status": att[st.id].status if st.id in att else None,
                        "minutes_present": att[st.id].minutes_present if st.id in att else 0,
                        "source": att[st.id].source if st.id in att else None,
                        "override_reason": att[st.id].override_reason if st.id in att else None} for st, name in students]}


@router.post("/trainer/attendance/{session_id}/override")
def override(session_id: str, req: OverrideIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer, s = _trainer_session(db, current_user, session_id)
    st = db.execute(select(Student).where(Student.id == req.student_id, Student.batch_id == s.batch_id)).scalar_one_or_none()
    if st is None:
        raise HTTPException(status_code=404, detail="Student not found in this session's batch")
    row = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == s.id, SessionAttendance.student_id == st.id)).scalar_one_or_none()
    before = row.status if row else None
    if row is None:
        row = SessionAttendance(id=("att_" + s.id + "_" + st.id)[:64], college_id=s.college_id, session_id=s.id, student_id=st.id,
                                minutes_present=0)
        db.add(row)
    row.status, row.source, row.overridden_by, row.override_reason = req.status, "manual", trainer.id, req.reason.strip()
    row.marked_at = datetime.datetime.now()
    record_audit(db, current_user, "attendance.overridden", "session", s.id,
                 {"student_id": st.id, "from": before, "to": req.status, "reason": req.reason.strip()})
    db.commit()
    return {"student_id": st.id, "status": row.status, "source": row.source}


@router.get("/trainer/attendance/{session_id}/checkin-code")
def checkin_code(session_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    _, s = _trainer_session(db, current_user, session_id)
    if not _checkin_open(s, datetime.datetime.now()):
        raise HTTPException(status_code=409, detail="Check-in is open from 15 minutes before the class until it ends")
    now = time.time()
    return {"code": _code(s.id, _window(now)), "expires_in": 60 - int(now % 60)}


# ---- student ----
@router.post("/student/attendance/checkin")
def student_checkin(req: CheckinIn, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    st = get_student_for_user(current_user, db)
    now_dt, now_ts = datetime.datetime.now(), time.time()
    code = req.code.strip().upper()
    windows = (_window(now_ts), _window(now_ts) - 1)
    candidates = db.execute(select(SessionItem).where(SessionItem.batch_id == st.batch_id, SessionItem.college_id == st.college_id,
                                                      SessionItem.status != "Cancelled",
                                                      SessionItem.scheduled_start <= now_dt + datetime.timedelta(minutes=CHECKIN_EARLY_MIN),
                                                      SessionItem.scheduled_end > now_dt)).scalars().all()
    s = next((c for c in candidates if any(hmac.compare_digest(code, _code(c.id, w)) for w in windows)), None)
    if s is None:
        raise HTTPException(status_code=422, detail="That code is not valid for your class right now. Ask your trainer for the current code.")
    row = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == s.id, SessionAttendance.student_id == st.id)).scalar_one_or_none()
    if row and row.source == "manual":
        return {"session_id": s.id, "title": s.title, "status": row.status, "checked_in": False,
                "message": "Your trainer has already marked your attendance for this class."}
    if row is None:
        row = SessionAttendance(id=("att_" + s.id + "_" + st.id)[:64], college_id=s.college_id, session_id=s.id, student_id=st.id,
                                minutes_present=0)
        db.add(row)
    already = row.source == "qr" and row.status == "Present"
    row.status, row.source, row.marked_at = "Present", "qr", now_dt
    if not already:
        record_audit(db, current_user, "attendance.checked_in", "session", s.id, {"student_id": st.id})
    db.commit()
    return {"session_id": s.id, "title": s.title, "status": "Present", "checked_in": True, "already": already}
