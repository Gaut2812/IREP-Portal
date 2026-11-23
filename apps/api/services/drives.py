"""Screen 38 mock drives (docs/screens/37-38-39-interviews-drives-readiness.md).

- L29 (42 -> 38): an event of kind "drive" has exactly one MockDrive (`ensure_for_event`).
- L17 (38 -> 37): publishing a drive turns each interview round into slots on the round trainer's 37,
  marked with `drive_round_id`; students book them on 36. A test round assigns its practice test to
  the drive's batch.
- Results are scores only: the latest submitted attempt for a test round, the interview's overall
  score for an interview round. Trainer notes and feedback never leave 36/37 (5.4, L35).
"""
import datetime
import uuid
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.schema import (BatchTrainer, DriveRound, Event, Interview, InterviewSlot, MockDrive, PracticeTest, Student,
                           TestAttempt, Trainer, User)
from services.interviews import rubric_config

ROUND_KINDS = ("test", "interview")
INTERVIEW_TYPES = ("technical", "hr", "ai_coding")


def ensure_for_event(db: Session, e: Event, created_by: Optional[str] = None) -> Optional[MockDrive]:
    """L29: the drive behind a "drive" event (idempotent)."""
    if e.kind != "drive":
        return None
    d = db.execute(select(MockDrive).where(MockDrive.event_id == e.id)).scalar_one_or_none()
    if d is None:
        d = MockDrive(id=f"drv_{uuid.uuid4().hex[:14]}", college_id=e.college_id, event_id=e.id, batch_id=e.batch_id,
                      company_pattern="", status="draft", created_by=created_by)
        db.add(d)
        db.flush()
    elif d.batch_id != e.batch_id and d.status == "draft":
        d.batch_id = e.batch_id
    return d


def get_drive(db: Session, college_id: str, drive_id: str) -> MockDrive:
    d = db.execute(select(MockDrive).where(MockDrive.id == drive_id, MockDrive.college_id == college_id)).scalar_one_or_none()
    if d is None:
        raise HTTPException(status_code=404, detail="Mock drive not found")
    return d


def rounds_of(db: Session, drive: MockDrive) -> List[DriveRound]:
    return db.execute(select(DriveRound).where(DriveRound.drive_id == drive.id).order_by(DriveRound.round_no)).scalars().all()


def batch_trainers(db: Session, college_id: str, batch_id: Optional[str]) -> Dict[str, str]:
    q = select(Trainer.id, User.name).join(User, User.id == Trainer.user_id).where(Trainer.college_id == college_id)
    if batch_id:
        q = q.where(Trainer.id.in_(select(BatchTrainer.trainer_id).where(BatchTrainer.batch_id == batch_id)))
    return dict(db.execute(q.order_by(User.name)).all())


def add_round(db: Session, drive: MockDrive, *, kind: str, test_id: Optional[str], round_type: Optional[str],
              trainer_id: Optional[str], starts_at: Optional[datetime.datetime], duration_min: int, slot_count: int,
              cutoff: float) -> DriveRound:
    if drive.status != "draft":
        raise HTTPException(status_code=409, detail="Rounds can only change while the drive is a draft")
    if kind not in ROUND_KINDS:
        raise HTTPException(status_code=422, detail="A round is a test or an interview")
    if kind == "test":
        t = db.execute(select(PracticeTest).where(PracticeTest.id == test_id, PracticeTest.college_id == drive.college_id,
                                                  PracticeTest.status == "published")).scalar_one_or_none() if test_id else None
        if t is None:
            raise HTTPException(status_code=404, detail="Published test not found")
        if not 0 <= cutoff <= 100:
            raise HTTPException(status_code=422, detail="A test cut-off is a percentage from 0 to 100")
        round_type, trainer_id, slot_count = None, None, 0
    else:
        if round_type not in INTERVIEW_TYPES:
            raise HTTPException(status_code=422, detail="round_type must be technical, hr or ai_coding")
        if trainer_id not in batch_trainers(db, drive.college_id, drive.batch_id):
            raise HTTPException(status_code=404, detail="Trainer not found for this drive's batch")
        if starts_at is None or starts_at <= datetime.datetime.now():
            raise HTTPException(status_code=422, detail="An interview round starts in the future")
        if not 1 <= slot_count <= 60:
            raise HTTPException(status_code=422, detail="An interview round has 1 to 60 slots")
        cfg = rubric_config(db, drive.college_id)
        if not 0 <= cutoff <= cfg.max_score:
            raise HTTPException(status_code=422, detail=f"An interview cut-off is a score from 0 to {cfg.max_score}")
        test_id = None
    n = (db.execute(select(func.max(DriveRound.round_no)).where(DriveRound.drive_id == drive.id)).scalar_one() or 0) + 1
    r = DriveRound(id=f"drr_{uuid.uuid4().hex[:14]}", college_id=drive.college_id, drive_id=drive.id, round_no=n, kind=kind,
                   test_id=test_id, round_type=round_type, trainer_id=trainer_id, starts_at=starts_at,
                   duration_min=duration_min, slot_count=slot_count, cutoff=cutoff)
    db.add(r)
    return r


