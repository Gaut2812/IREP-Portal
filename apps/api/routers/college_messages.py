"""Screen 41 · College messages: chat with trainers (L20) and announcement-only posts to students
and parents (L30), delivered in chunks through the outbox. Also the college's AWS Academy link
for the Cloud Sandbox lab (labs track S14). Spec: docs/screens/41-40-messages-surveys.md"""
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_user_name
from models.schema import Batch, Broadcast, Trainer, TrainerDirectThread, User, VirtualLabItem
from routers.messages_hub import _thread_row, _unread
from services.audit import record_audit
from services.broadcasts import start_broadcast
from services.chat_policy import can_message

router = APIRouter(prefix="/college", tags=["College messages"])
COLLEGE = require_role(["college_admin"])


class StartThreadIn(BaseModel):
    trainer_user_id: str


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    body: str = Field(min_length=3, max_length=2000)
    title_ta: Optional[str] = Field(default=None, max_length=255)
    body_ta: Optional[str] = Field(default=None, max_length=2000)
    audience: str = "both"                 # students, parents, both
    batch_ids: Optional[List[str]] = None  # None or empty = the whole college


class SandboxIn(BaseModel):
    url: str = Field(min_length=12, max_length=512)


# ------------------------------------------------------------------ L20: threads with trainers

@router.get("/threads")
def college_threads(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    threads = db.execute(select(TrainerDirectThread).where(TrainerDirectThread.college_id == current_user.college_id,
                                                           TrainerDirectThread.contact_user_id == current_user.sub)).scalars().all()
    unread = _unread(db, [t.id for t in threads], current_user.sub)
    rows = [_thread_row(db, t, current_user.sub, unread, False) for t in threads]
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_([t.trainer_user_id for t in threads] or ["_"]))).all())
    for r, t in zip(rows, threads):
        r["name"] = names.get(t.trainer_user_id, r["name"])        # the college sees the trainer's name
    return {"threads": rows}


@router.get("/message-contacts")
def college_trainers(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    rows = db.execute(select(Trainer.user_id, User.name, Trainer.designation).join(User, User.id == Trainer.user_id)
                      .where(Trainer.college_id == current_user.college_id).order_by(User.name)).all()
    return {"trainers": [{"user_id": u, "name": n, "designation": d} for u, n, d in rows]}


@router.post("/threads", status_code=status.HTTP_201_CREATED)
def start_thread(req: StartThreadIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    trainer = db.execute(select(User).where(User.id == req.trainer_user_id, User.college_id == current_user.college_id)).scalar_one_or_none()
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found")
    ok, why = can_message(current_user.role, trainer.role)            # the one place that decides (rule 7)
    if not ok:
        raise HTTPException(status_code=403, detail=why)
    t = db.execute(select(TrainerDirectThread).where(TrainerDirectThread.college_id == current_user.college_id,
                                                     TrainerDirectThread.trainer_user_id == trainer.id,
                                                     TrainerDirectThread.contact_user_id == current_user.sub)).scalars().first()
    if t is None:
        me = db.get(User, current_user.sub)
        t = TrainerDirectThread(id=f"th_{uuid.uuid4().hex[:16]}", college_id=current_user.college_id, trainer_user_id=trainer.id,
                                contact_user_id=me.id, contact_name=me.name, contact_category="College",
                                contact_role_chip="College coordinator", avatar_initials=(me.avatar_initials or "CC")[:8],
                                pref_language="Prefers Tamil" if me.language_pref == "ta" else "Prefers English")
        db.add(t)
        db.commit()
    return {"thread_id": t.id}


# ------------------------------------------------------------------ L30: announcements

def _announcement_out(b: Broadcast, batch_names: dict) -> dict:
    ids = json.loads(b.batch_ids or "[]")
    return {"id": b.id, "title": b.title, "title_ta": b.title_ta, "body": b.body, "audience": b.audience,
            "batches": [batch_names.get(i, i) for i in ids] or "all", "status": b.status, "recipients": b.recipients_total,
            "delivered": b.delivered, "chunks": f"{b.chunks_done}/{b.chunks_total}", "at": b.created_at.isoformat() if b.created_at else None}


@router.get("/announcements")
def list_announcements(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    names = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id)).all())
    rows = db.execute(select(Broadcast).where(Broadcast.college_id == current_user.college_id, Broadcast.author_role == "college")
                      .order_by(Broadcast.created_at.desc()).limit(50)).scalars().all()
    return {"announcements": [_announcement_out(b, names) for b in rows],
            "batches": [{"id": i, "name": n} for i, n in sorted(names.items(), key=lambda kv: kv[1])]}


@router.post("/announcements", status_code=status.HTTP_201_CREATED)
def announce(req: AnnouncementIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    if req.audience not in ("students", "parents", "both"):
        raise HTTPException(status_code=422, detail="audience must be students, parents or both")
    if req.batch_ids:
        known = set(db.execute(select(Batch.id).where(Batch.college_id == current_user.college_id, Batch.id.in_(req.batch_ids))).scalars())
        if known != set(req.batch_ids):
            raise HTTPException(status_code=404, detail="Batch not found")
    b = start_broadcast(db, college_id=current_user.college_id, author_user_id=current_user.sub,
                        author_name=get_user_name(db, current_user.sub, "College"), author_role="college", audience=req.audience,
                        batch_ids=req.batch_ids or None, title=req.title.strip(), body=req.body.strip(),
                        title_ta=(req.title_ta or "").strip() or None, body_ta=(req.body_ta or "").strip() or None)
    record_audit(db, current_user, "announcement.posted", "broadcast", b.id,
                 {"audience": b.audience, "recipients": b.recipients_total, "chunks": b.chunks_total})
    db.commit()
    names = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id)).all())
    return _announcement_out(b, names)


@router.get("/announcements/{broadcast_id}")
def announcement(broadcast_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    b = db.execute(select(Broadcast).where(Broadcast.id == broadcast_id, Broadcast.college_id == current_user.college_id)).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    names = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id)).all())
    return _announcement_out(b, names)


# ------------------------------------------------------------------ labs S14: the college's AWS Academy link

ALLOWED_SANDBOX_HOSTS = ("awsacademy.instructure.com", "www.awsacademy.com", "awsacademy.com")


@router.put("/labs/cloud-sandbox")
def set_cloud_sandbox(req: SandboxIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    """The Cloud Sandbox lab opens this college's AWS Academy Learner Lab course."""
    from urllib.parse import urlparse
    u = urlparse(req.url.strip())
    if u.scheme != "https" or (u.hostname or "").lower() not in ALLOWED_SANDBOX_HOSTS:
        raise HTTPException(status_code=422, detail="Use your AWS Academy course link (https://awsacademy.instructure.com/...)")
    lab = db.execute(select(VirtualLabItem).where(VirtualLabItem.college_id == current_user.college_id,
                                                  VirtualLabItem.runtime == "external")).scalars().first()
    if lab is None:
        raise HTTPException(status_code=404, detail="This college has no Cloud Sandbox lab")
    lab.external_url = req.url.strip()
    record_audit(db, current_user, "labs.cloud_sandbox_link", "lab", lab.id, {"host": u.hostname})
    db.commit()
    return {"lab_id": lab.id, "external_url": lab.external_url}


@router.get("/labs/cloud-sandbox")
def get_cloud_sandbox(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    lab = db.execute(select(VirtualLabItem).where(VirtualLabItem.college_id == current_user.college_id,
                                                  VirtualLabItem.runtime == "external")).scalars().first()
    return {"lab_id": lab.id if lab else None, "external_url": lab.external_url if lab else None}
