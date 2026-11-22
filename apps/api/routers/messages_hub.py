"""Screen 35 Trainer Message Hub: trainer <-> parent / college threads with
Tamil-English translation, the group moderation queue, broadcasts, and the
parent-side thread view (/parent/messages)."""
import datetime
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from core.security import require_role, TokenPayload, decode_access_token, websocket_user, normalize_role
from core.tenant import get_trainer_for_user, get_trainer_batch_ids
from models.schema import (
    TrainerDirectThread, DirectMessage, User, Student, Batch, ParentStudent,
    DiscussionGroup, GroupMessage, GroupMember, MessageReport, ModerationAction, Broadcast,
)
from services.audit import record_audit
from services.chat_policy import can_message, MATRIX
from services.notifications import notify_user
from services.readiness import latest_snapshot
from services.realtime import hub, publish_sync
from services.translation import translate, detect_lang

router = APIRouter(tags=["Trainer Message Hub"])
THREAD_ROLES = ["trainer", "parent", "college_admin"]
CATEGORIES = ("All", "Parents", "College", "Groups")


class SendIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    auto_translate: bool = True


class ModerateIn(BaseModel):
    action: str = Field(pattern="^(remove|keep|mute)$")
    reason: Optional[str] = Field(default=None, max_length=500)


class BroadcastIn(BaseModel):
    audience: str = Field(pattern="^(students|parents|both)$")
    batch_ids: List[str] = []
    title: str = Field(min_length=3, max_length=255)
    body: str = Field(min_length=3, max_length=4000)


def _offset() -> datetime.timedelta:
    return datetime.datetime.now() - datetime.datetime.utcnow()


def _when(dt: Optional[datetime.datetime]) -> str:
    """Thread-list time: '10:45 AM' today, 'Yesterday', else 'Oct 7'."""
    if not dt:
        return ""
    local = dt + _offset()
    today = datetime.datetime.now().date()
    if local.date() == today:
        return local.strftime("%I:%M %p").lstrip("0")
    if local.date() == today - datetime.timedelta(days=1):
        return "Yesterday"
    return local.strftime("%b %d").replace(" 0", " ")


