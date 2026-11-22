"""IREP staff read student or parent data only inside an active support session (docs/PERMISSIONS.md).

A super admin opens the session (routers/super_admin.py) for one staff member, one college, a reason
and a time limit. While it is open, that staff member may read that college's student-level records;
every read is written to the audit log as `support.read` with the session id. Without a session the
answer is 403. Student and parent names in staff-wide lists (data-request queue, audit trail) are
hidden for colleges without a session; ids and workflow stay usable.

Support-desk tickets (screen 49) are not covered: the requester sent them to IREP themselves.
"""
import datetime
from typing import Iterable, Optional, Set

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import TokenPayload, is_staff
from models.schema import SupportSession
from services.audit import record_audit

NEEDS_SESSION = ("Open a support session for this college first (Super admin > Support sessions): "
                 "IREP staff see student and parent data only inside a logged, time-limited session.")


def active_session(db: Session, user: TokenPayload, college_id: str) -> Optional[SupportSession]:
    now = datetime.datetime.utcnow()
    return db.execute(select(SupportSession).where(
        SupportSession.staff_user_id == user.sub, SupportSession.college_id == college_id,
        SupportSession.ended_at.is_(None), SupportSession.expires_at > now,
    ).order_by(SupportSession.expires_at.desc())).scalars().first()


def colleges_with_session(db: Session, user: TokenPayload, college_ids: Iterable[str]) -> Set[str]:
    ids = {c for c in college_ids if c}
    if not ids:
        return set()
    now = datetime.datetime.utcnow()
    return set(db.execute(select(SupportSession.college_id).where(
        SupportSession.staff_user_id == user.sub, SupportSession.college_id.in_(ids),
        SupportSession.ended_at.is_(None), SupportSession.expires_at > now)).scalars())


def require_session(db: Session, user: TokenPayload, college_id: str, view: str,
                    entity_type: str = "college", entity_id: Optional[str] = None) -> Optional[SupportSession]:
    """403 unless the staff caller has an active session for `college_id`; audits the read.
    Other roles pass through (their own routes enforce tenancy)."""
    if not is_staff(user.role):
        return None
    s = active_session(db, user, college_id)
    if s is None:
        record_audit(db, user, "support.read_denied", entity_type, entity_id or college_id, {"view": view}, college_id=college_id)
        db.commit()
        raise HTTPException(status_code=403, detail=NEEDS_SESSION)
    record_audit(db, user, "support.read", entity_type, entity_id or college_id,
                 {"view": view, "support_session_id": s.id}, college_id=college_id)
    return s
