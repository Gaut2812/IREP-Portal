"""Notification centre endpoints (shared by every role, opened from the bell)."""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, TokenPayload
from models.schema import Notification
from services.notifications import unread_count

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
    limit: int = 30,
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(Notification).where(
        Notification.user_id == current_user.sub,
        Notification.college_id == current_user.college_id,
        Notification.channel == "in_app",
    )
    if kind:
        q = q.where(Notification.kind == kind)
    rows = db.execute(q.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 100)))).scalars().all()
    return {
        "items": [_serialize(n, lang) for n in rows],
        "unread": unread_count(db, current_user.sub, current_user.college_id),
    }


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
