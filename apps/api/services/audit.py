"""Append-only audit log writer (platform package P04).

Call `record_audit(db, user, action, ...)` inside the same transaction as the
sensitive action so the trail and the change commit together.
"""
import datetime
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from core.security import TokenPayload
from models.schema import AuditLog
from services.outbox import emit


def record_audit(
    db: Session,
    user: Optional[TokenPayload],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    detail: Optional[dict] = None,
    college_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        id=f"aud_{uuid.uuid4().hex[:20]}",
        college_id=college_id or (user.college_id if user else "unknown"),
        actor_user_id=user.sub if user else None,
        actor_role=user.role if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        ip_address=ip_address,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(entry)
    # every audited state change is also an outbox event, in the same transaction
    emit(db, f"audit.{action}"[:64], {"audit_id": entry.id, "detail": detail or {}},
         college_id=entry.college_id, entity_type=entity_type, entity_id=entity_id)
    return entry
