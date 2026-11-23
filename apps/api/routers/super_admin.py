"""Super admin (docs/PERMISSIONS.md): IREP staff accounts and logged support sessions.

Only `super_admin` reaches these routes. MoU terms, feature switches (routers/admin_colleges.py) and
deletion approvals (routers/audit_consent.py) are also super-admin only. Accounts are invited, never
self-registered; IREP staff and super admins must use two-factor sign-in in Keycloak
(ops/configure_keycloak.py). Every request a super admin makes is audited (main.py), on top of the
specific audit events below.
"""
import datetime
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import PLATFORM_TENANT, STAFF_ROLES, SUPER, TokenPayload, get_password_hash, keycloak_mode
from models.schema import College, SupportSession, SupportTicket, User
from services.audit import record_audit
from services.outbox import emit, handler as outbox_handler

router = APIRouter(prefix="/admin", tags=["Super admin"])
ROLE_PATTERN = "^(irep_admin|super_admin)$"


class StaffIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: str = Field(default="irep_admin", pattern=ROLE_PATTERN)


class RoleIn(BaseModel):
    role: str = Field(pattern=ROLE_PATTERN)


class SupportSessionIn(BaseModel):
    college_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=10, max_length=1000)
    minutes: int = Field(default=60, ge=15, le=240)
    staff_user_id: Optional[str] = Field(default=None, max_length=64)   # default: the super admin
    ticket_id: Optional[str] = Field(default=None, max_length=64)


def _staff(db: Session, user_id: str) -> User:
    u = db.get(User, user_id)
    if u is None or u.college_id != PLATFORM_TENANT or u.role not in STAFF_ROLES:
        raise HTTPException(status_code=404, detail="Staff account not found")
    return u


def _staff_out(u: User, me: TokenPayload) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "is_active": bool(u.is_active),
            "two_factor": "required", "is_you": u.id == me.sub}


def _active_supers(db: Session) -> int:
    return db.execute(select(func.count(User.id)).where(User.role == "super_admin", User.is_active.is_(True))).scalar_one()


