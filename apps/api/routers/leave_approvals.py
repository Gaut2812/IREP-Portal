"""Screens 10 · Attendance (parent) and 43 · Approvals (trainer): links L07, L08, L09.
Spec: docs/screens/10-43-parent-attendance-and-approvals.md
"""
import calendar
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_child_for_parent, get_trainer_batch_ids, get_trainer_for_user, get_user_name
from models.schema import (BatchTrainer, LabApproval, LeaveRequest, SessionAttendance, SessionItem, Student, Trainer, User, VirtualLabItem)
from services.audit import record_audit
from services.consent import current as consent_state
from services.leave import apply_approved_leave
from services.notifications import notify_user
from services.templates import render

router = APIRouter(tags=["Screens 10/43 · Parent attendance and approvals"])
PARENT = require_role(["parent"])
TRAINER = require_role(["trainer"])
MAX_DAYS, PAST_DAYS, AHEAD_DAYS = 30, 7, 60


class LeaveIn(BaseModel):
    child_id: Optional[str] = None
    start_date: datetime.date
    end_date: datetime.date
    reason: str = Field(min_length=5, max_length=1000)


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|deny)$")
    note: Optional[str] = Field(default=None, max_length=1000)


def _leave_out(r: LeaveRequest) -> dict:
    return {"id": r.id, "student_id": r.student_id, "start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat(),
            "reason": r.reason, "status": r.status, "decision_note": r.decision_note, "requested_at": r.created_at.isoformat()}


# ---------------------------------------------------------------------------
# 10 · parent
# ---------------------------------------------------------------------------

