"""Screen 34 Discussion Groups (moderated student chat) + the 1-1 thread policy."""
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from core.security import require_role, TokenPayload, decode_access_token, normalize_role
from models.schema import (
    DiscussionGroup, GroupMessage, GroupMember, MessageReaction, MessageReport, User, College, TrainerDirectThread,
)
from services.chat_policy import can_message
from services.moderation import contains_blocked
from services.notifications import notify_user
from services.realtime import hub, publish_sync
from services.audit import record_audit

router = APIRouter(tags=["Discussion Groups"])
GROUP_ROLES = ["student", "trainer"]
HELPER_WINDOW_DAYS = 30
ONLINE_WINDOW_MIN = 10


class MessageIn(BaseModel):
    message_text: str = Field(min_length=1, max_length=4000)
    code_snippet: Optional[str] = Field(default=None, max_length=8000)


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class ThreadIn(BaseModel):
    to_user_id: str


def _membership(db: Session, group_id: str, user: TokenPayload) -> tuple:
    g = db.execute(select(DiscussionGroup).filter_by(id=group_id, college_id=user.college_id)).scalar_one_or_none()
    m = db.execute(select(GroupMember).filter_by(group_id=group_id, user_id=user.sub)).scalar_one_or_none() if g else None
    if not g or not m:
        raise HTTPException(status_code=404, detail="Group not found")
    return g, m


def _local(dt: datetime.datetime) -> datetime.datetime:
    """created_at is stored in UTC; show campus-local time."""
    return dt + (datetime.datetime.now() - datetime.datetime.utcnow())


def _serialize(db: Session, msgs, user: TokenPayload) -> list:
    ids = [m.id for m in msgs] or ["_"]
    counts = dict(db.execute(select(MessageReaction.message_id, func.count(MessageReaction.id)).where(MessageReaction.message_id.in_(ids)).group_by(MessageReaction.message_id)).all())
    mine = set(db.execute(select(MessageReaction.message_id).where(MessageReaction.message_id.in_(ids), MessageReaction.user_id == user.sub)).scalars().all())
    reported = set(db.execute(select(MessageReport.message_id).where(MessageReport.message_id.in_(ids), MessageReport.reporter_user_id == user.sub)).scalars().all())
    out = []
    for m in msgs:
        out.append({
            "id": m.id, "sender_name": m.sender_name, "sender_role": m.sender_role, "sender_initials": m.sender_initials,
            "is_mine": m.sender_user_id == user.sub,
            "message_text": "This message was removed by a moderator." if m.is_removed else m.message_text,
            "code_snippet": None if m.is_removed else m.code_snippet, "is_removed": m.is_removed,
            "is_marked_as_answer": m.is_marked_as_answer, "reactions": counts.get(m.id, 0) + (m.reactions_count or 0),
            "my_reaction": m.id in mine, "reported_by_me": m.id in reported,
            "time": _local(m.created_at).strftime("%I:%M %p").lstrip("0"), "date": _local(m.created_at).strftime("%b %d"),
            "created_at": m.created_at.isoformat(),
        })
    return out


@router.get("/student/discussions/groups")
def list_groups(current_user: TokenPayload = Depends(require_role(GROUP_ROLES)), db: Session = Depends(get_db)):
    rows = db.execute(
        select(DiscussionGroup, GroupMember).join(GroupMember, GroupMember.group_id == DiscussionGroup.id)
        .where(GroupMember.user_id == current_user.sub, DiscussionGroup.college_id == current_user.college_id)
    ).all()
    order = ["batch", "track_doubts", "daily_dsa", "team", "announcements", "gd"]
    out = []
    for g, m in sorted(rows, key=lambda r: (order.index(r[0].kind) if r[0].kind in order else 99, r[0].name)):
        last = db.execute(select(GroupMessage).where(GroupMessage.group_id == g.id, GroupMessage.is_removed.is_(False)).order_by(GroupMessage.created_at.desc())).scalars().first()
        unread_q = select(func.count(GroupMessage.id)).where(GroupMessage.group_id == g.id, GroupMessage.sender_user_id != current_user.sub)
        if m.last_read_at:
            unread_q = unread_q.where(GroupMessage.created_at > m.last_read_at)
        out.append({
            "id": g.id, "name": g.name, "kind": g.kind, "icon": g.icon, "is_locked": g.is_locked_announcement,
            "unread": db.execute(unread_q).scalar_one(),
            "preview": (f"{last.sender_name.split(' ')[0]}: {last.message_text[:60]}" if last else ""),
            "my_role": m.role,
        })
    return {"groups": out}