# ---- IREP staff accounts ----
@router.get("/staff")
def list_staff(current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    rows = db.execute(select(User).where(User.college_id == PLATFORM_TENANT, User.role.in_(STAFF_ROLES))
                      .order_by(User.role.desc(), User.name)).scalars().all()
    return {"items": [_staff_out(u, current_user) for u in rows]}


@router.post("/staff", status_code=status.HTTP_201_CREATED)
def invite_staff(req: StaffIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    if db.execute(select(User.id).where(func.lower(User.email) == email)).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    name = req.name.strip()
    temp_password = None if keycloak_mode() else secrets.token_urlsafe(9)
    u = User(id=f"usr_{uuid.uuid4().hex[:16]}", college_id=PLATFORM_TENANT, email=email, name=name, role=req.role,
             avatar_initials="".join(p[0] for p in name.split()[:2]).upper() or "IR", language_pref="en",
             hashed_password=get_password_hash(temp_password or secrets.token_urlsafe(32)))
    db.add(u)
    db.flush()
    record_audit(db, current_user, "staff.invited", "user", u.id, {"email": email, "role": req.role}, college_id=PLATFORM_TENANT)
    if keycloak_mode():
        # Keycloak emails a set-password link; the first sign-in also sets up the authenticator app (2FA)
        emit(db, "identity.invite_user", {"user_id": u.id}, college_id=PLATFORM_TENANT, entity_type="user", entity_id=u.id)
    db.commit()
    out = _staff_out(u, current_user)
    if temp_password:
        out["temporary_password"] = temp_password        # development only; shown once, never stored in plain text
    else:
        out["invite"] = "Keycloak will email a link to set a password and the authenticator app"
    return out


@router.put("/staff/{user_id}/role")
def change_staff_role(user_id: str, req: RoleIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    u = _staff(db, user_id)
    if u.role == req.role:
        return _staff_out(u, current_user)
    if u.role == "super_admin" and u.is_active and _active_supers(db) <= 1:
        raise HTTPException(status_code=409, detail="This is the last active super admin")
    before, u.role = u.role, req.role
    record_audit(db, current_user, "staff.role_changed", "user", u.id, {"from": before, "to": u.role}, college_id=PLATFORM_TENANT)
    if keycloak_mode():
        # the invite handler is idempotent: for an existing account it only re-syncs the realm role
        emit(db, "identity.invite_user", {"user_id": u.id}, college_id=PLATFORM_TENANT, entity_type="user", entity_id=u.id)
    db.commit()
    return _staff_out(u, current_user)


def _set_active(db: Session, current_user: TokenPayload, user_id: str, active: bool) -> dict:
    u = _staff(db, user_id)
    if u.id == current_user.sub and not active:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
    if not active and u.role == "super_admin" and u.is_active and _active_supers(db) <= 1:
        raise HTTPException(status_code=409, detail="This is the last active super admin")
    if bool(u.is_active) != active:
        u.is_active = active
        record_audit(db, current_user, "staff.reactivated" if active else "staff.deactivated", "user", u.id, None,
                     college_id=PLATFORM_TENANT)
        if keycloak_mode():
            emit(db, "identity.set_enabled", {"user_id": u.id, "enabled": active}, college_id=PLATFORM_TENANT,
                 entity_type="user", entity_id=u.id)
    db.commit()
    return _staff_out(u, current_user)


@router.post("/staff/{user_id}/deactivate")
def deactivate_staff(user_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    return _set_active(db, current_user, user_id, False)


@router.post("/staff/{user_id}/reactivate")
def reactivate_staff(user_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    return _set_active(db, current_user, user_id, True)


@outbox_handler("identity.set_enabled")
def _set_enabled_in_keycloak(db: Session, event) -> None:
    """Idempotent: sets Keycloak's enabled flag to the payload value (a disabled user cannot sign in)."""
    from services.keycloak_admin import admin_from_env
    u = db.get(User, event.payload["user_id"])
    if u is None:
        return
    kc = admin_from_env()
    existing = kc.find_user(u.email)
    if existing:
        kc.http.put(f"/users/{existing['id']}", json={"enabled": bool(event.payload["enabled"])}).raise_for_status()


# ---- logged support sessions ----
def _session_out(s: SupportSession, names: dict, now: datetime.datetime) -> dict:
    return {"id": s.id, "college_id": s.college_id, "college_name": names.get(s.college_id), "staff_user_id": s.staff_user_id,
            "staff_name": names.get(s.staff_user_id), "ticket_id": s.ticket_id, "reason": s.reason,
            "opened_at": s.opened_at.isoformat(), "expires_at": s.expires_at.isoformat(),
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "active": s.ended_at is None and s.expires_at > now}


def _names(db: Session, rows) -> dict:
    cids = {r.college_id for r in rows} or {"_"}
    uids = {r.staff_user_id for r in rows} or {"_"}
    out = dict(db.execute(select(College.id, College.name).where(College.id.in_(cids))).all())
    out.update(dict(db.execute(select(User.id, User.name).where(User.id.in_(uids))).all()))
    return out


@router.get("/support-sessions")
def list_support_sessions(current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    rows = db.execute(select(SupportSession).order_by(SupportSession.opened_at.desc()).limit(200)).scalars().all()
    now = datetime.datetime.utcnow()
    names = _names(db, rows)
    return {"items": [_session_out(s, names, now) for s in rows]}


@router.post("/support-sessions", status_code=status.HTTP_201_CREATED)
def open_support_session(req: SupportSessionIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    c = db.get(College, req.college_id)
    if c is None:
        raise HTTPException(status_code=404, detail="College not found")
    staff = _staff(db, req.staff_user_id or current_user.sub)
    if not staff.is_active:
        raise HTTPException(status_code=409, detail="This staff account is deactivated")
    if req.ticket_id:
        t = db.get(SupportTicket, req.ticket_id)
        if t is None or t.college_id != c.id:
            raise HTTPException(status_code=404, detail="Support ticket not found for this college")
    now = datetime.datetime.utcnow()
    s = SupportSession(id=f"sup_{uuid.uuid4().hex[:16]}", college_id=c.id, staff_user_id=staff.id, opened_by=current_user.sub,
                       ticket_id=req.ticket_id, reason=req.reason.strip(), opened_at=now,
                       expires_at=now + datetime.timedelta(minutes=req.minutes))
    db.add(s)
    db.flush()
    record_audit(db, current_user, "support_session.opened", "support_session", s.id,
                 {"staff_user_id": staff.id, "minutes": req.minutes, "ticket_id": req.ticket_id, "reason": s.reason}, college_id=c.id)
    db.commit()
    return _session_out(s, _names(db, [s]), now)


@router.post("/support-sessions/{session_id}/end")
def end_support_session(session_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    s = db.get(SupportSession, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Support session not found")
    now = datetime.datetime.utcnow()
    if s.ended_at is None:
        s.ended_at, s.ended_by = min(now, s.expires_at), current_user.sub
        record_audit(db, current_user, "support_session.ended", "support_session", s.id, None, college_id=s.college_id)
    db.commit()
    return _session_out(s, _names(db, [s]), now)