@router.get("/parent/attendance")
def parent_attendance(child_id: Optional[str] = None, month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"), lang: str = "en",
                      current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    child = get_child_for_parent(current_user, db, child_id)
    name = get_user_name(db, child.user_id, "Student")
    if consent_state(db, child.id, "parent_data_processing") != "granted":     # screen 48 gate, as on 15
        return {"consent_required": True, "ward": {"id": child.id, "name": name}}
    today = datetime.date.today()
    y, m = (int(month[:4]), int(month[5:])) if month else (today.year, today.month)
    first = datetime.date(y, m, 1)
    last = datetime.date(y, m, calendar.monthrange(y, m)[1])
    sessions = db.execute(select(SessionItem).where(
        SessionItem.batch_id == child.batch_id, SessionItem.college_id == child.college_id,
        SessionItem.scheduled_start >= datetime.datetime.combine(first, datetime.time.min),
        SessionItem.scheduled_start < datetime.datetime.combine(last + datetime.timedelta(days=1), datetime.time.min))
        .order_by(SessionItem.scheduled_start)).scalars().all()
    att = {a.session_id: a for a in db.execute(select(SessionAttendance).where(
        SessionAttendance.student_id == child.id, SessionAttendance.session_id.in_([s.id for s in sessions] or ["_"]))).scalars()}
    now = datetime.datetime.now()
    rows, counts = [], {"Present": 0, "Absent": 0, "Excused": 0}
    for s in sessions:
        if s.status == "Cancelled":
            st = "Cancelled"
        elif s.id in att:
            st = att[s.id].status if att[s.id].status in counts else "Absent"
        else:
            st = "Upcoming" if s.scheduled_end > now else "Not marked"
        if st in counts:
            counts[st] += 1
        rows.append({"session_id": s.id, "date": s.scheduled_start.date().isoformat(), "time": s.scheduled_start.strftime("%H:%M"),
                     "title": s.title, "status": st})
    marked = counts["Present"] + counts["Absent"]
    leaves = db.execute(select(LeaveRequest).where(LeaveRequest.student_id == child.id).order_by(LeaveRequest.created_at.desc()).limit(20)).scalars().all()
    return {"consent_required": False, "ward": {"id": child.id, "name": name, "batch": child.batch_name},
            "month": first.strftime("%Y-%m"), "sessions": rows,
            "summary": {**{k.lower(): v for k, v in counts.items()}, "pct": round(100 * counts["Present"] / marked) if marked else None,
                        "overall_pct": child.attendance_pct},
            "leave_requests": [_leave_out(r) for r in leaves]}


@router.post("/parent/leave-requests", status_code=status.HTTP_201_CREATED)
def request_leave(req: LeaveIn, current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    child = get_child_for_parent(current_user, db, req.child_id)
    today = datetime.date.today()
    if req.end_date < req.start_date:
        raise HTTPException(status_code=422, detail="The leave must end on or after the day it starts")
    if (req.end_date - req.start_date).days + 1 > MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"One request covers at most {MAX_DAYS} days")
    if req.start_date < today - datetime.timedelta(days=PAST_DAYS) or req.start_date > today + datetime.timedelta(days=AHEAD_DAYS):
        raise HTTPException(status_code=422, detail=f"Leave can start up to {PAST_DAYS} days ago and up to {AHEAD_DAYS} days ahead")
    overlap = db.execute(select(LeaveRequest.id).where(
        LeaveRequest.student_id == child.id, LeaveRequest.status.in_(("pending", "approved")),
        LeaveRequest.start_date <= req.end_date, LeaveRequest.end_date >= req.start_date)).first()
    if overlap:
        raise HTTPException(status_code=409, detail="These dates overlap another leave request")
    r = LeaveRequest(id=f"lv_{uuid.uuid4().hex[:16]}", college_id=child.college_id, student_id=child.id, requested_by=current_user.sub,
                     start_date=req.start_date, end_date=req.end_date, reason=req.reason.strip())
    db.add(r)
    db.flush()
    record_audit(db, current_user, "leave.requested", "leave_request", r.id,
                 {"student_id": child.id, "start": r.start_date.isoformat(), "end": r.end_date.isoformat()})
    name = get_user_name(db, child.user_id, "A student")
    trainer_users = db.execute(select(Trainer.user_id).join(BatchTrainer, BatchTrainer.trainer_id == Trainer.id)
                               .where(BatchTrainer.batch_id == child.batch_id)).scalars().all()
    for uid in trainer_users:
        notify_user(db, uid, f"Leave request: {name}", f"{r.start_date.isoformat()} to {r.end_date.isoformat()}",
                    title_ta=f"விடுப்புக் கோரிக்கை: {name}", kind="approval", link="/trainer/approvals", college_id=child.college_id)
    db.commit()
    return _leave_out(r)


# ---------------------------------------------------------------------------
# 43 · trainer approvals (one queue)
# ---------------------------------------------------------------------------

@router.get("/trainer/approvals")
def approvals_queue(status_filter: str = Query("pending", alias="status"), current_user: TokenPayload = Depends(TRAINER),
                    db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = get_trainer_batch_ids(trainer, db) or ["__none__"]
    states = None if status_filter == "all" else ([status_filter] if status_filter != "decided" else ["approved", "denied"])
    items = []
    q = (select(LeaveRequest, Student, User.name).join(Student, Student.id == LeaveRequest.student_id)
         .join(User, User.id == Student.user_id).where(LeaveRequest.college_id == current_user.college_id, Student.batch_id.in_(batch_ids)))
    if states:
        q = q.where(LeaveRequest.status.in_(states))
    for r, st, name in db.execute(q).all():
        items.append({"type": "leave", "id": r.id, "student_id": st.id, "student_name": name, "batch": st.batch_name, "status": r.status,
                      "detail": {"start_date": r.start_date.isoformat(), "end_date": r.end_date.isoformat(), "reason": r.reason,
                                 "requested_by": get_user_name(db, r.requested_by, "Parent")},
                      "decision_note": r.decision_note, "requested_at": r.created_at.isoformat()})
    q = (select(LabApproval, Student, User.name, VirtualLabItem.name).join(Student, Student.id == LabApproval.student_id)
         .join(User, User.id == Student.user_id).join(VirtualLabItem, VirtualLabItem.id == LabApproval.lab_id)
         .where(LabApproval.college_id == current_user.college_id, Student.batch_id.in_(batch_ids)))
    if states:
        q = q.where(LabApproval.status.in_(states))
    for ap, st, name, lab in db.execute(q).all():
        items.append({"type": "lab_access", "id": ap.id, "student_id": st.id, "student_name": name, "batch": st.batch_name,
                      "status": ap.status, "detail": {"lab_name": lab, "aup_accepted": ap.aup_accepted_at is not None},
                      "decision_note": ap.reason if ap.status != "pending" else None,
                      "requested_at": ap.created_at.isoformat() if ap.created_at else None})
    items.sort(key=lambda i: i["requested_at"] or "", reverse=True)
    return {"items": items, "counts": {"leave": sum(1 for i in items if i["type"] == "leave"),
                                       "lab_access": sum(1 for i in items if i["type"] == "lab_access")}}


@router.post("/trainer/approvals/leave/{leave_id}")
def decide_leave(leave_id: str, req: DecisionIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = set(get_trainer_batch_ids(trainer, db))
    r = db.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id, LeaveRequest.college_id == current_user.college_id)).scalar_one_or_none()
    st = db.get(Student, r.student_id) if r else None
    if r is None or st is None or st.batch_id not in batch_ids:
        raise HTTPException(status_code=404, detail="Leave request not found in your batches")
    if r.status != "pending":
        raise HTTPException(status_code=409, detail=f"This request is already {r.status}")
    note = (req.note or "").strip() or None
    if req.decision == "deny" and not note:
        raise HTTPException(status_code=422, detail="Give a reason when denying leave")
    now = datetime.datetime.now()
    r.status = "approved" if req.decision == "approve" else "denied"
    r.decided_by, r.decision_note, r.decided_at = trainer.id, note, datetime.datetime.utcnow()
    effect = apply_approved_leave(db, r, now) if r.status == "approved" else {"excused": 0, "kept": 0}
    record_audit(db, current_user, f"leave.{r.status}", "leave_request", r.id, {"student_id": st.id, **effect})
    name = get_user_name(db, st.user_id, "your child")
    dates = f"{r.start_date.isoformat()} to {r.end_date.isoformat()}"
    if r.status == "approved":
        title, title_ta, body = f"Leave approved for {name}", f"{name} விடுப்பு அனுமதிக்கப்பட்டது", dates
    else:
        title, title_ta, body = f"Leave not approved for {name}", f"{name} விடுப்பு அனுமதிக்கப்படவில்லை", f"{dates}: {note}"
    text = render(db, f"leave.{r.status}", {"title_en": title, "title_ta": title_ta, "body_en": body, "body_ta": None},
                  student=name, dates=dates, note=note or "")              # screen 46 template when one exists (L37)
    notify_user(db, r.requested_by, text["title_en"], text["body_en"], title_ta=text["title_ta"], body_ta=text["body_ta"],
                kind="approval", link="/parent/attendance", college_id=r.college_id)
    db.commit()
    return {"id": r.id, "status": r.status, **effect}
