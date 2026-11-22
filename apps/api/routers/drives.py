"""Screen 38 · Mock drives (college). L29: a "drive" event on 42 creates its drive here; L17: publishing
turns interview rounds into slots on 37. Spec: docs/screens/37-38-39-interviews-drives-readiness.md"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from models.schema import Batch, DriveRound, Event, MockDrive, PracticeTest, Student, Trainer
from services import drives as svc
from services.audit import record_audit
from services.interviews import ROUND_LABEL, rubric_config
from services.notifications import notify_user

router = APIRouter(prefix="/college/drives", tags=["Screen 38 · Mock drives"])
COLLEGE = require_role(["college_admin", "placement_officer"])


class DriveIn(BaseModel):
    company_pattern: str = Field(default="", max_length=255)


class RoundIn(BaseModel):
    kind: str = Field(pattern="^(test|interview)$")
    test_id: Optional[str] = None
    round_type: Optional[str] = None
    trainer_id: Optional[str] = None
    starts_at: Optional[datetime.datetime] = None
    duration_min: int = Field(default=40, ge=15, le=120)
    slot_count: int = Field(default=0, ge=0, le=60)
    cutoff: float = Field(default=0, ge=0)


def _title(e: Event, lang: str) -> str:
    return (e.title_ta if lang == "ta" and e.title_ta else e.title_en)


def _round_out(r: DriveRound, tests: dict, trainers: dict, lang: str) -> dict:
    label = (ROUND_LABEL.get(r.round_type or "technical", ROUND_LABEL["technical"])["ta" if lang == "ta" else "en"]
             if r.kind == "interview" else ("தேர்வு" if lang == "ta" else "Test"))
    return {"id": r.id, "round_no": r.round_no, "kind": r.kind, "label": label, "test_id": r.test_id, "test_title": tests.get(r.test_id),
            "round_type": r.round_type, "trainer_id": r.trainer_id, "trainer": trainers.get(r.trainer_id),
            "starts_at": r.starts_at.isoformat() if r.starts_at else None, "duration_min": r.duration_min,
            "slot_count": r.slot_count, "cutoff": r.cutoff}


def _summary(db: Session, d: MockDrive, e: Event, batches: dict, lang: str) -> dict:
    n = len(svc.rounds_of(db, d))
    return {"id": d.id, "event_id": e.id, "title": _title(e, lang), "starts_at": e.starts_at.isoformat(), "event_status": e.status,
            "batch_id": d.batch_id, "batch": batches.get(d.batch_id), "status": d.status, "rounds": n,
            "company_pattern": d.company_pattern}


@router.get("")
def list_drives(lang: str = "en", current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    rows = db.execute(select(MockDrive, Event).join(Event, Event.id == MockDrive.event_id)
                      .where(MockDrive.college_id == current_user.college_id).order_by(Event.starts_at.desc())).all()
    batches = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id)).all())
    return {"drives": [_summary(db, d, e, batches, lang) for d, e in rows]}


def _detail(db: Session, d: MockDrive, lang: str) -> dict:
    e = db.get(Event, d.event_id)
    batches = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == d.college_id)).all())
    tests = dict(db.execute(select(PracticeTest.id, PracticeTest.title).where(PracticeTest.college_id == d.college_id,
                                                                            PracticeTest.status == "published")).all())
    trainers = svc.batch_trainers(db, d.college_id, d.batch_id)
    all_trainers = svc.batch_trainers(db, d.college_id, None)
    return {**_summary(db, d, e, batches, lang),
            "round_list": [_round_out(r, tests, all_trainers, lang) for r in svc.rounds_of(db, d)],
            "options": {"tests": [{"id": k, "title": v} for k, v in tests.items()],
                        "trainers": [{"id": k, "name": v} for k, v in trainers.items()],
                        "round_types": [{"key": k, "label": v["ta" if lang == "ta" else "en"]} for k, v in ROUND_LABEL.items()],
                        "rubric_max": rubric_config(db, d.college_id).max_score}}


@router.get("/{drive_id}")
def get_drive(drive_id: str, lang: str = "en", current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    return _detail(db, svc.get_drive(db, current_user.college_id, drive_id), lang)


@router.put("/{drive_id}")
def update_drive(drive_id: str, req: DriveIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    d = svc.get_drive(db, current_user.college_id, drive_id)
    if d.status != "draft":
        raise HTTPException(status_code=409, detail="A published drive cannot be changed")
    d.company_pattern = req.company_pattern.strip()
    db.commit()
    return _detail(db, d, "en")


@router.post("/{drive_id}/rounds", status_code=201)
def add_round(drive_id: str, req: RoundIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    d = svc.get_drive(db, current_user.college_id, drive_id)
    r = svc.add_round(db, d, kind=req.kind, test_id=req.test_id, round_type=req.round_type, trainer_id=req.trainer_id,
                      starts_at=req.starts_at, duration_min=req.duration_min, slot_count=req.slot_count, cutoff=req.cutoff)
    record_audit(db, current_user, "drive.round_added", "mock_drive", d.id, {"round_no": r.round_no, "kind": r.kind})
    db.commit()
    return _detail(db, d, "en")


@router.delete("/{drive_id}/rounds/{round_id}")
def remove_round(drive_id: str, round_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    d = svc.get_drive(db, current_user.college_id, drive_id)
    svc.remove_round(db, d, round_id)
    record_audit(db, current_user, "drive.round_removed", "mock_drive", d.id, {"round_id": round_id})
    db.commit()
    return _detail(db, d, "en")


@router.post("/{drive_id}/publish")
def publish_drive(drive_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    """L17: interview rounds become slots on the trainers' 37; trainers and the batch's students are told."""
    d = svc.get_drive(db, current_user.college_id, drive_id)
    e = db.get(Event, d.event_id)
    out = svc.publish(db, d)
    for tid in out["trainer_ids"]:
        t = db.get(Trainer, tid)
        if t:
            notify_user(db, t.user_id, f"Mock drive slots: {e.title_en}", "Interview slots were added to your Mock interviews page.",
                        title_ta=f"மாதிரி முகாம் நேரங்கள்: {e.title_ta or e.title_en}",
                        body_ta="நேர்காணல் நேரங்கள் உங்கள் மாதிரி நேர்காணல் பக்கத்தில் சேர்க்கப்பட்டன.",
                        kind="info", link="/trainer/interviews", college_id=d.college_id)
    for uid in db.execute(select(Student.user_id).where(Student.college_id == d.college_id, Student.batch_id == d.batch_id)).scalars():
        notify_user(db, uid, f"Mock drive: {e.title_en}", "Book your interview slots and take the test round.",
                    title_ta=f"மாதிரி வேலைவாய்ப்பு முகாம்: {e.title_ta or e.title_en}",
                    body_ta="நேர்காணல் நேரங்களைப் பதிவு செய்து தேர்வுச் சுற்றை எழுதுங்கள்.",
                    kind="event", link="/student/interviews", college_id=d.college_id)
    record_audit(db, current_user, "drive.published", "mock_drive", d.id, {"slots": out["slots"], "trainers": len(out["trainer_ids"])})
    db.commit()
    return {**_detail(db, d, "en"), "slots_created": out["slots"]}


@router.get("/{drive_id}/results")
def drive_results(drive_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    d = svc.get_drive(db, current_user.college_id, drive_id)
    return {"drive_id": d.id, "status": d.status, **svc.results(db, d)}


@router.post("/{drive_id}/shortlist")
def publish_shortlist(drive_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    d = svc.get_drive(db, current_user.college_id, drive_id)
    if d.status != "published":
        raise HTTPException(status_code=409, detail="Publish the drive first; a shortlist is published once")
    e = db.get(Event, d.event_id)
    res = svc.results(db, d)
    picked = [s["student_id"] for s in res["students"] if s["shortlisted"]]
    for sid in picked:
        st = db.get(Student, sid)
        notify_user(db, st.user_id, f"Shortlisted: {e.title_en}", "You cleared every round of the mock drive.",
                    title_ta=f"தேர்வுப் பட்டியலில்: {e.title_ta or e.title_en}", body_ta="மாதிரி முகாமின் எல்லாச் சுற்றுகளிலும் தேறினீர்கள்.",
                    kind="info", link="/student", college_id=d.college_id)
    d.status, d.results_published_at = "results_published", datetime.datetime.utcnow()
    record_audit(db, current_user, "drive.shortlist_published", "mock_drive", d.id, {"shortlisted": len(picked), "total": res["total"]})
    db.commit()
    return {"drive_id": d.id, "status": d.status, "shortlisted": len(picked), "total": res["total"]}
