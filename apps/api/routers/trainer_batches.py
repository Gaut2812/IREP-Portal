"""Screen 04 · Trainer batches (roster, student profiles, private notes) and the
college side of roster change requests (link L24). Spec: docs/screens/04-trainer-batches.md
"""
import datetime
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_trainer_batch_ids, get_trainer_for_user
from models.schema import (AtRiskFlag, Batch, BatchTrainer, ParentStudent, RosterChangeRequest, Student, Trainer, TrainerNote,
                           User)
from services.audit import record_audit
from services.notifications import notify_user

router = APIRouter(tags=["Screen 04 · Trainer batches"])
TRAINER = require_role(["trainer"])
COLLEGE = require_role(["college_admin"])


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class RosterRequestIn(BaseModel):
    student_id: str
    kind: str = Field(pattern="^(move|remove)$")
    to_batch_id: Optional[str] = None
    reason: str = Field(min_length=10, max_length=2000)


class DecisionIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


# ---- helpers ----
def _my_batches(db: Session, user: TokenPayload):
    trainer = get_trainer_for_user(user, db)
    return trainer, set(get_trainer_batch_ids(trainer, db))


def _my_student(db: Session, user: TokenPayload, student_id: str):
    trainer, batch_ids = _my_batches(db, user)
    s = db.execute(select(Student).where(Student.id == student_id, Student.college_id == user.college_id)).scalar_one_or_none()
    if s is None or s.batch_id not in batch_ids:
        raise HTTPException(status_code=404, detail="Student not found in your batches")
    return trainer, s


def _names(db: Session, user_ids) -> dict:
    ids = set(user_ids) or {"_"}
    return dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all())