@router.get("/groups/{group_id}/messages")
def get_messages(group_id: str, after: Optional[str] = None, current_user: TokenPayload = Depends(require_role(GROUP_ROLES)), db: Session = Depends(get_db)):
    g, m = _membership(db, group_id, current_user)
    q = select(GroupMessage).where(GroupMessage.group_id == g.id)
    if after:
        q = q.where(GroupMessage.created_at > datetime.datetime.fromisoformat(after))
    msgs = db.execute(q.order_by(GroupMessage.created_at.desc()).limit(60)).scalars().all()[::-1]
    now = datetime.datetime.utcnow()
    m.last_read_at = now
    m.last_seen_at = now
    db.commit()
    mods = db.execute(select(User.name).join(GroupMember, GroupMember.user_id == User.id).where(GroupMember.group_id == g.id, GroupMember.role == "moderator")).scalars().all()
    muted = bool(m.muted_until and m.muted_until > now)
    can_post = not muted and (not g.is_locked_announcement or m.role == "moderator")
    return {
        "group": {"id": g.id, "name": g.name, "kind": g.kind, "icon": g.icon, "is_locked": g.is_locked_announcement, "pinned_note": g.pinned_note,
                  "moderators": [n.replace("Arun Kumar", "Arun K.").replace("Meena S", "Meena S.") for n in mods]},
        "me": {"role": m.role, "can_post": can_post, "muted_until": m.muted_until.isoformat() if muted else None},
        "messages": _serialize(db, msgs, current_user),
    }


@router.get("/groups/{group_id}/info")
def group_info(group_id: str, current_user: TokenPayload = Depends(require_role(GROUP_ROLES)), db: Session = Depends(get_db)):
    g, _ = _membership(db, group_id, current_user)
    members = db.execute(select(GroupMember.role, func.count(GroupMember.id)).where(GroupMember.group_id == g.id).group_by(GroupMember.role)).all()
    by_role = dict(members)
    now = datetime.datetime.utcnow()
    online = db.execute(select(func.count(GroupMember.id)).where(GroupMember.group_id == g.id, GroupMember.last_seen_at >= now - datetime.timedelta(minutes=ONLINE_WINDOW_MIN))).scalar_one()
    answered = db.execute(select(func.count(GroupMessage.id)).where(GroupMessage.group_id == g.id, GroupMessage.is_marked_as_answer.is_(True))).scalar_one()
    # average trainer reply: time from a student message to the next trainer message in the group
    msgs = db.execute(select(GroupMessage.sender_role, GroupMessage.created_at).where(GroupMessage.group_id == g.id).order_by(GroupMessage.created_at)).all()
    waits, pending = [], None
    for role, at in msgs:
        if role == "Student" and pending is None:
            pending = at
        elif role == "Trainer" and pending is not None:
            waits.append((at - pending).total_seconds() / 60)
            pending = None
    since = now - datetime.timedelta(days=HELPER_WINDOW_DAYS)
    # a helper answer = a student reply that is not itself a question, in the last 30 days
    helpers = db.execute(
        select(GroupMessage.sender_name, func.count(GroupMessage.id)).where(
            GroupMessage.group_id == g.id, GroupMessage.sender_role == "Student", GroupMessage.created_at >= since,
            GroupMessage.is_removed.is_(False), GroupMessage.message_text.notlike("%?%"))
        .group_by(GroupMessage.sender_name).order_by(func.count(GroupMessage.id).desc()).limit(3)
    ).all()
    return {
        "students": by_role.get("member", 0), "moderators": by_role.get("moderator", 0), "online": online,
        "doubts_answered": answered, "avg_trainer_reply_min": round(sum(waits) / len(waits)) if waits else None,
        "top_helpers": [{"name": n, "answers": c, "medal": ["gold", "silver", "bronze"][i]} for i, (n, c) in enumerate(helpers)],
    }


