"""Consent records (screen 48; DPDP). Append-only: the latest row per
(student, purpose) is the current state. Parent-facing data for a student
needs a granted `parent_data_processing` consent (docs/screens/48)."""
import datetime
import uuid
from typing import Dict, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.schema import ConsentRecord

PURPOSES = ("parent_data_processing", "public_portfolio", "ai_hints", "recordings", "sms_alerts")
METHODS = ("otp_parent", "paper_form_upload", "in_app")


def current(db: Session, student_id: str, purpose: str) -> Optional[str]:
    """'granted', 'withdrawn' or None (never asked)."""
    row = db.execute(select(ConsentRecord.status).where(
        ConsentRecord.subject_student_id == student_id, ConsentRecord.purpose == purpose)
        .order_by(ConsentRecord.recorded_at.desc(), ConsentRecord.id.desc()).limit(1)).scalar_one_or_none()
    return row


def is_granted(db: Session, student_id: str, purpose: str) -> bool:
    return current(db, student_id, purpose) == "granted"


def current_for(db: Session, college_id: str, student_ids: Iterable[str]) -> Dict[str, Dict[str, str]]:
    """{student_id: {purpose: status}} for many students in one query."""
    ids = list(student_ids)
    if not ids:
        return {}
    latest = (select(ConsentRecord.subject_student_id, ConsentRecord.purpose, func.max(ConsentRecord.recorded_at).label("at"))
              .where(ConsentRecord.college_id == college_id, ConsentRecord.subject_student_id.in_(ids))
              .group_by(ConsentRecord.subject_student_id, ConsentRecord.purpose).subquery())
    rows = db.execute(select(ConsentRecord.subject_student_id, ConsentRecord.purpose, ConsentRecord.status).join(
        latest, (ConsentRecord.subject_student_id == latest.c.subject_student_id)
        & (ConsentRecord.purpose == latest.c.purpose) & (ConsentRecord.recorded_at == latest.c.at))).all()
    out: Dict[str, Dict[str, str]] = {}
    for sid, purpose, status in rows:
        out.setdefault(sid, {})[purpose] = status
    return out


def record(db: Session, *, college_id: str, student_id: str, granted_by: str, purpose: str, status: str, method: str,
           evidence_ref: Optional[str] = None, at: Optional[datetime.datetime] = None) -> ConsentRecord:
    if purpose not in PURPOSES or status not in ("granted", "withdrawn") or method not in METHODS:
        raise ValueError("invalid consent record")
    row = ConsentRecord(id=f"cns_{uuid.uuid4().hex[:20]}", college_id=college_id, subject_student_id=student_id,
                        granted_by_user_id=granted_by, purpose=purpose, status=status, method=method,
                        evidence_ref=evidence_ref, recorded_at=at or datetime.datetime.utcnow())
    db.add(row)
    return row
