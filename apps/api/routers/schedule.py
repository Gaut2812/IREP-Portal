"""Screens 05 · Schedule (trainer) and 06 · Timetable (college): link L11.
Spec: docs/screens/05-06-schedule-and-timetable.md
"""
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import case, distinct, or_, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_trainer_batch_ids, get_trainer_for_user
from models.schema import Batch, LiveMeeting, ScheduleChangeRequest, SessionItem, Student, Trainer, User
from services.audit import record_audit
from services.notifications import notify_users, notify_user
from services.outbox import emit
from services.scheduling import CANCELLED, find_clashes

router = APIRouter(tags=["Screens 05/06 · Schedule and timetable"])
TRAINER = require_role(["trainer"])
COLLEGE = require_role(["college_admin"])
MIN_MINUTES, MAX_MINUTES = 15, 240


class ProposalIn(BaseModel):
    kind: str = Field(pattern="^(new|reschedule|cancel|substitute)$")
    batch_id: Optional[str] = None                    # for kind=new
    session_id: Optional[str] = None                  # for the other kinds
    title: Optional[str] = Field(default=None, max_length=255)
    start: Optional[datetime.datetime] = None
    end: Optional[datetime.datetime] = None
    room: Optional[str] = Field(default=None, max_length=64)
    substitute_trainer_id: Optional[str] = None
    reason: str = Field(min_length=5, max_length=2000)


class DecisionIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


def _week(week: Optional[datetime.date]):
    day = week or datetime.date.today()
    monday = day - datetime.timedelta(days=day.weekday())
    start = datetime.datetime.combine(monday, datetime.time.min)
    return monday, start, start + datetime.timedelta(days=7)


def _session_out(s: SessionItem, batches: dict, names: dict) -> dict:
    return {"id": s.id, "title": s.title, "batch_id": s.batch_id, "batch": batches.get(s.batch_id), "start": s.scheduled_start.isoformat(),
            "end": s.scheduled_end.isoformat(), "room": s.room, "status": s.status, "session_type": s.session_type,
            "substitute": names.get(s.substitute_trainer_id) if s.substitute_trainer_id else None}


def _trainer_names(db: Session, college_id: str) -> dict:
    return dict(db.execute(select(Trainer.id, User.name).join(User, User.id == Trainer.user_id).where(Trainer.college_id == college_id)).all())


def _request_out(r: ScheduleChangeRequest, batches: dict, names: dict, sessions: dict) -> dict:
    s = sessions.get(r.session_id)
    return {"id": r.id, "kind": r.kind, "batch": batches.get(r.batch_id), "batch_id": r.batch_id, "session_id": r.session_id,
            "session_title": s.title if s else None, "current_start": s.scheduled_start.isoformat() if s else None,
            "title": r.proposed_title, "start": r.proposed_start.isoformat() if r.proposed_start else None,
            "end": r.proposed_end.isoformat() if r.proposed_end else None, "room": r.proposed_room,
            "substitute": names.get(r.substitute_trainer_id) if r.substitute_trainer_id else None,
            "requested_by": names.get(r.requested_by_trainer_id), "reason": r.reason, "status": r.status, "clashes": r.clashes or [],
            "decision_note": r.decision_note, "at": r.created_at.isoformat()}


def _clashes_for(db: Session, r: ScheduleChangeRequest) -> list:
    if r.kind == "cancel":
        return []
    s = db.get(SessionItem, r.session_id) if r.session_id else None
    start = r.proposed_start or (s.scheduled_start if s else None)
    end = r.proposed_end or (s.scheduled_end if s else None)
    trainers = [r.substitute_trainer_id] if r.kind == "substitute" else [r.requested_by_trainer_id]
    room = r.proposed_room if r.proposed_room is not None else (s.room if s else None)
    if r.kind == "substitute":
        # the batch itself does not clash with its own session: only the substitute's other commitments
        return [c for c in find_clashes(db, college_id=r.college_id, batch_id="__none__", start=start, end=end, trainer_ids=trainers,
                                        exclude_session_id=r.session_id) if c["kind"] == "trainer"]
    return find_clashes(db, college_id=r.college_id, batch_id=r.batch_id, start=start, end=end, trainer_ids=trainers,
                        room=room, exclude_session_id=r.session_id)


