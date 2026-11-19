"""Notification centre (platform package P05).

Every notification is stored in the `notifications` table (in-app channel)
and optionally fanned out through an SMS / email adapter. The default
adapter is a fake that only records the delivery status, so the portal is
fully usable without a DLT sender or SMTP server. Select the real adapter
with NOTIFY_ADAPTER=smtp|sms once credentials exist.
"""
import datetime
import uuid
from abc import ABC, abstractmethod
from typing import Iterable, List, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.schema import Notification, User
from services.outbox import emit, handler as outbox_handler


class NotificationAdapter(ABC):
    @abstractmethod
    def deliver(self, user: User, channel: str, title: str, body: Optional[str]) -> str:
        """Return a delivery status string."""


class FakeNotificationAdapter(NotificationAdapter):
    """Records deliveries in memory; never contacts an external gateway."""
    sent: List[dict] = []

    def deliver(self, user: User, channel: str, title: str, body: Optional[str]) -> str:
        FakeNotificationAdapter.sent.append({
            "user_id": user.id, "channel": channel, "title": title, "body": body,
            "at": datetime.datetime.utcnow().isoformat()
        })
        return "delivered"


def get_notification_adapter() -> NotificationAdapter:
    # Real SMS/email adapters plug in here (NOTIFY_ADAPTER=smtp|sms).
    return FakeNotificationAdapter()


def notify_user(
    db: Session,
    user_id: str,
    title_en: str,
    body_en: Optional[str] = None,
    *,
    title_ta: Optional[str] = None,
    body_ta: Optional[str] = None,
    kind: str = "info",
    link: Optional[str] = None,
    channels: Iterable[str] = ("in_app",),
    college_id: Optional[str] = None,
) -> List[Notification]:
    """Create one notification row per channel for a user and return them.

    The in-app row is the delivery. SMS/email rows start as ``queued`` and are
    sent by the outbox worker after the caller's transaction commits.
    """
    user = db.execute(select(User).filter_by(id=user_id)).scalar_one_or_none()
    if not user:
        return []
    created: List[Notification] = []
    for channel in channels:
        status = "delivered" if channel == "in_app" else "queued"
        n = Notification(
            id=f"ntf_{uuid.uuid4().hex[:20]}",
            college_id=college_id or user.college_id,
            user_id=user.id,
            kind=kind,
            title_en=title_en,
            title_ta=title_ta,
            body_en=body_en,
            body_ta=body_ta,
            link=link,
            channel=channel,
            delivery_status=status,
        )
        db.add(n)
        created.append(n)
        if channel != "in_app":
            emit(db, "notification.deliver", {"notification_id": n.id},
                 college_id=n.college_id, entity_type="notification", entity_id=n.id)
    return created


@outbox_handler("notification.deliver")
def _deliver_queued_notification(db: Session, event) -> None:
    """Send one queued SMS/email. Idempotent: an already-sent row is skipped."""
    n = db.get(Notification, event.payload["notification_id"])
    if n is None or n.delivery_status != "queued":
        return
    user = db.get(User, n.user_id)
    if user is None:
        n.delivery_status = "failed"
        return
    # raises on gateway errors -> the outbox retries with backoff
    n.delivery_status = get_notification_adapter().deliver(user, n.channel, n.title_en, n.body_en)


def notify_users(db: Session, user_ids: Iterable[str], title_en: str, body_en: Optional[str] = None, **kwargs) -> int:
    count = 0
    for uid in user_ids:
        count += len(notify_user(db, uid, title_en, body_en, **kwargs))
    return count


def unread_count(db: Session, user_id: str, college_id: str) -> int:
    return db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.college_id == college_id,
            Notification.channel == "in_app",
            Notification.read_at.is_(None),
        )
    ).scalar_one()