@router.post("/groups/{group_id}/messages")
def post_message(group_id: str, req: MessageIn, current_user: TokenPayload = Depends(require_role(GROUP_ROLES)), db: Session = Depends(get_db)):
    g, m = _membership(db, group_id, current_user)
    now = datetime.datetime.utcnow()
    if g.is_locked_announcement and m.role != "moderator":
        raise HTTPException(status_code=403, detail="This is an announcement-only group. Students can read and react.")
    if m.muted_until and m.muted_until > now:
        raise HTTPException(status_code=403, detail="A moderator has muted you in this group for now.")
    if contains_blocked(req.message_text) or (req.code_snippet and contains_blocked(req.code_snippet)):
        raise HTTPException(status_code=422, detail="Please rephrase: the message breaks the group rules (no insults, no graded-test answers).")
    user = db.execute(select(User).filter_by(id=current_user.sub)).scalar_one()
    role = "Trainer" if normalize_role(current_user.role) == "trainer" else "Student"
    msg = GroupMessage(id=f"msg_{uuid.uuid4().hex[:16]}", college_id=g.college_id, group_id=g.id, sender_user_id=user.id,
                       sender_name=user.name, sender_role=role, sender_initials=user.avatar_initials, message_text=req.message_text.strip(),
                       code_snippet=(req.code_snippet or "").rstrip() or None, timestamp_str=datetime.datetime.now().strftime("%I:%M %p").lstrip("0"),
                       reactions_count=0)
    db.add(msg)
    m.last_read_at = m.last_seen_at = now
    db.commit()
    publish_sync(f"group:{g.id}", {"type": "message", "group_id": g.id, "message_id": msg.id})
    return {"success": True, "message_id": msg.id}


def _message_for(db: Session, message_id: str, user: TokenPayload):
    msg = db.execute(select(GroupMessage).filter_by(id=message_id, college_id=user.college_id)).scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    g, m = _membership(db, msg.group_id, user)
    return msg, g, m


@router.post("/messages/{message_id}/react")
def react(message_id: str, current_user: TokenPayload = Depends(require_role(GROUP_ROLES)), db: Session = Depends(get_db)):
    msg, g, _ = _message_for(db, message_id, current_user)
    existing = db.execute(select(MessageReaction).filter_by(message_id=msg.id, user_id=current_user.sub)).scalar_one_or_none()
    if existing:
        db.delete(existing)
        mine = False
    else:
        db.add(MessageReaction(id=f"rx_{uuid.uuid4().hex[:16]}", college_id=g.college_id, message_id=msg.id, user_id=current_user.sub))
        mine = True
    db.commit()
    total = db.execute(select(func.count(MessageReaction.id)).filter_by(message_id=msg.id)).scalar_one() + (msg.reactions_count or 0)
    publish_sync(f"group:{g.id}", {"type": "reaction", "group_id": g.id})
    return {"success": True, "my_reaction": mine, "reactions": total}