# ---------------------------------------------------------------------------
# 05 · trainer
# ---------------------------------------------------------------------------

@router.get("/trainer/schedule")
def trainer_week(week: Optional[datetime.date] = None, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = get_trainer_batch_ids(trainer, db)
    monday, start, end = _week(week)
    rows = db.execute(select(SessionItem).where(
        SessionItem.college_id == current_user.college_id, SessionItem.scheduled_start >= start, SessionItem.scheduled_start < end,
        or_(SessionItem.batch_id.in_(batch_ids or ["_"]), SessionItem.substitute_trainer_id == trainer.id))
        .order_by(SessionItem.scheduled_start)).scalars().all()
    batches = dict(db.execute(select(Batch.id, Batch.short_name).where(Batch.college_id == current_user.college_id)).all())
    names = _trainer_names(db, current_user.college_id)
    reqs = db.execute(select(ScheduleChangeRequest).where(ScheduleChangeRequest.requested_by_trainer_id == trainer.id)
                      .order_by(ScheduleChangeRequest.created_at.desc()).limit(20)).scalars().all()
    sessions = {s.id: s for s in db.execute(select(SessionItem).where(SessionItem.id.in_({r.session_id for r in reqs if r.session_id} or {"_"}))).scalars()}
    substitutes = db.execute(select(Trainer.id, User.name).join(User, User.id == Trainer.user_id)
                             .where(Trainer.college_id == current_user.college_id, Trainer.id != trainer.id).order_by(User.name)).all()
    return {"week": monday.isoformat(), "my_batches": [{"id": b, "short_name": batches.get(b)} for b in batch_ids],
            "sessions": [_session_out(s, batches, names) for s in rows],
            "requests": [_request_out(r, batches, names, sessions) for r in reqs],
            "substitutes": [{"id": i, "name": n} for i, n in substitutes]}


@router.post("/trainer/schedule/requests", status_code=status.HTTP_201_CREATED)
def propose(req: ProposalIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    mine = set(get_trainer_batch_ids(trainer, db))
    session = None
    if req.kind == "new":
        if not req.batch_id or req.batch_id not in mine:
            raise HTTPException(status_code=404, detail="Batch not found in your batches")
        if not (req.title and req.title.strip()):
            raise HTTPException(status_code=422, detail="Give the session a title")
        batch_id = req.batch_id
    else:
        session = db.execute(select(SessionItem).where(SessionItem.id == req.session_id, SessionItem.college_id == current_user.college_id)).scalar_one_or_none()
        if session is None or session.batch_id not in mine:
            raise HTTPException(status_code=404, detail="Session not found in your batches")
        if session.status == CANCELLED:
            raise HTTPException(status_code=409, detail="This session is already cancelled")
        batch_id = session.batch_id
    if req.kind in ("new", "reschedule"):
        if not req.start or not req.end:
            raise HTTPException(status_code=422, detail="Give the start and end time")
        minutes = (req.end - req.start).total_seconds() / 60
        if not (MIN_MINUTES <= minutes <= MAX_MINUTES):
            raise HTTPException(status_code=422, detail=f"A session lasts {MIN_MINUTES} to {MAX_MINUTES} minutes")
        if req.start < datetime.datetime.now():
            raise HTTPException(status_code=422, detail="The new time is in the past")
    if req.kind == "substitute":
        sub = db.execute(select(Trainer).where(Trainer.id == req.substitute_trainer_id, Trainer.college_id == current_user.college_id)).scalar_one_or_none()
        if sub is None or sub.id == trainer.id:
            raise HTTPException(status_code=404, detail="Substitute trainer not found in your college")
    if db.execute(select(ScheduleChangeRequest.id).where(ScheduleChangeRequest.session_id == req.session_id, ScheduleChangeRequest.status == "pending")).first() and req.session_id:
        raise HTTPException(status_code=409, detail="This session already has a pending change")
    r = ScheduleChangeRequest(id=f"scr_{uuid.uuid4().hex[:16]}", college_id=current_user.college_id, kind=req.kind, batch_id=batch_id,
                              session_id=session.id if session else None, proposed_title=(req.title or "").strip() or None,
                              proposed_start=req.start, proposed_end=req.end, proposed_room=(req.room or "").strip() or None,
                              substitute_trainer_id=req.substitute_trainer_id if req.kind == "substitute" else None,
                              reason=req.reason.strip(), requested_by_trainer_id=trainer.id)
    db.add(r)
    db.flush()
    r.clashes = _clashes_for(db, r)
    record_audit(db, current_user, "schedule.change_proposed", "schedule_request", r.id, {"kind": r.kind, "clashes": len(r.clashes)})
    for admin_id in db.execute(select(User.id).where(User.college_id == current_user.college_id, User.role == "college_admin",
                                                     User.is_active.is_(True))).scalars():
        notify_user(db, admin_id, "Schedule change to approve", r.reason, title_ta="ஒப்புதலுக்கு அட்டவணை மாற்றம்", kind="approval",
                    link="/college/timetable", college_id=current_user.college_id)
    db.commit()
    return {"id": r.id, "status": r.status, "clashes": r.clashes}


# ---------------------------------------------------------------------------
# 06 · college
# ---------------------------------------------------------------------------

@router.get("/college/timetable")
def college_week(week: Optional[datetime.date] = None, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid = current_user.college_id
    monday, start, end = _week(week)
    rows = db.execute(select(SessionItem).where(SessionItem.college_id == cid, SessionItem.scheduled_start >= start,
                                                SessionItem.scheduled_start < end).order_by(SessionItem.scheduled_start)).scalars().all()
    batches = dict(db.execute(select(Batch.id, Batch.short_name).where(Batch.college_id == cid)).all())
    names = _trainer_names(db, cid)
    pending_first = case((ScheduleChangeRequest.status == "pending", 0), else_=1)
    reqs = db.execute(select(ScheduleChangeRequest).where(ScheduleChangeRequest.college_id == cid)
                      .order_by(pending_first, ScheduleChangeRequest.created_at.desc()).limit(50)).scalars().all()
    for r in reqs:
        if r.status == "pending":
            r.clashes = _clashes_for(db, r)            # live: the timetable may have changed since the proposal
    sessions = {s.id: s for s in db.execute(select(SessionItem).where(SessionItem.id.in_({r.session_id for r in reqs if r.session_id} or {"_"}))).scalars()}
    rooms = sorted(r for r in db.execute(select(distinct(SessionItem.room)).where(SessionItem.college_id == cid, SessionItem.room.isnot(None))).scalars() if r)
    db.commit()
    return {"week": monday.isoformat(), "sessions": [_session_out(s, batches, names) for s in rows],
            "requests": [_request_out(r, batches, names, sessions) for r in reqs], "rooms": rooms}


def _pending(db: Session, user: TokenPayload, request_id: str) -> ScheduleChangeRequest:
    r = db.execute(select(ScheduleChangeRequest).where(ScheduleChangeRequest.id == request_id,
                                                       ScheduleChangeRequest.college_id == user.college_id)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.status != "pending":
        raise HTTPException(status_code=409, detail=f"This request is already {r.status}")
    return r


def _batch_student_users(db: Session, batch_id: str):
    return list(db.execute(select(Student.user_id).where(Student.batch_id == batch_id)).scalars())


@router.post("/college/schedule-requests/{request_id}/approve")
def approve(request_id: str, override: bool = Query(False), current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    r = _pending(db, current_user, request_id)
    clashes = _clashes_for(db, r)
    if clashes and not override:
        db.rollback()
        raise HTTPException(status_code=409, detail={"message": "The change clashes with the timetable", "clashes": clashes})
    batch = db.get(Batch, r.batch_id)
    s = db.get(SessionItem, r.session_id) if r.session_id else None
    teams_meeting = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == r.session_id)).scalar_one_or_none() if s else None
    when = None
    if r.kind == "new":
        trainer_user = db.get(User, db.get(Trainer, r.requested_by_trainer_id).user_id)
        s = SessionItem(id=f"sess_{uuid.uuid4().hex[:16]}", college_id=r.college_id, title=r.proposed_title, track=batch.track,
                        trainer_name=trainer_user.name if trainer_user else "", scheduled_start=r.proposed_start, scheduled_end=r.proposed_end,
                        duration_min=int((r.proposed_end - r.proposed_start).total_seconds() // 60), session_type="Live", status="Scheduled",
                        batch_id=r.batch_id, room=r.proposed_room)
        db.add(s)
        db.flush()
        r.session_id, when = s.id, s.scheduled_start
    elif r.kind == "reschedule":
        s.scheduled_start, s.scheduled_end = r.proposed_start, r.proposed_end
        s.duration_min = int((r.proposed_end - r.proposed_start).total_seconds() // 60)
        if r.proposed_room is not None:
            s.room = r.proposed_room
        when = s.scheduled_start
        if teams_meeting and teams_meeting.graph_event_id:
            emit(db, "teams.update_event", {"session_id": s.id}, college_id=r.college_id, entity_type="session", entity_id=s.id)
    elif r.kind == "cancel":
        s.status = CANCELLED
        if teams_meeting and teams_meeting.graph_event_id:
            emit(db, "teams.cancel_event", {"session_id": s.id, "comment": r.reason}, college_id=r.college_id, entity_type="session", entity_id=s.id)
    else:
        s.substitute_trainer_id = r.substitute_trainer_id
        sub = db.get(Trainer, r.substitute_trainer_id)
        if sub:
            notify_user(db, sub.user_id, f"You are substituting: {s.title}", s.scheduled_start.strftime("%a %d %b %H:%M"),
                        kind="info", link="/trainer/schedule", college_id=r.college_id)
    r.status, r.decided_by, r.decided_at = "approved", current_user.sub, datetime.datetime.utcnow()
    r.clashes = clashes
    record_audit(db, current_user, "schedule.change_approved", "schedule_request", r.id,
                 {"kind": r.kind, "session_id": r.session_id, "override": bool(clashes), "clashes": clashes})
    t = db.get(Trainer, r.requested_by_trainer_id)
    if t:
        notify_user(db, t.user_id, "Schedule change approved", f"{r.kind}: {s.title if s else ''}", title_ta="அட்டவணை மாற்றம் ஏற்கப்பட்டது",
                    kind="approval", link="/trainer/schedule", college_id=r.college_id)
    if r.kind in ("new", "reschedule", "cancel"):           # students see it on 08 and are told (flow step 5)
        title = {"new": "New class", "reschedule": "Class moved", "cancel": "Class cancelled"}[r.kind]
        title_ta = {"new": "புதிய வகுப்பு", "reschedule": "வகுப்பு நேரம் மாற்றப்பட்டது", "cancel": "வகுப்பு ரத்து"}[r.kind]
        body = f"{s.title} · {when.strftime('%a %d %b %H:%M')}" if when else s.title
        notify_users(db, _batch_student_users(db, r.batch_id), f"{title}: {s.title}", body, title_ta=f"{title_ta}: {s.title}",
                     kind="reminder", link="/student/live", college_id=r.college_id)
    db.commit()
    return {"id": r.id, "status": r.status, "session_id": r.session_id, "override": bool(clashes)}


@router.post("/college/schedule-requests/{request_id}/reject")
def reject(request_id: str, req: DecisionIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    if not req.reason or len(req.reason.strip()) < 5:
        raise HTTPException(status_code=422, detail="Give a reason for rejecting (at least 5 characters)")
    r = _pending(db, current_user, request_id)
    r.status, r.decision_note, r.decided_by, r.decided_at = "rejected", req.reason.strip(), current_user.sub, datetime.datetime.utcnow()
    record_audit(db, current_user, "schedule.change_rejected", "schedule_request", r.id, {"kind": r.kind})
    t = db.get(Trainer, r.requested_by_trainer_id)
    if t:
        notify_user(db, t.user_id, "Schedule change rejected", r.decision_note, title_ta="அட்டவணை மாற்றம் நிராகரிக்கப்பட்டது",
                    kind="approval", link="/trainer/schedule", college_id=r.college_id)
    db.commit()
    return {"id": r.id, "status": r.status}
