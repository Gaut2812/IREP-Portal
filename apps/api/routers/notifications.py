"""Notification centre endpoints (shared by every role, opened from the bell)."""
import datetime
from typing import Optional

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import distinct, select, update
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, TokenPayload
from models.schema import Notification, NotificationPreference, User
from services.audit import record_audit
from services.notifications import get_preferences, unread_count

router = APIRouter(prefix="/notifications", tags=["Notification Centre"])


def _serialize(n: Notification, lang: str) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": (n.title_ta if lang == "ta" and n.title_ta else n.title_en),
        "body": (n.body_ta if lang == "ta" and n.body_ta else n.body_en),
        "link": n.link,
        "channel": n.channel,
        "delivery_status": n.delivery_status,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "read": n.read_at is not None,
    }


@router.get("/unread-count")
def get_unread_count(current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"unread": unread_count(db, current_user.sub, current_user.college_id)}


@router.get("")
def list_notifications(
    lang: str = "en",
    kind: Optional[str] = None,
    unread_only: bool = False,
    before: Optional[datetime.datetime] = Query(None, description="cursor: created_at of the last item seen"),
    limit: int = 30,
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Screen 44 list: newest first, filter by kind or unread, paged with a created_at cursor."""
    mine = (Notification.user_id == current_user.sub, Notification.college_id == current_user.college_id, Notification.channel == "in_app")
    q = select(Notification).where(*mine)
    if kind:
        q = q.where(Notification.kind == kind)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    if before:
        q = q.where(Notification.created_at < before)
    size = max(1, min(limit, 100))
    rows = db.execute(q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(size + 1)).scalars().all()
    kinds = sorted(k for k in db.execute(select(distinct(Notification.kind)).where(*mine)).scalars() if k)
    return {
        "items": [_serialize(n, lang) for n in rows[:size]],
        "unread": unread_count(db, current_user.sub, current_user.college_id),
        "kinds": kinds,
        "next_before": rows[size - 1].created_at.isoformat() if len(rows) > size else None,
    }


class PreferencesIn(BaseModel):
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    quiet_start_hour: Optional[int] = Field(default=None, ge=0, le=23)
    quiet_end_hour: Optional[int] = Field(default=None, ge=0, le=23)
    language: str = Field(pattern="^(en|ta)$")


def _prefs_out(p: Optional[NotificationPreference], u: Optional[User]) -> dict:
    return {
        "in_app": True,                                   # always on: the centre itself
        "email_enabled": p.email_enabled if p else True,
        "sms_enabled": p.sms_enabled if p else True,
        "push_enabled": p.push_enabled if p else False,
        "quiet_start_hour": p.quiet_start_hour if p else None,
        "quiet_end_hour": p.quiet_end_hour if p else None,
        "language": (u.language_pref if u else None) or "en",
    }


@router.get("/preferences")
def get_preferences_endpoint(current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    return _prefs_out(get_preferences(db, current_user.sub), db.get(User, current_user.sub))


@router.put("/preferences")
def set_preferences(req: PreferencesIn, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    if (req.quiet_start_hour is None) != (req.quiet_end_hour is None):
        raise HTTPException(status_code=422, detail="Set both quiet-hours start and end, or neither")
    u = db.execute(select(User).where(User.id == current_user.sub, User.college_id == current_user.college_id)).scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    p = get_preferences(db, u.id)
    if p is None:
        p = NotificationPreference(id=f"np_{uuid.uuid4().hex[:16]}", college_id=u.college_id, user_id=u.id)
        db.add(p)
    p.email_enabled, p.sms_enabled, p.push_enabled = req.email_enabled, req.sms_enabled, req.push_enabled
    p.quiet_start_hour, p.quiet_end_hour = req.quiet_start_hour, req.quiet_end_hour
    u.language_pref = req.language
    record_audit(db, current_user, "notifications.preferences_changed", "user", u.id,
                 {"email": req.email_enabled, "sms": req.sms_enabled, "push": req.push_enabled,
                  "quiet": [req.quiet_start_hour, req.quiet_end_hour], "language": req.language})
    db.commit()
    return _prefs_out(p, u)


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.execute(
        select(Notification).filter_by(id=notification_id, user_id=current_user.sub, college_id=current_user.college_id)
    ).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read_at = datetime.datetime.utcnow()
    db.commit()
    return {"success": True}


@router.post("/read-all")
def mark_all_read(current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.sub,
            Notification.college_id == current_user.college_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.datetime.utcnow())
    )
    db.commit()
    return {"success": True}
