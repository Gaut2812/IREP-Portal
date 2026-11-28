"""Screen 02 · College settings (college admin). Spec: docs/screens/02-college-settings.md

Users and roles, branding and chat policy, student lookup for data requests
(the requests themselves live in routers/audit_consent.py, link L27).
"""
import re
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, get_password_hash, keycloak_mode, require_role
from models.schema import College, Student, User
from services.audit import record_audit
from services.invitations import INVITE_HOURS, create_invitation, get_invitation, list_invitations, resend_invitation, revoke_invitation
from services.outbox import emit

router = APIRouter(prefix="/college", tags=["Screen 02 · College settings"])
COLLEGE = require_role(["college_admin"])
STAFF_ROLES = ("college_admin", "placement_officer")
LOGO_RE = re.compile(r"^(https://[^\s]+|/[A-Za-z0-9_\-./]+)$")


class BrandingIn(BaseModel):
    logo_url: Optional[str] = Field(default=None, max_length=512)
    chat_retention_days: int = Field(ge=30, le=3650)


class CollegeUserIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=32)
    role: str = Field(pattern="^(college_admin|placement_officer)$")


def _college(db: Session, college_id: str) -> College:
    c = db.get(College, college_id)
    if c is None:
        raise HTTPException(status_code=404, detail="College not found")
    return c


def _college_user(db: Session, college_id: str, user_id: str) -> User:
    u = db.execute(select(User).where(User.id == user_id, User.college_id == college_id, User.role.in_(STAFF_ROLES))).scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=404, detail="User not found in your college")
    return u


@router.get("/settings")
def get_settings(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    c = _college(db, current_user.college_id)
    users = db.execute(select(User).where(User.college_id == c.id, User.role.in_(STAFF_ROLES)).order_by(User.name)).scalars().all()
    return {
        "college": {"id": c.id, "name": c.name, "code": c.code, "city": c.city, "state": c.state, "status": c.status,
                    "logo_url": c.logo_url, "chat_retention_days": c.chat_retention_days},
        "users": [{"id": u.id, "name": u.name, "email": u.email, "phone": u.phone, "role": u.role, "is_active": bool(u.is_active),
                   "is_me": u.id == current_user.sub} for u in users],
    }


@router.put("/settings/branding")
def set_branding(req: BrandingIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    c = _college(db, current_user.college_id)
    logo = (req.logo_url or "").strip() or None
    if logo and not LOGO_RE.match(logo):
        raise HTTPException(status_code=422, detail="The logo must be an https:// URL or a portal path like /logo.png")
    before = {"logo_url": c.logo_url, "chat_retention_days": c.chat_retention_days}
    c.logo_url, c.chat_retention_days = logo, req.chat_retention_days
    after = {"logo_url": c.logo_url, "chat_retention_days": c.chat_retention_days}
    record_audit(db, current_user, "college.settings_changed", "college", c.id,
                 {k: {"from": before[k], "to": after[k]} for k in after if before[k] != after[k]})
    db.commit()
    return after


@router.post("/users", status_code=status.HTTP_201_CREATED)
def add_user(req: CollegeUserIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid = current_user.college_id
    email = req.email.strip().lower()
    if db.execute(select(User.id).where(func.lower(User.email) == email)).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    name = req.name.strip()
    u = User(id=f"usr_{uuid.uuid4().hex[:16]}", college_id=cid, email=email, name=name, phone=(req.phone or "").strip() or None,
             role=req.role, avatar_initials="".join(p[0] for p in name.split()[:2]).upper() or "CU", language_pref="en",
             hashed_password=get_password_hash(secrets.token_urlsafe(32)))
    db.add(u)
    db.flush()
    record_audit(db, current_user, "college.user_created", "user", u.id, {"role": req.role})
    invite = create_invitation(db, u, current_user)       # Phase 5: a set-password link, not a temporary password
    db.commit()
    return {"id": u.id, "email": email, "role": u.role, **invite}


@router.get("/invitations")
def college_invitations(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    """Who was invited to this college, by whom, and whether they accepted."""
    return {"items": list_invitations(db, current_user.college_id), "valid_hours": INVITE_HOURS}


@router.post("/invitations/{invitation_id}/resend")
def college_resend_invitation(invitation_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    out = resend_invitation(db, get_invitation(db, current_user.college_id, invitation_id), current_user)
    db.commit()
    return out


@router.post("/invitations/{invitation_id}/revoke")
def college_revoke_invitation(invitation_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    inv = get_invitation(db, current_user.college_id, invitation_id)
    if inv.user_id == current_user.sub:
        raise HTTPException(status_code=409, detail="You cannot revoke your own invitation")
    out = revoke_invitation(db, inv, current_user)
    db.commit()
    return out


@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    u = _college_user(db, current_user.college_id, user_id)
    if u.id == current_user.sub:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
    if u.role == "college_admin":
        active_admins = db.execute(select(func.count(User.id)).where(User.college_id == u.college_id, User.role == "college_admin",
                                                                     User.is_active.is_(True))).scalar_one()
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The college needs at least one active college admin")
    u.is_active = False
    record_audit(db, current_user, "college.user_deactivated", "user", u.id, {"role": u.role})
    db.commit()
    return {"id": u.id, "is_active": False}


@router.post("/users/{user_id}/reactivate")
def reactivate_user(user_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    u = _college_user(db, current_user.college_id, user_id)
    u.is_active = True
    record_audit(db, current_user, "college.user_reactivated", "user", u.id, {"role": u.role})
    db.commit()
    return {"id": u.id, "is_active": True}


@router.get("/students")
def search_students(search: str = Query(min_length=2, max_length=64), current_user: TokenPayload = Depends(COLLEGE),
                    db: Session = Depends(get_db)):
    like = f"%{search.strip()}%"
    rows = db.execute(select(Student.id, Student.register_no, User.name, Student.batch_name).join(User, User.id == Student.user_id)
                      .where(Student.college_id == current_user.college_id, or_(Student.register_no.ilike(like), User.name.ilike(like)))
                      .order_by(User.name).limit(20)).all()
    return {"students": [{"id": r[0], "register_no": r[1], "name": r[2], "batch": r[3]} for r in rows]}