def _ago(dt: datetime.datetime) -> str:
    mins = max(0, int((datetime.datetime.utcnow() - dt).total_seconds() // 60))
    if mins < 60:
        return f"{mins} min ago"
    if mins < 60 * 24:
        return f"{mins // 60} hr ago"
    return f"{mins // (60 * 24)} d ago"


def _thread_for(db: Session, thread_id: str, user: TokenPayload) -> TrainerDirectThread:
    """Only the trainer and the contact of a thread may see it; anyone else gets 404."""
    t = db.execute(select(TrainerDirectThread).filter_by(id=thread_id, college_id=user.college_id)).scalar_one_or_none()
    if not t or user.sub not in (t.trainer_user_id, t.contact_user_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    return t


def _child(db: Session, student_id: Optional[str]) -> Optional[dict]:
    if not student_id:
        return None
    s = db.execute(select(Student).filter_by(id=student_id)).scalar_one_or_none()
    if not s:
        return None
    u = db.execute(select(User).filter_by(id=s.user_id)).scalar_one_or_none()
    b = db.execute(select(Batch).filter_by(id=s.batch_id)).scalar_one_or_none() if s.batch_id else None
    snap = latest_snapshot(db, s)
    return {"id": s.id, "name": u.name if u else "", "batch": b.name if b else "", "readiness": snap.score if snap else None, "band": snap.band if snap else None}


def _unread(db: Session, thread_ids: List[str], me: str) -> dict:
    rows = db.execute(
        select(DirectMessage.thread_id, func.count(DirectMessage.id))
        .where(DirectMessage.thread_id.in_(thread_ids or ["_"]), DirectMessage.read_at.is_(None),
               (DirectMessage.sender_user_id != me) | DirectMessage.sender_user_id.is_(None))
        .group_by(DirectMessage.thread_id)
    ).all()
    return dict(rows)


def _last(db: Session, thread_id: str) -> Optional[DirectMessage]:
    return db.execute(select(DirectMessage).filter_by(thread_id=thread_id).order_by(DirectMessage.created_at.desc())).scalars().first()


def _thread_row(db: Session, t: TrainerDirectThread, me: str, unread: dict, viewer_is_trainer: bool) -> dict:
    last = _last(db, t.id)
    child = _child(db, t.student_id)
    if viewer_is_trainer:
        name, chip, initials = t.contact_name, (f"Parent · {child['name']}" if child else t.contact_role_chip), t.avatar_initials
    else:
        trainer = db.execute(select(User).filter_by(id=t.trainer_user_id)).scalar_one_or_none()
        name, chip, initials = (trainer.name if trainer else "Trainer"), (f"Trainer · {child['name']}" if child else "Trainer"), (trainer.avatar_initials if trainer else "T")
    return {
        "id": t.id, "kind": "thread", "name": name, "category": t.contact_category, "role_chip": chip, "avatar": initials,
        "unread": unread.get(t.id, 0), "last_message": (last.text_en if last else "") or "", "time": _when(last.created_at if last else None),
        "sort": (last.created_at if last else t.created_at).isoformat(),
    }


@router.get("/trainer/threads")
def trainer_threads(category: str = "All", current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    if category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown category")
    threads = db.execute(select(TrainerDirectThread).filter_by(trainer_user_id=current_user.sub, college_id=current_user.college_id)).scalars().all()
    unread = _unread(db, [t.id for t in threads], current_user.sub)
    rows = [_thread_row(db, t, current_user.sub, unread, True) for t in threads if category in ("All", t.contact_category)]
    rows.sort(key=lambda r: r["sort"], reverse=True)

    groups = []
    if category in ("All", "Groups"):
        gids = db.execute(select(GroupMember.group_id).filter_by(user_id=current_user.sub, role="moderator")).scalars().all()
        for g in db.execute(select(DiscussionGroup).where(DiscussionGroup.id.in_(gids or ["_"]), DiscussionGroup.college_id == current_user.college_id)).scalars().all():
            last = db.execute(select(GroupMessage).filter_by(group_id=g.id).order_by(GroupMessage.created_at.desc())).scalars().first()
            members = db.execute(select(func.count(GroupMember.id)).filter_by(group_id=g.id, role="member")).scalar_one()
            groups.append({"id": g.id, "kind": "group", "name": g.name, "category": "Groups", "role_chip": f"Group · {members}", "avatar": g.name[:2].upper(),
                           "unread": 0, "last_message": (last.message_text if last and not last.is_removed else "") or "", "time": _when(last.created_at if last else None),
                           "sort": (last.created_at if last else g.created_at).isoformat()})
        groups.sort(key=lambda r: r["sort"], reverse=True)
    return {"threads": rows + groups, "permission_matrix": MATRIX, "moderation_open": len(_open_reports(db, current_user))}


@router.get("/parent/threads")
def parent_threads(current_user: TokenPayload = Depends(require_role(["parent"])), db: Session = Depends(get_db)):
    threads = db.execute(select(TrainerDirectThread).filter_by(contact_user_id=current_user.sub, college_id=current_user.college_id)).scalars().all()
    unread = _unread(db, [t.id for t in threads], current_user.sub)
    rows = sorted((_thread_row(db, t, current_user.sub, unread, False) for t in threads), key=lambda r: r["sort"], reverse=True)
    return {"threads": rows, "reply_sla_hours": 24}


@router.get("/threads/{thread_id}/messages")
def thread_messages(thread_id: str, lang: Optional[str] = None,
                    current_user: TokenPayload = Depends(require_role(THREAD_ROLES)), db: Session = Depends(get_db)):
    """Messages of one thread. lang=ta|en returns each message translated
    (cached); the original always travels with it. Opening marks incoming read."""
    t = _thread_for(db, thread_id, current_user)
    msgs = db.execute(select(DirectMessage).filter_by(thread_id=t.id).order_by(DirectMessage.created_at)).scalars().all()
    now = datetime.datetime.utcnow()
    for m in msgs:
        if m.read_at is None and m.sender_user_id != current_user.sub:
            m.read_at = now
    out = []
    for m in msgs:
        original = m.text_ta if m.original_lang == "ta" and m.text_ta else m.text_en
        display = original
        if lang in ("en", "ta") and lang != m.original_lang:
            stored = m.text_ta if lang == "ta" else m.text_en
            display = stored if stored and stored != original else translate(db, original, lang, t.college_id, src=m.original_lang)
        out.append({"id": m.id, "is_mine": m.sender_user_id == current_user.sub, "sender_name": m.sender_name, "original_lang": m.original_lang,
                    "text": display, "original_text": original, "translated": display != original,
                    "time": (m.created_at + _offset()).strftime("%I:%M %p").lstrip("0"), "date": _when(m.created_at), "read": m.read_at is not None})
    db.commit()
    contact = db.execute(select(User).filter_by(id=t.contact_user_id)).scalar_one_or_none() if t.contact_user_id else None
    trainer = db.execute(select(User).filter_by(id=t.trainer_user_id)).scalar_one_or_none()
    prefers_ta = bool(contact and contact.language_pref == "ta") or t.pref_language == "Prefers Tamil"
    return {
        "thread": {"id": t.id, "category": t.contact_category, "contact_name": t.contact_name, "contact_role": contact.role if contact else "college",
                   "prefers_tamil": prefers_ta, "trainer_name": trainer.name if trainer else "", "child": _child(db, t.student_id)},
        "messages": out,
    }


@router.post("/threads/{thread_id}/messages")
def send_thread_message(thread_id: str, req: SendIn, current_user: TokenPayload = Depends(require_role(THREAD_ROLES)), db: Session = Depends(get_db)):
    t = _thread_for(db, thread_id, current_user)
    me = db.execute(select(User).filter_by(id=current_user.sub)).scalar_one()
    other_id = t.contact_user_id if current_user.sub == t.trainer_user_id else t.trainer_user_id
    other = db.execute(select(User).filter_by(id=other_id)).scalar_one_or_none() if other_id else None
    ok, why = can_message(me.role, other.role if other else "college_admin")
    if not ok:
        raise HTTPException(status_code=403, detail=why)
    text = req.text.strip()
    src = detect_lang(text)
    text_en = text if src == "en" else translate(db, text, "en", t.college_id, src="ta")
    text_ta = text if src == "ta" else None
    if src == "en" and req.auto_translate and other and other.language_pref == "ta":
        text_ta = translate(db, text, "ta", t.college_id, src="en")
    m = DirectMessage(id=f"dm_{uuid.uuid4().hex[:16]}", college_id=t.college_id, thread_id=t.id, is_incoming=normalize_role(me.role) != "trainer",
                      sender_user_id=me.id, sender_name=me.name, text_en=text_en, text_ta=text_ta, original_lang=src,
                      timestamp_str=datetime.datetime.now().strftime("%I:%M %p").lstrip("0"))
    db.add(m)
    t.last_message_preview, t.last_message_time = text_en[:255], m.timestamp_str
    if other:
        link = "/trainer/messages" if normalize_role(other.role) == "trainer" else ("/parent/messages" if other.role == "parent" else "/college")
        title_en = f"New message from {me.name}"
        notify_user(db, other.id, title_en, text_en[:140], title_ta=f"{me.name} அனுப்பிய புதிய செய்தி", body_ta=(text_ta or text_en)[:140],
                    kind="message", link=link, channels=("in_app", "sms") if other.role == "parent" else ("in_app",), college_id=t.college_id)
    record_audit(db, current_user, "thread.message", "thread", t.id, {"message_id": m.id, "lang": src})
    db.commit()
    publish_sync(f"thread:{t.id}", {"type": "message", "thread_id": t.id, "message_id": m.id})
    return {"success": True, "message_id": m.id, "translated_to_tamil": bool(text_ta and src == "en")}


@router.post("/direct-messages/{message_id}/translate")
def translate_message(message_id: str, to: str = "ta", current_user: TokenPayload = Depends(require_role(THREAD_ROLES)), db: Session = Depends(get_db)):
    if to not in ("en", "ta"):
        raise HTTPException(status_code=422, detail="to must be en or ta")
    m = db.execute(select(DirectMessage).filter_by(id=message_id, college_id=current_user.college_id)).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    _thread_for(db, m.thread_id, current_user)
    original = m.text_ta if m.original_lang == "ta" and m.text_ta else m.text_en
    out = original if to == m.original_lang else ((m.text_ta if to == "ta" else m.text_en) or translate(db, original, to, m.college_id, src=m.original_lang))
    db.commit()
    return {"id": m.id, "to": to, "text": out, "original_text": original, "original_lang": m.original_lang}


# ---- moderation queue (reports from Screen 34 groups) ----
def _open_reports(db: Session, user: TokenPayload) -> list:
    gids = db.execute(select(GroupMember.group_id).filter_by(user_id=user.sub, role="moderator")).scalars().all()
    return db.execute(select(MessageReport).where(MessageReport.group_id.in_(gids or ["_"]), MessageReport.status == "open",
                                                  MessageReport.college_id == user.college_id).order_by(MessageReport.created_at.desc())).scalars().all()


@router.get("/trainer/moderation")
def moderation_queue(current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    items = []
    for r in _open_reports(db, current_user):
        msg = db.execute(select(GroupMessage).filter_by(id=r.message_id)).scalar_one_or_none()
        g = db.execute(select(DiscussionGroup).filter_by(id=r.group_id)).scalar_one_or_none()
        if not msg or not g:
            continue
        items.append({"id": r.id, "group": g.name, "reason": r.reason, "author": msg.sender_name, "author_role": msg.sender_role,
                      "snippet": msg.message_text[:200], "time": _ago(r.created_at)})
    return {"items": items, "count": len(items)}


@router.post("/trainer/moderation/{report_id}")
def moderate(report_id: str, req: ModerateIn, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    report = next((r for r in _open_reports(db, current_user) if r.id == report_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or already handled")
    reason = (req.reason or "").strip()
    if req.action in ("remove", "mute") and len(reason) < 3:
        raise HTTPException(status_code=422, detail="A reason is required to remove a message or mute a member")
    msg = db.execute(select(GroupMessage).filter_by(id=report.message_id)).scalar_one()
    if req.action in ("remove", "mute"):
        msg.is_removed, msg.removed_reason = True, reason
    if req.action == "mute" and msg.sender_user_id:
        member = db.execute(select(GroupMember).filter_by(group_id=report.group_id, user_id=msg.sender_user_id)).scalar_one_or_none()
        if member:
            member.muted_until = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    report.status = "dismissed" if req.action == "keep" else "actioned"
    db.add(ModerationAction(id=f"mod_{uuid.uuid4().hex[:16]}", college_id=report.college_id, report_id=report.id, message_id=msg.id,
                            target_user_id=msg.sender_user_id, action=req.action, reason=reason or None, actor_user_id=current_user.sub))
    if req.action != "keep" and msg.sender_user_id:
        notify_user(db, msg.sender_user_id, "A moderator removed your message", reason, title_ta="கண்காணிப்பாளர் உங்கள் செய்தியை நீக்கினார்",
                    kind="info", link="/student/discussions", college_id=report.college_id)
    record_audit(db, current_user, f"moderation.{req.action}", "message", msg.id, {"report_id": report.id, "reason": reason})
    db.commit()
    publish_sync(f"group:{report.group_id}", {"type": "moderation", "message_id": msg.id})
    return {"success": True, "status": report.status}


# ---- broadcasts ----
@router.post("/broadcasts")
def send_broadcast(req: BroadcastIn, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    mine = get_trainer_batch_ids(trainer, db)
    batch_ids = req.batch_ids or mine
    if any(b not in mine for b in batch_ids):
        raise HTTPException(status_code=403, detail="You can only broadcast to your own batches")
    students = db.execute(select(Student).where(Student.batch_id.in_(batch_ids), Student.college_id == current_user.college_id)).scalars().all()
    report = {"students_in_app": 0, "parents_in_app": 0, "parents_sms": 0, "students": 0, "parents": 0}
    link_ta = f"அறிவிப்பு: {req.title}"
    if req.audience in ("students", "both"):
        for s in students:
            if s.user_id and notify_user(db, s.user_id, req.title, req.body, title_ta=link_ta, kind="broadcast", college_id=current_user.college_id):
                report["students"] += 1
                report["students_in_app"] += 1
    if req.audience in ("parents", "both"):
        parent_ids = sorted(set(db.execute(select(ParentStudent.parent_user_id).where(ParentStudent.student_id.in_([s.id for s in students] or ["_"]))).scalars().all()))
        for pid in parent_ids:
            rows = notify_user(db, pid, req.title, req.body, title_ta=link_ta, kind="broadcast", link="/parent", channels=("in_app", "sms"), college_id=current_user.college_id)
            if rows:
                report["parents"] += 1
                report["parents_in_app"] += sum(1 for n in rows if n.channel == "in_app")
                # SMS is handed to the outbox here and sent after commit
                report["parents_sms"] += sum(1 for n in rows if n.channel == "sms" and n.delivery_status == "queued")
    report["total_recipients"] = report["students"] + report["parents"]
    b = Broadcast(id=f"bc_{uuid.uuid4().hex[:16]}", college_id=current_user.college_id, author_user_id=current_user.sub, audience=req.audience,
                  batch_ids=json.dumps(batch_ids), title=req.title, body=req.body, delivery=json.dumps(report))
    db.add(b)
    record_audit(db, current_user, "broadcast.sent", "broadcast", b.id, {"audience": req.audience, "batches": batch_ids, **report})
    db.commit()
    return {"success": True, "broadcast_id": b.id, "delivery": report}


@router.get("/trainer/broadcasts")
def list_broadcasts(current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    batches = [{"id": b.id, "name": b.name} for b in db.execute(select(Batch).where(Batch.id.in_(get_trainer_batch_ids(trainer, db) or ["_"]))).scalars().all()]
    rows = db.execute(select(Broadcast).filter_by(author_user_id=current_user.sub).order_by(Broadcast.created_at.desc()).limit(10)).scalars().all()
    return {"batches": batches, "broadcasts": [{"id": b.id, "title": b.title, "audience": b.audience, "delivery": json.loads(b.delivery), "time": _when(b.created_at)} for b in rows]}


@router.websocket("/ws/threads/{thread_id}")
async def thread_socket(websocket: WebSocket, thread_id: str, token: Optional[str] = None):
    payload = websocket_user(token)          # local or Keycloak token, and still active
    if not payload:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        _thread_for(db, thread_id, payload)
    except HTTPException:
        await websocket.close(code=4404)
        return
    finally:
        db.close()
    channel = f"thread:{thread_id}"
    await hub.subscribe(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(channel, websocket)
