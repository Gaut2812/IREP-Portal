"""Screen 36/37 mock interviews.

Booking: one booking per slot, enforced by a UNIQUE constraint on
interview_bookings.slot_id, so two students racing for the same slot can
never both win. Scores: rubric rows exist only once the trainer submits;
the student sees nothing about a round until `submitted_at` is set.
"""
import datetime
import uuid
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.schema import (
    Interview, InterviewSlot, InterviewBooking, InterviewRubricScore, InterviewComment, RubricConfig,
    Student, Trainer, User, BatchTrainer,
)
from services.live_sessions import sign_url

DEFAULT_CRITERIA = [
    {"key": "problem_solving", "label_en": "Problem solving", "label_ta": "சிக்கல் தீர்த்தல்"},
    {"key": "coding", "label_en": "Coding & correctness", "label_ta": "கோடிங் & துல்லியம்"},
    {"key": "thinking_aloud", "label_en": "Thinking aloud", "label_ta": "உரக்கச் சிந்தித்தல்"},
    {"key": "core_cs", "label_en": "Core CS knowledge", "label_ta": "அடிப்படை CS அறிவு"},
    {"key": "project", "label_en": "Project explanation", "label_ta": "புராஜெக்ட் விளக்கம்"},
    {"key": "communication", "label_en": "Communication & confidence", "label_ta": "தொடர்பு & தன்னம்பிக்கை"},
]
ROUND_LABEL = {
    "technical": {"en": "Technical", "ta": "தொழில்நுட்பம்"},
    "hr": {"en": "HR round", "ta": "HR சுற்று"},
    "ai_coding": {"en": "AI-allowed coding", "ta": "AI அனுமதி கோடிங்"},
}
CANCEL_CUTOFF_HOURS = 2


def rubric_config(db: Session, college_id: str) -> RubricConfig:
    cfg = db.execute(select(RubricConfig).filter_by(college_id=college_id, round_type="technical")).scalars().first()
    if not cfg:
        cfg = RubricConfig(id=f"rub_{college_id}", college_id=college_id, round_type="technical", criteria=DEFAULT_CRITERIA)
        db.add(cfg)
        db.flush()
    return cfg


def verdict_chips(overall: float, cfg: RubricConfig, lang: str) -> List[dict]:
    chips = []
    if overall >= cfg.service_ready_min:
        chips.append({"label": "சேவை நிறுவனப் பணிக்குத் தயார்" if lang == "ta" else "Hire-ready for service roles", "type": "green"})
    else:
        chips.append({"label": "சேவை நிறுவனங்களுக்கு மேம்படுத்தவும்" if lang == "ta" else "Improve for service roles", "type": "amber"})
    if overall >= cfg.product_ready_min:
        chips.append({"label": "தயாரிப்பு நிறுவனப் பணிக்குத் தயார்" if lang == "ta" else "Hire-ready for product roles", "type": "green"})
    else:
        chips.append({"label": "தயாரிப்பு நிறுவனங்களுக்கு மேம்படுத்தவும்" if lang == "ta" else "Improve for product roles", "type": "amber"})
    return chips


def _slot_label(when: datetime.datetime) -> dict:
    return {"date": when.strftime("%a, %b %d").replace(" 0", " "), "time": when.strftime("%I:%M %p").lstrip("0")}


def student_trainer_ids(db: Session, student: Student) -> List[str]:
    return list(db.execute(select(BatchTrainer.trainer_id).filter_by(batch_id=student.batch_id)).scalars().all())


