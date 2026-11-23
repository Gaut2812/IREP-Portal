"""Announcements at scale (S14; screen 41, link L30). Master Plan target: a 50,000-recipient
broadcast within 15 minutes.

`start_broadcast` writes the Broadcast row, the announcement-only group post (34) and one
outbox event per CHUNK recipients, all in the caller's transaction. The dispatcher (API thread
in development, Celery workers in production, several in parallel) delivers each chunk with
`notify_user`: in-app rows at once, SMS queued for parents. A chunk is idempotent: anyone
who already has this announcement's notification is skipped, so a retry never doubles up.
"""
import datetime
import json
import uuid
from typing import Iterable, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.schema import Broadcast, DiscussionGroup, GroupMessage, Notification, OutboxEvent, ParentStudent, Student
from services.notifications import notify_user
from services.outbox import emit, handler

CHUNK = 500


def audience_users(db: Session, college_id: str, audience: str, batch_ids: Optional[List[str]]) -> dict:
    q = select(Student.id, Student.user_id).where(Student.college_id == college_id)
    if batch_ids:
        q = q.where(Student.batch_id.in_(batch_ids))
    students = db.execute(q).all()
    out = {"student": [], "parent": []}
    if audience in ("students", "both"):
        out["student"] = sorted({uid for _, uid in students if uid})
    if audience in ("parents", "both"):
        out["parent"] = sorted(set(db.execute(select(ParentStudent.parent_user_id).where(
            ParentStudent.college_id == college_id, ParentStudent.student_id.in_([sid for sid, _ in students] or ["_"]))).scalars()))
    return out


def _links(b: Broadcast) -> dict:
    return {"student": f"/student/discussions?announcement={b.id}", "parent": f"/parent?announcement={b.id}"}


def start_broadcast(db: Session, *, college_id: str, author_user_id: str, author_name: str, author_role: str, audience: str,
                    batch_ids: Optional[List[str]], title: str, body: str, title_ta: Optional[str] = None,
                    body_ta: Optional[str] = None, post_to_groups: bool = True) -> Broadcast:
    users = audience_users(db, college_id, audience, batch_ids)
    b = Broadcast(id=f"bc_{uuid.uuid4().hex[:16]}", college_id=college_id, author_user_id=author_user_id, audience=audience,
                  batch_ids=json.dumps(batch_ids or []), title=title, body=body, title_ta=title_ta, body_ta=body_ta,
                  author_role=author_role, status="sending", recipients_total=len(users["student"]) + len(users["parent"]))
    db.add(b)
    db.flush()
    chunks = 0
    for kind in ("student", "parent"):
        ids = users[kind]
        for i in range(0, len(ids), CHUNK):
            emit(db, "broadcast.chunk", {"broadcast_id": b.id, "kind": kind, "user_ids": ids[i:i + CHUNK]},
                 college_id=college_id, entity_type="broadcast", entity_id=b.id)
            chunks += 1
    b.chunks_total = chunks
    if chunks == 0:
        b.status = "done"
    if post_to_groups and audience in ("students", "both"):          # L30 -> 34: announcement-only groups
        q = select(DiscussionGroup).where(DiscussionGroup.college_id == college_id, DiscussionGroup.kind == "announcements")
        for g in db.execute(q).scalars():
            if batch_ids and g.batch_id and g.batch_id not in batch_ids:
                continue
            db.add(GroupMessage(id=f"gm_bc_{uuid.uuid4().hex[:14]}", college_id=college_id, group_id=g.id, sender_name=author_name,
                                sender_role="College" if author_role == "college" else "Trainer", sender_initials="IR",
                                sender_user_id=author_user_id, message_text=f"{title}\n{body}",
                                timestamp_str=datetime.datetime.now().strftime("%I:%M %p").lstrip("0")))
    db.flush()
    return b


def deliver_chunk(db: Session, broadcast_id: str, kind: str, user_ids: Iterable[str]) -> int:
    b = db.get(Broadcast, broadcast_id)
    if b is None:
        return 0
    link = _links(b)[kind]
    ids = list(user_ids)
    done = set(db.execute(select(Notification.user_id).where(Notification.user_id.in_(ids or ["_"]), Notification.link == link,
                                                             Notification.channel == "in_app")).scalars())
    sent = 0
    for uid in ids:
        if uid in done:
            continue
        notify_user(db, uid, b.title, b.body[:280], title_ta=b.title_ta, body_ta=(b.body_ta or "")[:280] or None, kind="broadcast",
                    link=link, channels=("in_app", "sms") if kind == "parent" else ("in_app",), college_id=b.college_id)
        sent += 1
    db.execute(update(Broadcast).where(Broadcast.id == b.id).values(delivered=Broadcast.delivered + sent, chunks_done=Broadcast.chunks_done + 1))
    db.flush()
    db.refresh(b)
    if b.chunks_done >= b.chunks_total:
        b.status = "done"
    return sent


@handler("broadcast.chunk")
def _chunk(db: Session, ev: OutboxEvent) -> None:
    p = ev.payload or {}
    deliver_chunk(db, p.get("broadcast_id"), p.get("kind", "student"), p.get("user_ids") or [])


def for_parent(db: Session, college_id: str, batch_id: Optional[str], days: int = 30, limit: int = 3) -> list:
    """L30 -> 15: recent announcements for a parent's child (college- or trainer-wide, or the child's batch)."""
    since = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    rows = db.execute(select(Broadcast).where(Broadcast.college_id == college_id, Broadcast.audience.in_(["parents", "both"]),
                                              Broadcast.created_at >= since).order_by(Broadcast.created_at.desc()).limit(20)).scalars().all()
    out = []
    for b in rows:
        ids = json.loads(b.batch_ids or "[]")
        if ids and batch_id not in ids:
            continue
        out.append(b)
        if len(out) >= limit:
            break
    return out