@router.post("/messages/{message_id}/mark-answer")
def mark_answer(message_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    msg, g, m = _message_for(db, message_id, current_user)
    if m.role != "moderator":
        raise HTTPException(status_code=403, detail="Only the group's moderators can mark answers")
    msg.is_marked_as_answer = not msg.is_marked_as_answer
    db.commit()
    publish_sync(f"group:{g.id}", {"type": "answer", "group_id": g.id})
    return {"success": True, "is_marked_as_answer": msg.is_marked_as_answer}


@router.post("/messages/{message_id}/report")
def report(message_id: str, req: ReportIn, current_user: TokenPayload = Depends(require_role(GROUP_ROLES)), db: Session = Depends(get_db)):
    msg, g, _ = _message_for(db, message_id, current_user)
    if msg.sender_user_id == current_user.sub:
        raise HTTPException(status_code=422, detail="You cannot report your own message")
    if db.execute(select(MessageReport).filter_by(message_id=msg.id, reporter_user_id=current_user.sub)).scalar_one_or_none():
        return {"success": True, "already": True}
    rep = MessageReport(id=f"rep_{uuid.uuid4().hex[:14]}", college_id=g.college_id, message_id=msg.id, group_id=g.id,
                        reporter_user_id=current_user.sub, reason=req.reason.strip(), status="open")
    db.add(rep)
    for uid in db.execute(select(GroupMember.user_id).filter_by(group_id=g.id, role="moderator")).scalars().all():
        notify_user(db, uid, f"Message reported in {g.name}", req.reason, kind="approval", link="/trainer/messages", college_id=g.college_id)
    record_audit(db, current_user, "group.report", "group_message", msg.id, {"reason": req.reason})
    db.commit()
    return {"success": True, "report_id": rep.id}


@router.post("/threads")
def create_thread(req: ThreadIn, current_user: TokenPayload = Depends(require_role(["student", "trainer", "parent", "college_admin"])), db: Session = Depends(get_db)):
    """One-to-one threads obey the messaging policy at the API, not just in the UI."""
    other = db.execute(select(User).filter_by(id=req.to_user_id, college_id=current_user.college_id)).scalar_one_or_none()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")
    ok, why = can_message(current_user.role, other.role)
    if not ok:
        record_audit(db, current_user, "thread.blocked", "user", other.id, {"to_role": other.role})
        db.commit()
        raise HTTPException(status_code=403, detail=why)
    trainer_id, contact = (current_user.sub, other) if normalize_role(current_user.role) == "trainer" else (other.id, db.execute(select(User).filter_by(id=current_user.sub)).scalar_one())
    existing = db.execute(select(TrainerDirectThread).filter_by(trainer_user_id=trainer_id, contact_user_id=contact.id)).scalars().first()
    if existing:
        return {"success": True, "thread_id": existing.id}
    t = TrainerDirectThread(id=f"th_{uuid.uuid4().hex[:12]}", college_id=current_user.college_id, trainer_user_id=trainer_id,
                            contact_user_id=contact.id, contact_name=contact.name,
                            contact_category="Parents" if contact.role == "parent" else "College",
                            contact_role_chip="Parent" if contact.role == "parent" else "College", avatar_initials=contact.avatar_initials,
                            pref_language="Prefers Tamil" if contact.language_pref == "ta" else "Prefers English",
                            last_message_preview="", last_message_time="")
    db.add(t)
    db.commit()
    return {"success": True, "thread_id": t.id}


def purge_expired_messages(db: Session, college_id: str, now: Optional[datetime.datetime] = None) -> int:
    """Retention policy (college setting): delete group messages older than the limit."""
    now = now or datetime.datetime.utcnow()
    college = db.execute(select(College).filter_by(id=college_id)).scalar_one_or_none()
    days = college.chat_retention_days if college and college.chat_retention_days else 365
    cutoff = now - datetime.timedelta(days=days)
    old = db.execute(select(GroupMessage.id).where(GroupMessage.college_id == college_id, GroupMessage.created_at < cutoff)).scalars().all()
    if old:
        db.execute(delete(MessageReaction).where(MessageReaction.message_id.in_(old)))
        db.execute(delete(MessageReport).where(MessageReport.message_id.in_(old)))
        db.execute(delete(GroupMessage).where(GroupMessage.id.in_(old)))
    return len(old)


@router.post("/admin/jobs/chat-retention")
def run_retention(current_user: TokenPayload = Depends(require_role(["college_admin", "super_admin"])), db: Session = Depends(get_db)):
    n = purge_expired_messages(db, current_user.college_id)
    record_audit(db, current_user, "job.chat_retention", "college", current_user.college_id, {"deleted": n})
    db.commit()
    return {"success": True, "deleted": n}


@router.websocket("/ws/groups/{group_id}")
async def group_socket(websocket: WebSocket, group_id: str, token: Optional[str] = None):
    payload = decode_access_token(token) if token else None
    if not payload:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        _membership(db, group_id, payload)
    except HTTPException:
        await websocket.close(code=4404)
        return
    finally:
        db.close()
    channel = f"group:{group_id}"
    await hub.subscribe(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(channel, websocket)