def build_student_interviews(db: Session, student: Student, lang: str = "en", now: Optional[datetime.datetime] = None) -> dict:
    now = now or datetime.datetime.now()
    cfg = rubric_config(db, student.college_id)
    submitted = db.execute(
        select(Interview).where(Interview.student_id == student.id, Interview.submitted_at.is_not(None))
        .order_by(Interview.round_number)
    ).scalars().all()
    latest = submitted[-1] if submitted else None
    trainer_names = {t.id: n for t, n in db.execute(select(Trainer, User.name).join(User, User.id == Trainer.user_id)).all()}

    latest_payload = None
    if latest:
        scores = {s.criterion_key: s.score for s in db.execute(select(InterviewRubricScore).filter_by(interview_id=latest.id)).scalars().all()}
        comments = db.execute(select(InterviewComment).filter_by(interview_id=latest.id).order_by(InterviewComment.at_seconds)).scalars().all()
        rl = ROUND_LABEL.get(latest.round_type, ROUND_LABEL["technical"])[lang if lang in ("en", "ta") else "en"]
        latest_payload = {
            "id": latest.id, "round_number": latest.round_number, "round_type": latest.round_type,
            "title": f"Mock Interview #{latest.round_number} – {rl}" if lang != "ta" else f"மாதிரி நேர்காணல் #{latest.round_number} – {rl}",
            "date": latest.scheduled_at.strftime("%b %d").replace(" 0", " "), "duration_min": latest.duration_min,
            "interviewer": trainer_names.get(latest.trainer_id, "Trainer"),
            "overall": latest.overall_score, "max": cfg.max_score, "chips": verdict_chips(latest.overall_score or 0, cfg, lang),
            "rubric": [{"key": c["key"], "label": c["label_ta"] if lang == "ta" else c["label_en"], "score": scores.get(c["key"], 0), "max": cfg.max_score} for c in cfg.criteria],
            "feedback": (latest.feedback_ta if lang == "ta" and latest.feedback_ta else latest.feedback_en),
            "has_recording": bool(latest.recording_key),
            "comments": [{"id": c.id, "at_seconds": c.at_seconds, "label": f"{c.at_seconds // 60}:{c.at_seconds % 60:02d}", "text": c.text, "author": c.author_name} for c in comments],
        }

    trainers = student_trainer_ids(db, student)
    booked_slot_ids = set(db.execute(select(InterviewBooking.slot_id)).scalars().all())
    slots = db.execute(
        select(InterviewSlot).where(InterviewSlot.college_id == student.college_id, InterviewSlot.trainer_id.in_(trainers or ["_"]),
                                    InterviewSlot.status == "open", InterviewSlot.starts_at > now)
        .order_by(InterviewSlot.starts_at).limit(8)
    ).scalars().all()
    mine = db.execute(
        select(InterviewBooking, InterviewSlot).join(InterviewSlot, InterviewSlot.id == InterviewBooking.slot_id)
        .where(InterviewBooking.student_id == student.id, InterviewSlot.starts_at > now).order_by(InterviewSlot.starts_at)
    ).all()

    return {
        "latest_interview": latest_payload,
        "trend": [{"round": i.round_number, "label": f"#{i.round_number} · {i.overall_score:.1f}", "score": i.overall_score} for i in submitted],
        "target": cfg.product_ready_min,
        "available_slots": [
            {"id": s.id, **_slot_label(s.starts_at), "starts_at": s.starts_at.isoformat(), "round_type": s.round_type,
             "type_label": ROUND_LABEL.get(s.round_type, ROUND_LABEL["technical"])[lang if lang in ("en", "ta") else "en"],
             "trainer": trainer_names.get(s.trainer_id, "Trainer")}
            for s in slots if s.id not in booked_slot_ids
        ],
        "my_bookings": [
            {"id": b.id, "slot_id": s.id, **_slot_label(s.starts_at), "starts_at": s.starts_at.isoformat(), "round_type": s.round_type,
             "type_label": ROUND_LABEL.get(s.round_type, ROUND_LABEL["technical"])[lang if lang in ("en", "ta") else "en"],
             "trainer": trainer_names.get(s.trainer_id, "Trainer"),
             "can_cancel": s.starts_at - now > datetime.timedelta(hours=CANCEL_CUTOFF_HOURS)}
            for b, s in mine
        ],
    }


def book_slot(db: Session, student: Student, slot_id: str, now: Optional[datetime.datetime] = None) -> InterviewBooking:
    now = now or datetime.datetime.now()
    slot = db.execute(select(InterviewSlot).filter_by(id=slot_id, college_id=student.college_id)).scalar_one_or_none()
    if not slot or slot.trainer_id not in student_trainer_ids(db, student):
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.starts_at <= now or slot.status == "cancelled":
        raise HTTPException(status_code=409, detail="This slot is no longer available")
    same_type = db.execute(
        select(func.count(InterviewBooking.id)).join(InterviewSlot, InterviewSlot.id == InterviewBooking.slot_id)
        .where(InterviewBooking.student_id == student.id, InterviewSlot.round_type == slot.round_type, InterviewSlot.starts_at > now)
    ).scalar_one()
    if same_type:
        raise HTTPException(status_code=409, detail="You already have an upcoming round of this type")
    rounds = db.execute(select(func.count(Interview.id)).where(Interview.student_id == student.id, Interview.status != "cancelled")).scalar_one()
    interview = Interview(id=f"iv_{uuid.uuid4().hex[:14]}", college_id=student.college_id, student_id=student.id, trainer_id=slot.trainer_id,
                          slot_id=slot.id, round_number=rounds + 1, round_type=slot.round_type, scheduled_at=slot.starts_at,
                          duration_min=slot.duration_min, status="scheduled")
    booking = InterviewBooking(id=f"bk_{uuid.uuid4().hex[:14]}", college_id=student.college_id, slot_id=slot.id,
                               student_id=student.id, interview_id=interview.id)
    try:
        db.add(booking)
        db.flush()   # the UNIQUE(slot_id) constraint decides races
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Someone has just booked this slot")
    db.add(interview)
    slot.status = "booked"
    return booking


def cancel_booking(db: Session, student: Student, booking_id: str, now: Optional[datetime.datetime] = None) -> None:
    now = now or datetime.datetime.now()
    b = db.execute(select(InterviewBooking).filter_by(id=booking_id, student_id=student.id)).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    slot = db.execute(select(InterviewSlot).filter_by(id=b.slot_id)).scalar_one()
    if slot.starts_at - now <= datetime.timedelta(hours=CANCEL_CUTOFF_HOURS):
        raise HTTPException(status_code=409, detail=f"Bookings can be cancelled up to {CANCEL_CUTOFF_HOURS} hours before the start")
    if b.interview_id:
        iv = db.execute(select(Interview).filter_by(id=b.interview_id)).scalar_one_or_none()
        if iv:
            iv.status = "cancelled"
    slot.status = "open"
    db.delete(b)


def recording_url(interview: Interview, minutes: int = 15) -> str:
    return sign_url(interview.recording_key, datetime.datetime.now() + datetime.timedelta(minutes=minutes))