def remove_round(db: Session, drive: MockDrive, round_id: str) -> None:
    if drive.status != "draft":
        raise HTTPException(status_code=409, detail="Rounds can only change while the drive is a draft")
    r = db.execute(select(DriveRound).where(DriveRound.id == round_id, DriveRound.drive_id == drive.id)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Round not found")
    db.delete(r)
    db.flush()
    for i, other in enumerate(rounds_of(db, drive), start=1):        # keep 1..n
        other.round_no = i


def publish(db: Session, drive: MockDrive) -> dict:
    """L17: interview rounds become slots on 37; test rounds assign the test to the batch."""
    if drive.status != "draft":
        raise HTTPException(status_code=409, detail="This drive is already published")
    rounds = rounds_of(db, drive)
    if not rounds:
        raise HTTPException(status_code=422, detail="Add at least one round before publishing")
    if not drive.batch_id:
        raise HTTPException(status_code=422, detail="Choose the drive's batch on the event (42) before publishing")
    slots = 0
    trainers = set()
    for r in rounds:
        if r.kind == "interview":
            for i in range(r.slot_count):
                db.add(InterviewSlot(id=f"slot_{uuid.uuid4().hex[:12]}", college_id=drive.college_id, trainer_id=r.trainer_id,
                                     batch_id=drive.batch_id, round_type=r.round_type,
                                     starts_at=r.starts_at + datetime.timedelta(minutes=i * r.duration_min),
                                     duration_min=r.duration_min, status="open", drive_round_id=r.id))
                slots += 1
            trainers.add(r.trainer_id)
        else:
            t = db.get(PracticeTest, r.test_id)
            if t is not None and drive.batch_id not in (t.batch_ids or []):
                t.batch_ids = list(t.batch_ids or []) + [drive.batch_id]
    drive.status, drive.published_at = "published", datetime.datetime.utcnow()
    return {"slots": slots, "trainer_ids": sorted(trainers)}


def results(db: Session, drive: MockDrive) -> dict:
    """Per student: score per round, cut-off cleared, shortlisted (all rounds cleared). Scores only."""
    rounds = rounds_of(db, drive)
    students = db.execute(select(Student.id, User.name, Student.register_no).join(User, User.id == Student.user_id)
                          .where(Student.college_id == drive.college_id, Student.batch_id == drive.batch_id)
                          .order_by(Student.register_no)).all() if drive.batch_id else []
    ids = [s for s, _, _ in students]
    by_round: Dict[str, Dict[str, float]] = {}
    for r in rounds:
        if r.kind == "test":
            rows = db.execute(select(TestAttempt.student_id, TestAttempt.score, TestAttempt.total_questions, TestAttempt.submitted_at)
                              .where(TestAttempt.test_id == r.test_id, TestAttempt.student_id.in_(ids or ["_"]),
                                     TestAttempt.status == "submitted").order_by(TestAttempt.submitted_at)).all()
            by_round[r.id] = {sid: round(100 * (score or 0) / max(1, total), 1) for sid, score, total, _ in rows}   # latest wins
        else:
            rows = db.execute(select(Interview.student_id, Interview.overall_score)
                              .join(InterviewSlot, InterviewSlot.id == Interview.slot_id)
                              .where(InterviewSlot.drive_round_id == r.id, Interview.submitted_at.is_not(None))).all()
            by_round[r.id] = {sid: score for sid, score in rows if score is not None}
    out, shortlisted = [], 0
    for sid, name, reg in students:
        cells, cleared_all = [], bool(rounds)
        for r in rounds:
            v = by_round[r.id].get(sid)
            cleared = v is not None and v >= r.cutoff
            cleared_all = cleared_all and cleared
            cells.append({"round_id": r.id, "score": v, "cleared": cleared})
        shortlisted += cleared_all
        out.append({"student_id": sid, "name": name, "register_no": reg, "rounds": cells, "shortlisted": cleared_all})
    funnel = [{"round_no": r.round_no, "attempted": len(by_round[r.id]), "cleared": sum(1 for v in by_round[r.id].values() if v >= r.cutoff)}
              for r in rounds]
    return {"students": out, "shortlisted": shortlisted, "total": len(students), "funnel": funnel}
