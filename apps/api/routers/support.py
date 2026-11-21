"""Screen 49 · Support desk: report a problem from any screen (L39); IREP staff
replies reach the requester's notification centre (L28).
Spec: docs/screens/21-16-20-49-reports-and-support.md"""
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import PLATFORM_TENANT, TokenPayload, get_current_user, normalize_role
from models.schema import College, SupportMessage, SupportTicket, User
from services.notifications import notify_user

router = APIRouter(prefix="/support", tags=["Support desk"])
CATEGORIES = ("bug", "question", "access", "data")


class TicketIn(BaseModel):
    subject: str = Field(min_length=4, max_length=255)
    body: str = Field(min_length=4, max_length=4000)
    category: str = "question"
    page_path: Optional[str] = Field(default=None, max_length=255)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


def _is_staff(user: TokenPayload) -> bool:
    return normalize_role(user.role) == "irep_admin"


def _ticket(db: Session, ticket_id: str, user: TokenPayload) -> SupportTicket:
    t = db.get(SupportTicket, ticket_id)
    # requesters see their own tickets only; IREP staff see every college's
    if t is None or not (_is_staff(user) or (t.requester_user_id == user.sub and t.college_id == user.college_id)):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


def _row(t: SupportTicket, colleges: Optional[dict] = None, count: int = 0) -> dict:
    return {"id": t.id, "subject": t.subject, "category": t.category, "status": t.status, "page_path": t.page_path,
            "requester_name": t.requester_name, "requester_role": t.requester_role,
            "college": (colleges or {}).get(t.college_id, t.college_id), "messages": count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "last_activity_at": t.last_activity_at.isoformat() if t.last_activity_at else None}


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def report_problem(req: TicketIn, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    """L39: report-a-problem from any screen."""
    if req.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown category")
    me = db.get(User, current_user.sub)
    if me is None:
        raise HTTPException(status_code=404, detail="User not found")
    now = datetime.datetime.utcnow()
    t = SupportTicket(id=f"tkt_{uuid.uuid4().hex[:16]}", college_id=current_user.college_id, requester_user_id=me.id,
                      requester_name=me.name, requester_role=normalize_role(current_user.role), subject=req.subject.strip(),
                      category=req.category, page_path=req.page_path, status="open", last_activity_at=now)
    db.add(t)
    db.flush()                                    # the ticket row exists before its first message (FK)
    db.add(SupportMessage(id=f"smsg_{uuid.uuid4().hex[:16]}", college_id=t.college_id, ticket_id=t.id, author_user_id=me.id,
                          author_name=me.name, is_staff=False, body=req.body.strip()))
    staff = db.execute(select(User.id).where(User.college_id == PLATFORM_TENANT, User.role.in_(["irep_admin", "super_admin", "admin"]),
                                             User.is_active.is_(True))).scalars().all()
    for uid in staff:
        notify_user(db, uid, f"New support ticket: {t.subject}", f"{me.name} ({t.requester_role}) · {req.page_path or ''}",
                    title_ta=f"புதிய உதவிக் கோரிக்கை: {t.subject}", kind="support", link=f"/admin/support?ticket={t.id}",
                    college_id=PLATFORM_TENANT)
    db.commit()
    return _row(t, count=1)


@router.get("/tickets")
def list_tickets(status_filter: Optional[str] = None, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(SupportTicket)
    if not _is_staff(current_user):
        q = q.where(SupportTicket.requester_user_id == current_user.sub, SupportTicket.college_id == current_user.college_id)
    if status_filter in ("open", "answered", "closed"):
        q = q.where(SupportTicket.status == status_filter)
    tickets = db.execute(q.order_by(SupportTicket.last_activity_at.desc()).limit(200)).scalars().all()
    counts = dict(db.execute(select(SupportMessage.ticket_id, func.count(SupportMessage.id))
                             .where(SupportMessage.ticket_id.in_([t.id for t in tickets] or ["_"])).group_by(SupportMessage.ticket_id)).all())
    colleges = dict(db.execute(select(College.id, College.name)).all()) if _is_staff(current_user) else None
    return {"staff": _is_staff(current_user), "tickets": [_row(t, colleges, counts.get(t.id, 0)) for t in tickets]}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _ticket(db, ticket_id, current_user)
    msgs = db.execute(select(SupportMessage).where(SupportMessage.ticket_id == t.id).order_by(SupportMessage.created_at)).scalars().all()
    colleges = dict(db.execute(select(College.id, College.name).where(College.id == t.college_id)).all())
    return {**_row(t, colleges, len(msgs)),
            "thread": [{"id": m.id, "author": m.author_name, "is_staff": m.is_staff, "body": m.body,
                        "at": m.created_at.isoformat() if m.created_at else None} for m in msgs]}


@router.post("/tickets/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
def reply(ticket_id: str, req: MessageIn, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _ticket(db, ticket_id, current_user)
    if t.status == "closed":
        raise HTTPException(status_code=409, detail="This ticket is closed; report a new problem instead")
    staff = _is_staff(current_user)
    name = (db.execute(select(User.name).where(User.id == current_user.sub)).scalar_one_or_none() or current_user.name or "IREP support")
    m = SupportMessage(id=f"smsg_{uuid.uuid4().hex[:16]}", college_id=t.college_id, ticket_id=t.id, author_user_id=current_user.sub,
                       author_name=name if not staff else f"{name} (IREP support)", is_staff=staff, body=req.body.strip())
    db.add(m)
    t.last_activity_at = datetime.datetime.utcnow()
    if staff:
        t.status = "answered"
        # L28: ticket replies reach the requester's notification centre (support.ticket_replied; no audit, §5.3)
        notify_user(db, t.requester_user_id, f"IREP support replied: {t.subject}", req.body.strip()[:140],
                    title_ta=f"IREP உதவி பதிலளித்தது: {t.subject}", kind="support", link=f"/support?ticket={t.id}",
                    college_id=t.college_id)
    elif t.status == "answered":
        t.status = "open"
    db.commit()
    return {"id": m.id, "status": t.status}


@router.post("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _ticket(db, ticket_id, current_user)
    t.status, t.last_activity_at = "closed", datetime.datetime.utcnow()
    db.commit()
    return {"id": t.id, "status": t.status}
