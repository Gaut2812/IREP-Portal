"""Quotas (link L36, screen 47): one place that turns a college's active MoU into the limits
the metered screens enforce, and reports usage against them.

- 29 Virtual labs: lab minutes per student per month = MoU lab_hours_per_student x 60.
- 25 Study Buddy: AI calls per student per day = MoU ai_calls_per_day.
- 08 Live sessions: recording storage per college = MoU storage_gb.
Cloud credits stay a per-student education allowance (services/lab_orchestrator).
Without an active MoU the platform defaults apply.
"""
import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.schema import College, MouTerm, Recording, Student, UsageLedger

DEFAULT_LAB_HOURS = 20          # per student per month
DEFAULT_AI_CALLS_PER_DAY = 30
DEFAULT_STORAGE_GB = 50
WARN_AT = 0.8


def active_mou(db: Session, college_id: str) -> Optional[MouTerm]:
    return db.execute(select(MouTerm).where(MouTerm.college_id == college_id, MouTerm.status == "active")).scalars().first()


def lab_minutes_per_student(db: Session, college_id: str) -> int:
    mou = active_mou(db, college_id)
    hours = mou.lab_hours_per_student if mou and mou.lab_hours_per_student is not None else DEFAULT_LAB_HOURS
    return int(hours) * 60


def ai_calls_per_day(db: Session, college_id: str) -> int:
    mou = active_mou(db, college_id)
    return mou.ai_calls_per_day if mou and mou.ai_calls_per_day is not None else DEFAULT_AI_CALLS_PER_DAY


def storage_mb(db: Session, college_id: str) -> int:
    mou = active_mou(db, college_id)
    return (mou.storage_gb if mou and mou.storage_gb is not None else DEFAULT_STORAGE_GB) * 1024


def recordings_mb(db: Session, college_id: str) -> int:
    return int(db.execute(select(func.coalesce(func.sum(Recording.size_mb), 0)).where(
        Recording.college_id == college_id, Recording.status != "over_quota")).scalar_one())


def can_store_recording(db: Session, college_id: str, size_mb: int) -> bool:
    return recordings_mb(db, college_id) + max(0, size_mb) <= storage_mb(db, college_id)


def _level(used: float, quota: float) -> str:
    if quota <= 0:
        return "over" if used > 0 else "ok"
    return "over" if used >= quota else "warn" if used >= WARN_AT * quota else "ok"


def college_usage(db: Session, college_id: str, period: Optional[str] = None) -> dict:
    """Screen 47: this month's use against the MoU, for the whole college (aggregates only)."""
    period = period or datetime.date.today().strftime("%Y-%m")
    students = db.execute(select(func.count(Student.id)).where(Student.college_id == college_id)).scalar_one()
    used = dict(db.execute(select(UsageLedger.kind, func.coalesce(func.sum(UsageLedger.amount), 0)).where(
        UsageLedger.college_id == college_id, UsageLedger.period == period).group_by(UsageLedger.kind)).all())
    y, m = (int(x) for x in period.split("-"))
    days = ((datetime.date(y + (m == 12), m % 12 + 1, 1)) - datetime.date(y, m, 1)).days
    lab_q = lab_minutes_per_student(db, college_id) * students
    ai_q = ai_calls_per_day(db, college_id) * students * days
    st_q, st_used = storage_mb(db, college_id), recordings_mb(db, college_id)
    mou = active_mou(db, college_id)
    rows = {
        "lab_minutes": {"used": round(float(used.get("lab_minutes", 0))), "quota": lab_q},
        "ai_calls": {"used": round(float(used.get("ai_calls", 0))), "quota": ai_q},
        "recording_mb": {"used": st_used, "quota": st_q},
        "cloud_credits": {"used": round(float(used.get("cloud_credits", 0)), 1), "quota": None},
    }
    for r in rows.values():
        r["pct"] = round(100 * r["used"] / r["quota"]) if r["quota"] else None
        r["level"] = _level(r["used"], r["quota"]) if r["quota"] is not None else "ok"
    return {"period": period, "students": students, "mou": {
        "id": mou.id, "starts_on": mou.starts_on.isoformat(), "ends_on": mou.ends_on.isoformat(),
        "lab_hours_per_student": mou.lab_hours_per_student, "ai_calls_per_day": mou.ai_calls_per_day, "storage_gb": mou.storage_gb,
    } if mou else None, "usage": rows}


def all_colleges(db: Session, period: Optional[str] = None) -> list:
    from core.security import PLATFORM_TENANT
    colleges = db.execute(select(College).where(College.id != PLATFORM_TENANT).order_by(College.name)).scalars().all()
    return [{"college_id": c.id, "name": c.name, "code": c.code, **college_usage(db, c.id, period)} for c in colleges]
