"""Screen 36 Student Mock Interviews (+ the trainer actions Screen 37 builds on)."""
import datetime
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import require_role, TokenPayload
from core.tenant import get_student_for_user, get_trainer_for_user, get_trainer_batch_ids
from models.schema import Interview, InterviewSlot, InterviewRubricScore, InterviewComment, Student
from services.interviews import build_student_interviews, book_slot, cancel_booking, rubric_config, recording_url
from services.notifications import notify_user
from services.audit import record_audit

router = APIRouter(tags=["Mock Interviews"])


class SlotCreate(BaseModel):
    starts_at: datetime.datetime
    round_type: str = "technical"
    duration_min: int = Field(default=40, ge=15, le=120)
    batch_id: Optional[str] = None


class CommentIn(BaseModel):
    at_seconds: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=1000)


class SubmitScores(BaseModel):
    scores: Dict[str, int]
    overall: Optional[float] = Field(default=None, ge=1, le=5)   # trainer's holistic score; defaults to the rubric average
    feedback_en: str = Field(min_length=5)
    feedback_ta: Optional[str] = None
    comments: List[CommentIn] = []


# ---------------- student ----------------

@router.get("/student/interviews")
def get_my_interviews(lang: str = "en", current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    return build_student_interviews(db, student, lang)


@router.post("/student/interview-slots/{slot_id}/book")
def book(slot_id: str, current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    booking = book_slot(db, student, slot_id)
    slot = db.execute(select(InterviewSlot).filter_by(id=slot_id)).scalar_one()
    when = slot.starts_at.strftime("%a %b %d, %I:%M %p")
    notify_user(db, current_user.sub, "Mock interview booked", f"Your {slot.round_type.replace('_', ' ')} round is on {when}.",
                title_ta="மாதிரி நேர்காணல் பதிவு செய்யப்பட்டது", kind="reminder", link="/student/interviews", college_id=student.college_id)
    from models.schema import Trainer
    tr = db.execute(select(Trainer).filter_by(id=slot.trainer_id)).scalar_one_or_none()
    if tr:
        notify_user(db, tr.user_id, f"Interview booked by {current_user.name}", f"{when} · {slot.round_type.replace('_', ' ')}", kind="info",
                    link="/trainer/interviews", college_id=student.college_id)
    record_audit(db, current_user, "interview.book", "interview_slot", slot.id)
    db.commit()
    return {"success": True, "booking_id": booking.id}


@router.delete("/student/bookings/{booking_id}")
def cancel(booking_id: str, current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    cancel_booking(db, student, booking_id)
    record_audit(db, current_user, "interview.cancel", "interview_booking", booking_id)
    db.commit()
    return {"success": True}


@router.get("/student/interviews/{interview_id}/recording")
def get_recording(interview_id: str, current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    iv = db.execute(select(Interview).filter_by(id=interview_id, student_id=student.id)).scalar_one_or_none()
    if not iv or not iv.submitted_at:
        raise HTTPException(status_code=404, detail="Interview not found")
    if not iv.recording_key:
        raise HTTPException(status_code=404, detail="No recording for this interview")
    return {"url": recording_url(iv), "duration_min": iv.duration_min}


# ---------------- trainer ----------------

@router.post("/trainer/interview-slots")
def create_slot(req: SlotCreate, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    if req.round_type not in ("technical", "hr", "ai_coding"):
        raise HTTPException(status_code=422, detail="round_type must be technical, hr or ai_coding")
    if req.batch_id and req.batch_id not in get_trainer_batch_ids(trainer, db):
        raise HTTPException(status_code=404, detail="Batch not found")
    slot = InterviewSlot(id=f"slot_{uuid.uuid4().hex[:12]}", college_id=trainer.college_id, trainer_id=trainer.id, batch_id=req.batch_id,
                         round_type=req.round_type, starts_at=req.starts_at, duration_min=req.duration_min, status="open")
    db.add(slot)
    db.commit()
    return {"success": True, "slot_id": slot.id}


@router.post("/trainer/interviews/{interview_id}/submit")
def submit_scores(interview_id: str, req: SubmitScores, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    iv = db.execute(select(Interview).filter_by(id=interview_id, college_id=current_user.college_id, trainer_id=trainer.id)).scalar_one_or_none()
    if not iv:
        raise HTTPException(status_code=404, detail="Interview not found")
    if iv.submitted_at:
        raise HTTPException(status_code=409, detail="Scores were already submitted")
    cfg = rubric_config(db, iv.college_id)
    keys = [c["key"] for c in cfg.criteria]
    if set(req.scores) != set(keys):
        raise HTTPException(status_code=422, detail=f"Score every criterion: {', '.join(keys)}")
    if any(not (1 <= v <= cfg.max_score) for v in req.scores.values()):
        raise HTTPException(status_code=422, detail=f"Scores run from 1 to {cfg.max_score}")
    db.execute(delete(InterviewRubricScore).where(InterviewRubricScore.interview_id == iv.id))
    for k, v in req.scores.items():
        db.add(InterviewRubricScore(id=f"rs_{uuid.uuid4().hex[:16]}", college_id=iv.college_id, interview_id=iv.id, criterion_key=k, score=v))
    for c in req.comments:
        db.add(InterviewComment(id=f"ic_{uuid.uuid4().hex[:16]}", college_id=iv.college_id, interview_id=iv.id, at_seconds=c.at_seconds,
                                text=c.text, author_name=current_user.name or "Trainer"))
    iv.overall_score = round(req.overall if req.overall is not None else sum(req.scores.values()) / len(req.scores), 1)
    iv.feedback_en, iv.feedback_ta = req.feedback_en.strip(), (req.feedback_ta or "").strip() or None
    iv.status, iv.submitted_at = "submitted", datetime.datetime.utcnow()
    st = db.execute(select(Student).filter_by(id=iv.student_id)).scalar_one()
    notify_user(db, st.user_id, f"Interview #{iv.round_number} feedback is ready", f"Overall {iv.overall_score} / {cfg.max_score}",
                title_ta=f"நேர்காணல் #{iv.round_number} கருத்து தயார்", kind="info", link="/student/interviews", college_id=iv.college_id)
    record_audit(db, current_user, "interview.submit", "interview", iv.id, {"overall": iv.overall_score})
    db.commit()
    return {"success": True, "overall": iv.overall_score}