# ---- trainer: batches and roster ----
@router.get("/trainer/batches")
def my_batches(current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer, batch_ids = _my_batches(db, current_user)
    if not batch_ids:
        return {"batches": []}
    roles = dict(db.execute(select(BatchTrainer.batch_id, BatchTrainer.role).where(BatchTrainer.trainer_id == trainer.id)).all())
    stats = {r[0]: r[1:] for r in db.execute(
        select(Student.batch_id, func.count(Student.id), func.avg(Student.readiness_score), func.avg(Student.attendance_pct))
        .where(Student.batch_id.in_(batch_ids), Student.college_id == current_user.college_id).group_by(Student.batch_id)).all()}
    batches = db.execute(select(Batch).where(Batch.id.in_(batch_ids)).order_by(Batch.semester, Batch.short_name)).scalars().all()
    from models.schema import Branch, College
    college = db.get(College, current_user.college_id)
    branches = {br.id: br for br in db.execute(select(Branch).where(Branch.id.in_([b.branch_id for b in batches] or ["_"]))).scalars()}
    return {"college": {"id": college.id, "name": college.name, "code": college.code} if college else None, "batches": [{
        "branch": branches[b.branch_id].name if b.branch_id in branches else None,
        "branch_code": branches[b.branch_id].code if b.branch_id in branches else None,
        "college": college.name if college else None,
        "id": b.id, "short_name": b.short_name, "name": b.name, "semester": b.semester, "academic_year": b.academic_year,
        "track": b.track, "role": roles.get(b.id, "primary"), "students": stats.get(b.id, (0, None, None))[0],
        "avg_readiness": round(stats[b.id][1]) if b.id in stats and stats[b.id][1] is not None else None,
        "avg_attendance": round(stats[b.id][2]) if b.id in stats and stats[b.id][2] is not None else None,
    } for b in batches]}


@router.get("/trainer/batches/{batch_id}/roster")
def roster(batch_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    _, batch_ids = _my_batches(db, current_user)
    if batch_id not in batch_ids:
        raise HTTPException(status_code=404, detail="Batch not found in your batches")
    b = db.get(Batch, batch_id)
    rows = db.execute(select(Student, User.name).join(User, User.id == Student.user_id)
                      .where(Student.batch_id == batch_id, Student.college_id == current_user.college_id).order_by(User.name)).all()
    open_flags = dict(db.execute(select(AtRiskFlag.student_id, func.count(AtRiskFlag.id))
                                 .where(AtRiskFlag.student_id.in_([s.id for s, _ in rows] or ["_"]), AtRiskFlag.status != "resolved")
                                 .group_by(AtRiskFlag.student_id)).all())
    pending = set(db.execute(select(RosterChangeRequest.student_id).where(RosterChangeRequest.from_batch_id == batch_id,
                                                                          RosterChangeRequest.status == "open")).scalars())
    from models.schema import Branch, College
    br, college = db.get(Branch, b.branch_id), db.get(College, b.college_id)
    return {"batch": {"id": b.id, "short_name": b.short_name, "name": b.name, "semester": b.semester, "academic_year": b.academic_year,
                      "branch": br.name if br else None, "college": college.name if college else None},
            "students": [{"id": s.id, "name": name, "register_no": s.register_no, "readiness_score": s.readiness_score,
                          "readiness_band": s.readiness_band, "attendance_pct": s.attendance_pct, "open_flags": open_flags.get(s.id, 0),
                          "pending_roster_request": s.id in pending} for s, name in rows]}


@router.get("/trainer/students/{student_id}")
def student_profile(student_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer, s = _my_student(db, current_user, student_id)
    u = db.get(User, s.user_id)
    parents = db.execute(select(User.name, ParentStudent.relationship).join(ParentStudent, ParentStudent.parent_user_id == User.id)
                         .where(ParentStudent.student_id == s.id)).all()
    notes = db.execute(select(TrainerNote).where(TrainerNote.student_id == s.id).order_by(TrainerNote.created_at.desc())).scalars().all()
    authors = dict(db.execute(select(Trainer.id, User.name).join(User, User.id == Trainer.user_id)
                              .where(Trainer.id.in_({n.author_trainer_id for n in notes} or {"_"}))).all())
    req = db.execute(select(RosterChangeRequest).where(RosterChangeRequest.student_id == s.id, RosterChangeRequest.status == "open")).scalars().first()
    other_batches = db.execute(select(Batch).where(Batch.college_id == s.college_id, Batch.semester == s.semester,
                                                   Batch.id != s.batch_id).order_by(Batch.short_name)).scalars().all()
    return {
        "student": {"id": s.id, "name": u.name if u else "", "register_no": s.register_no, "branch": s.branch, "semester": s.semester,
                    "batch": s.batch_name, "batch_id": s.batch_id, "track": s.track, "readiness_score": s.readiness_score,
                    "readiness_band": s.readiness_band, "attendance_pct": s.attendance_pct, "problems_solved": s.problems_solved,
                    "email": u.email if u else None},
        "parents": [{"name": n, "relationship": r} for n, r in parents],               # names only (§5.4)
        "notes": [{"id": n.id, "text": n.text, "author": authors.get(n.author_trainer_id, ""), "mine": n.author_trainer_id == trainer.id,
                   "at": n.created_at.isoformat()} for n in notes],
        "open_roster_request": {"id": req.id, "kind": req.kind, "to_batch_id": req.to_batch_id} if req else None,
        "move_targets": [{"id": b.id, "short_name": b.short_name} for b in other_batches],
    }


@router.post("/trainer/students/{student_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(student_id: str, req: NoteIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer, s = _my_student(db, current_user, student_id)
    n = TrainerNote(id=f"tn_{uuid.uuid4().hex[:16]}", college_id=s.college_id, student_id=s.id, author_trainer_id=trainer.id,
                    text=req.text.strip())
    db.add(n)
    record_audit(db, current_user, "trainer.note_added", "student", s.id, {"note_id": n.id})     # never the note text
    db.commit()
    return {"id": n.id}


@router.delete("/trainer/notes/{note_id}")
def delete_note(note_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    n = db.execute(select(TrainerNote).where(TrainerNote.id == note_id, TrainerNote.college_id == current_user.college_id)).scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail="Note not found")
    if n.author_trainer_id != trainer.id:
        raise HTTPException(status_code=403, detail="Only the author can delete a note")
    db.delete(n)
    record_audit(db, current_user, "trainer.note_deleted", "student", n.student_id, {"note_id": n.id})
    db.commit()
    return {"success": True}


@router.post("/trainer/roster-requests", status_code=status.HTTP_201_CREATED)
def request_roster_change(req: RosterRequestIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer, s = _my_student(db, current_user, req.student_id)
    to = None
    if req.kind == "move":
        if not req.to_batch_id:
            raise HTTPException(status_code=422, detail="Choose the batch to move the student to")
        to = db.execute(select(Batch).where(Batch.id == req.to_batch_id, Batch.college_id == s.college_id)).scalar_one_or_none()
        if to is None:
            raise HTTPException(status_code=404, detail="Target batch not found")
        if to.id == s.batch_id or to.semester != s.semester:
            raise HTTPException(status_code=422, detail="Move to a different batch of the same semester")
    if db.execute(select(RosterChangeRequest.id).where(RosterChangeRequest.student_id == s.id, RosterChangeRequest.status == "open")).first():
        raise HTTPException(status_code=409, detail="This student already has an open roster request")
    r = RosterChangeRequest(id=f"rcr_{uuid.uuid4().hex[:16]}", college_id=s.college_id, student_id=s.id, from_batch_id=s.batch_id,
                            to_batch_id=to.id if to else None, kind=req.kind, reason=req.reason.strip(), requested_by_trainer_id=trainer.id)
    db.add(r)
    db.flush()
    record_audit(db, current_user, "roster.change_requested", "student", s.id, {"request_id": r.id, "kind": r.kind, "to_batch_id": r.to_batch_id})
    for admin_id in db.execute(select(User.id).where(User.college_id == s.college_id, User.role == "college_admin", User.is_active.is_(True))).scalars():
        who = db.get(User, trainer.user_id)
        notify_user(db, admin_id, "Roster change requested", f"{who.name if who else 'A trainer'} asked to {r.kind} a student",
                    title_ta="தொகுதி மாற்றக் கோரிக்கை",
                    kind="approval", link="/college/structure", college_id=s.college_id)
    db.commit()
    return {"id": r.id, "status": r.status}


# ---- college: approve or reject (03 side of L24) ----
def _request_out(r: RosterChangeRequest, names: dict, batches: dict) -> dict:
    return {"id": r.id, "kind": r.kind, "student_id": r.student_id, "student_name": names.get(r.student_id),
            "from_batch": batches.get(r.from_batch_id), "to_batch": batches.get(r.to_batch_id), "reason": r.reason,
            "status": r.status, "decision_note": r.decision_note, "at": r.created_at.isoformat()}


@router.get("/college/roster-requests")
def college_roster_requests(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    open_first = case((RosterChangeRequest.status == "open", 0), else_=1)
    rows = db.execute(select(RosterChangeRequest).where(RosterChangeRequest.college_id == current_user.college_id)
                      .order_by(open_first, RosterChangeRequest.created_at.desc()).limit(200)).scalars().all()
    names = dict(db.execute(select(Student.id, User.name).join(User, User.id == Student.user_id)
                            .where(Student.id.in_({r.student_id for r in rows} or {"_"}))).all())
    batches = dict(db.execute(select(Batch.id, Batch.short_name).where(Batch.college_id == current_user.college_id)).all())
    return {"items": [_request_out(r, names, batches) for r in rows]}


def _open_request(db: Session, user: TokenPayload, request_id: str) -> RosterChangeRequest:
    r = db.execute(select(RosterChangeRequest).where(RosterChangeRequest.id == request_id,
                                                     RosterChangeRequest.college_id == user.college_id)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if r.status != "open":
        raise HTTPException(status_code=409, detail=f"This request is already {r.status}")
    return r


def _notify_trainer(db: Session, r: RosterChangeRequest, title: str, body: str) -> None:
    t = db.get(Trainer, r.requested_by_trainer_id)
    if t:
        notify_user(db, t.user_id, title, body, kind="approval", link=f"/trainer/students/{r.student_id}", college_id=r.college_id)


@router.post("/college/roster-requests/{request_id}/approve")
def approve_roster_request(request_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    r = _open_request(db, current_user, request_id)
    s = db.get(Student, r.student_id)
    if r.kind == "move":
        to = db.get(Batch, r.to_batch_id)
        s.batch_id, s.batch_name, s.semester = to.id, to.name, to.semester
    else:
        s.batch_id, s.batch_name = None, ""
    r.status, r.decided_by, r.decided_at = "approved", current_user.sub, datetime.datetime.utcnow()
    record_audit(db, current_user, "roster.change_approved", "student", s.id, {"request_id": r.id, "kind": r.kind, "to_batch_id": r.to_batch_id})
    _notify_trainer(db, r, "Roster change approved", f"The {r.kind} request was approved.")
    db.commit()
    return {"id": r.id, "status": r.status, "student_batch_id": s.batch_id}


@router.post("/college/roster-requests/{request_id}/reject")
def reject_roster_request(request_id: str, req: DecisionIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    if not req.reason or len(req.reason.strip()) < 5:
        raise HTTPException(status_code=422, detail="Give a reason for rejecting (at least 5 characters)")
    r = _open_request(db, current_user, request_id)
    r.status, r.decision_note, r.decided_by, r.decided_at = "rejected", req.reason.strip(), current_user.sub, datetime.datetime.utcnow()
    record_audit(db, current_user, "roster.change_rejected", "student", r.student_id, {"request_id": r.id})
    _notify_trainer(db, r, "Roster change rejected", r.decision_note)
    db.commit()
    return {"id": r.id, "status": r.status}
