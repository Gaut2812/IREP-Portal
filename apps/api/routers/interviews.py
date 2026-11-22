"""Screen 36 Student Mock Interviews and Screen 37 Trainer Mock Interviews (L16; drive slots L17).
Spec: docs/screens/37-38-39-interviews-drives-readiness.md"""
import datetime
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import require_role, TokenPayload
from core.tenant import get_student_for_user, get_trainer_for_user, get_trainer_batch_ids
from models.schema import (Batch, DriveRound, Event, Interview, InterviewBooking, InterviewComment, InterviewRubricScore,
                           InterviewSlot, MockDrive, Student, User)
from services.interviews import ROUND_LABEL, build_student_interviews, book_slot, cancel_booking, rubric_config, recording_url
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
                    link="/trainer", college_id=student.college_id)
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


# ---------------- trainer overview (screen 37) ----------------

TRAINER = require_role(["trainer"])
RECORDING_TYPES = {"video/mp4": "mp4", "video/webm": "webm", "audio/mpeg": "mp3", "audio/mp4": "m4a"}
MAX_RECORDING_MB = 500


def _round_label(round_type: str, lang: str) -> str:
    return ROUND_LABEL.get(round_type, ROUND_LABEL["technical"])["ta" if lang == "ta" else "en"]


@router.get("/trainer/interviews")
def trainer_interviews(lang: str = "en", current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """Slots (with who booked them), interviews waiting for scores, recent results, the rubric and
    the trainer's batches. Drive slots carry the drive's title (L17)."""
    trainer = get_trainer_for_user(current_user, db)
    now = datetime.datetime.now()
    batch_ids = get_trainer_batch_ids(trainer, db)
    cfg = rubric_config(db, trainer.college_id)
    slots = db.execute(select(InterviewSlot).where(InterviewSlot.trainer_id == trainer.id, InterviewSlot.college_id == trainer.college_id,
                                                   InterviewSlot.status != "cancelled", InterviewSlot.starts_at > now - datetime.timedelta(hours=2))
                       .order_by(InterviewSlot.starts_at)).scalars().all()
    bookings = {b.slot_id: b for b in db.execute(select(InterviewBooking).where(InterviewBooking.slot_id.in_([s.id for s in slots] or ["_"]))).scalars()}
    names = dict(db.execute(select(Student.id, User.name).join(User, User.id == Student.user_id)
                            .where(Student.college_id == trainer.college_id)).all())
    drive_titles = dict(db.execute(select(DriveRound.id, Event.title_ta if lang == "ta" else Event.title_en)
                                   .join(MockDrive, MockDrive.id == DriveRound.drive_id).join(Event, Event.id == MockDrive.event_id)
                                   .where(DriveRound.college_id == trainer.college_id)).all())
    ivs = db.execute(select(Interview).where(Interview.trainer_id == trainer.id, Interview.college_id == trainer.college_id,
                                             Interview.status != "cancelled").order_by(Interview.scheduled_at.desc())).scalars().all()
    slot_drive = dict(db.execute(select(InterviewSlot.id, InterviewSlot.drive_round_id)
                                 .where(InterviewSlot.id.in_([i.slot_id for i in ivs if i.slot_id] or ["_"]))).all())

    def iv_row(i: Interview) -> dict:
        return {"id": i.id, "student_id": i.student_id, "student": names.get(i.student_id, "Student"), "round_number": i.round_number,
                "round_type": i.round_type, "round_label": _round_label(i.round_type, lang), "scheduled_at": i.scheduled_at.isoformat(),
                "duration_min": i.duration_min, "overall": i.overall_score, "has_recording": bool(i.recording_key),
                "drive": drive_titles.get(slot_drive.get(i.slot_id)) if i.slot_id else None}

    return {
        "rubric": {"max": cfg.max_score, "criteria": [{"key": c["key"], "label": c["label_ta"] if lang == "ta" else c["label_en"]} for c in cfg.criteria]},
        "batches": [{"id": b, "name": n} for b, n in db.execute(select(Batch.id, Batch.name).where(Batch.id.in_(batch_ids or ["_"]))).all()],
        "slots": [{"id": sl.id, "starts_at": sl.starts_at.isoformat(), "duration_min": sl.duration_min, "round_type": sl.round_type,
                   "round_label": _round_label(sl.round_type, lang), "batch_id": sl.batch_id,
                   "booked_by": names.get(bookings[sl.id].student_id) if sl.id in bookings else None,
                   "drive": drive_titles.get(sl.drive_round_id), "can_cancel": sl.starts_at > now}
                  for sl in slots],
        "to_score": [iv_row(i) for i in ivs if i.submitted_at is None and i.scheduled_at <= now],
        "upcoming": [iv_row(i) for i in ivs if i.submitted_at is None and i.scheduled_at > now],
        "submitted": [iv_row(i) for i in ivs if i.submitted_at is not None][:20],
    }


@router.delete("/trainer/interview-slots/{slot_id}")
def cancel_slot(slot_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """Cancel a slot that has not started; a booked slot also cancels the interview and tells the student."""
    trainer = get_trainer_for_user(current_user, db)
    slot = db.execute(select(InterviewSlot).filter_by(id=slot_id, trainer_id=trainer.id, college_id=trainer.college_id)).scalar_one_or_none()
    if slot is None or slot.status == "cancelled":
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.starts_at <= datetime.datetime.now():
        raise HTTPException(status_code=409, detail="This slot has already started")
    booking = db.execute(select(InterviewBooking).filter_by(slot_id=slot.id)).scalar_one_or_none()
    student_user = None
    if booking:
        iv = db.get(Interview, booking.interview_id) if booking.interview_id else None
        if iv:
            iv.status = "cancelled"
        st = db.get(Student, booking.student_id)
        student_user = st.user_id if st else None
        db.delete(booking)
    slot.status = "cancelled"
    record_audit(db, current_user, "interview.slot_cancelled", "interview_slot", slot.id, {"was_booked": booking is not None})
    if student_user:
        when = slot.starts_at.strftime("%a %b %d, %I:%M %p")
        notify_user(db, student_user, "Mock interview cancelled", f"Your {slot.round_type.replace('_', ' ')} round on {when} was cancelled by the trainer. Book another slot.",
                    title_ta="மாதிரி நேர்காணல் ரத்து செய்யப்பட்டது", body_ta="பயிற்சியாளர் இந்த நேரத்தை ரத்து செய்தார். வேறு நேரத்தைப் பதிவு செய்யுங்கள்.",
                    kind="reminder", link="/student/interviews", college_id=slot.college_id)
    db.commit()
    return {"success": True}


@router.post("/trainer/interviews/{interview_id}/recording")
async def add_recording(interview_id: str, file: UploadFile = File(...), current_user: TokenPayload = Depends(TRAINER),
                        db: Session = Depends(get_db)):
    """Store the interview recording (storage interface) for the student's signed link on 36 (L16)."""
    from services.quotas import can_store_recording
    from services.storage import get_storage
    trainer = get_trainer_for_user(current_user, db)
    iv = db.execute(select(Interview).filter_by(id=interview_id, trainer_id=trainer.id, college_id=trainer.college_id)).scalar_one_or_none()
    if iv is None or iv.status == "cancelled":
        raise HTTPException(status_code=404, detail="Interview not found")
    ext = RECORDING_TYPES.get((file.content_type or "").split(";")[0].strip())
    if ext is None:
        raise HTTPException(status_code=415, detail="Upload an MP4 or WebM video, or an MP3/M4A audio file")
    data = await file.read(MAX_RECORDING_MB * 1024 * 1024 + 1)
    if len(data) > MAX_RECORDING_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Recordings can be at most {MAX_RECORDING_MB} MB")
    size_mb = max(1, len(data) // (1024 * 1024))
    if not can_store_recording(db, iv.college_id, size_mb):          # L36: the MoU's storage quota
        raise HTTPException(status_code=409, detail="The college's recording storage is full (MoU quota)")
    key = f"recordings/interviews/{iv.id}.{ext}"
    get_storage().put(key, data, file.content_type)
    iv.recording_key = key
    record_audit(db, current_user, "interview.recording_added", "interview", iv.id, {"size_mb": size_mb})
    db.commit()
    return {"success": True, "has_recording": True}
