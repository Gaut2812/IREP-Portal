"""Phase 5: invitations instead of temporary passwords.

Every account a person creates for someone else (a college's first admin, college trainers and staff, IREP staff)
gets one Invitation row: who invited whom, when, and whether they accepted. Three delivery paths:

- Keycloak mode (production): Keycloak emails its own set-password link (outbox ``identity.invite_user``).
  The portal keeps no token.
- Local mode with real email (NOTIFY_ADAPTER=live): the outbox handler ``invite.send`` mints the one-time token
  when it sends the email, so the token never sits in an outbox payload or a notification row.
- Local mode without email (development): the request mints the token and returns the link once to the
  person who created the account (it replaces the temporary password shown before).

Only the SHA-256 of a token is stored. A token works once, for INVITE_HOURS. Resending makes the old link stop
working. Revoking also deactivates the not-yet-used account.
"""
from __future__ import annotations

import datetime
import hashlib
import re
import secrets
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.security import TokenPayload, get_password_hash, keycloak_mode
from models.schema import Invitation, User
from services.audit import record_audit
from services.outbox import emit, handler as outbox_handler

INVITE_HOURS = 48
MIN_PASSWORD = 10


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _email_is_live() -> bool:
    return settings.NOTIFY_ADAPTER.lower() == "live"


def invite_link(token: str) -> str:
    # the token travels in the fragment (#), so it never reaches server logs or a Referer header
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/auth/set-password#token={token}"


def _mint(inv: Invitation, now: Optional[datetime.datetime] = None) -> str:
    now = now or datetime.datetime.utcnow()
    token = secrets.token_urlsafe(32)
    inv.token_hash, inv.expires_at, inv.last_sent_at = hash_token(token), now + datetime.timedelta(hours=INVITE_HOURS), now
    return token


def _deliver(db: Session, inv: Invitation, user: User, resend: bool) -> dict:
    """Start delivery for the current send_seq. Returns what the creator's response says."""
    if inv.provider == "keycloak":
        inv.last_sent_at = datetime.datetime.utcnow()
        emit(db, "identity.invite_user", {"user_id": user.id, "resend": resend}, college_id=inv.college_id,
             entity_type="user", entity_id=user.id)
        return {"invite": "Keycloak will email a link to set a password"}
    if _email_is_live():
        inv.token_hash, inv.expires_at = None, None          # the mailer mints the token; an older link stops working now
        emit(db, "invite.send", {"invitation_id": inv.id, "seq": inv.send_seq}, college_id=inv.college_id,
             entity_type="invitation", entity_id=inv.id)
        return {"invite": f"An invitation email is on its way to {user.email}"}
    token = _mint(inv)
    return {"invite_link": invite_link(token), "invite_expires_at": inv.expires_at.isoformat(),
            "invite": "Share this link with them. It works once, for 48 hours."}


def create_invitation(db: Session, user: User, creator: TokenPayload) -> dict:
    """Call right after the new User is flushed. The account gets an unusable random password until accepted."""
    user.hashed_password = get_password_hash(secrets.token_urlsafe(32))
    inv = Invitation(id=f"inv_{uuid.uuid4().hex[:20]}", college_id=user.college_id, user_id=user.id, email=user.email, role=user.role,
                     provider="keycloak" if keycloak_mode() else "local", invited_by=creator.sub,
                     invited_by_name=creator.name or db.execute(select(User.name).where(User.id == creator.sub)).scalar_one_or_none())
    db.add(inv)
    db.flush()
    record_audit(db, creator, "invitation.created", "invitation", inv.id, {"user_id": user.id, "role": user.role}, college_id=user.college_id)
    return {**_deliver(db, inv, user, resend=False), "invitation": invitation_out(inv)}


def invitation_status(inv: Invitation, now: Optional[datetime.datetime] = None) -> str:
    now = now or datetime.datetime.utcnow()
    if inv.accepted_at:
        return "accepted"
    if inv.revoked_at:
        return "revoked"
    if inv.provider == "local" and inv.expires_at and inv.expires_at <= now:
        return "expired"
    return "pending"


def invitation_out(inv: Invitation, name: Optional[str] = None) -> dict:
    return {"id": inv.id, "user_id": inv.user_id, "email": inv.email, "name": name, "role": inv.role, "provider": inv.provider,
            "status": invitation_status(inv), "invited_by": inv.invited_by_name,
            "invited_at": inv.created_at.isoformat() if inv.created_at else None,
            "last_sent_at": inv.last_sent_at.isoformat() if inv.last_sent_at else None,
            "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None, "resends": max(0, (inv.send_seq or 1) - 1)}


def list_invitations(db: Session, college_id: str) -> list:
    rows = db.execute(select(Invitation, User.name).join(User, User.id == Invitation.user_id)
                      .where(Invitation.college_id == college_id).order_by(Invitation.created_at.desc())).all()
    return [invitation_out(i, n) for i, n in rows]


def get_invitation(db: Session, college_id: str, invitation_id: str) -> Invitation:
    inv = db.execute(select(Invitation).where(Invitation.id == invitation_id, Invitation.college_id == college_id)).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return inv


def resend_invitation(db: Session, inv: Invitation, actor: TokenPayload) -> dict:
    """A fresh link (the old one stops working). A revoked invitation can be sent again: that reactivates the account."""
    if inv.accepted_at:
        raise HTTPException(status_code=409, detail="This invitation was already accepted")
    user = db.get(User, inv.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    was_revoked = inv.revoked_at is not None
    inv.revoked_at, inv.send_seq = None, (inv.send_seq or 1) + 1
    if not user.is_active:
        user.is_active = True
        if keycloak_mode():
            emit(db, "identity.set_enabled", {"user_id": user.id, "enabled": True}, college_id=inv.college_id, entity_type="user", entity_id=user.id)
    out = _deliver(db, inv, user, resend=True)
    record_audit(db, actor, "invitation.resent", "invitation", inv.id, {"user_id": user.id, "was_revoked": was_revoked}, college_id=inv.college_id)
    return {**out, "invitation": invitation_out(inv, user.name)}


def revoke_invitation(db: Session, inv: Invitation, actor: TokenPayload) -> dict:
    """The link stops working and the unused account is deactivated (next request, next WebSocket)."""
    if inv.accepted_at:
        raise HTTPException(status_code=409, detail="This invitation was already accepted; deactivate the account instead")
    user = db.get(User, inv.user_id)
    inv.revoked_at, inv.token_hash, inv.expires_at = datetime.datetime.utcnow(), None, None
    if user is not None and user.is_active:
        user.is_active = False
        if keycloak_mode():
            emit(db, "identity.set_enabled", {"user_id": user.id, "enabled": False}, college_id=inv.college_id, entity_type="user", entity_id=user.id)
    record_audit(db, actor, "invitation.revoked", "invitation", inv.id, {"user_id": inv.user_id}, college_id=inv.college_id)
    return {"invitation": invitation_out(inv, user.name if user else None)}


# ---- the invited person ----
def _by_token(db: Session, token: str) -> Invitation:
    """404 for an unknown or used link, 410 for an expired or revoked one. Same 404 for every unknown token."""
    if not token or len(token) > 200:
        raise HTTPException(status_code=404, detail="This invitation link is not valid")
    inv = db.execute(select(Invitation).where(Invitation.token_hash == hash_token(token))).scalar_one_or_none()
    if inv is None or inv.provider != "local" or inv.accepted_at:
        raise HTTPException(status_code=404, detail="This invitation link is not valid or was already used")
    st = invitation_status(inv)
    if st in ("expired", "revoked"):
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail="This invitation has expired. Ask the person who invited you to send it again.")
    return inv


def describe(db: Session, token: str) -> dict:
    from models.schema import College
    inv = _by_token(db, token)
    user = db.get(User, inv.user_id)
    college = db.get(College, inv.college_id)
    return {"email": inv.email, "name": user.name if user else None, "role": inv.role,
            "college": college.name if college else None, "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            "min_length": MIN_PASSWORD}


def check_password(password: str, email: str) -> None:
    """At least MIN_PASSWORD characters, a letter and a digit, and not built from the email name."""
    local = (email or "").split("@")[0].lower()
    if len(password) < MIN_PASSWORD:
        raise HTTPException(status_code=422, detail=f"Use at least {MIN_PASSWORD} characters")
    if len(password) > 128:
        raise HTTPException(status_code=422, detail="Use at most 128 characters")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=422, detail="Use at least one letter and one number")
    if len(local) >= 4 and local in password.lower():
        raise HTTPException(status_code=422, detail="Do not use your email name in the password")


def accept(db: Session, token: str, password: str) -> User:
    """Set the password, mark the invitation accepted and burn the token. Caller issues the session and commits."""
    inv = _by_token(db, token)
    user = db.get(User, inv.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="This invitation link is not valid or was already used")
    check_password(password, user.email)
    user.hashed_password = get_password_hash(password)
    user.failed_logins, user.locked_until = 0, None
    inv.accepted_at, inv.token_hash = datetime.datetime.utcnow(), None
    record_audit(db, TokenPayload(sub=user.id, role=user.role, college_id=user.college_id, email=user.email, name=user.name),
                 "invitation.accepted", "invitation", inv.id, {"user_id": user.id})
    return user


# ---- mailer (local mode with NOTIFY_ADAPTER=live) ----
@outbox_handler("invite.send")
def _send_invitation_email(db: Session, event) -> None:
    """Idempotent: one email per send_seq; a newer resend, a revoke or an acceptance makes an old event a no-op."""
    from services.gateways import real_email, send_email
    inv = db.get(Invitation, (event.payload or {}).get("invitation_id"))
    seq = (event.payload or {}).get("seq")
    if inv is None or inv.accepted_at or inv.revoked_at or inv.send_seq != seq or inv.emailed_seq >= seq:
        return
    user = db.get(User, inv.user_id)
    if user is None or not real_email(user.email):
        inv.emailed_seq = seq
        return
    token = _mint(inv)
    inv.emailed_seq = seq
    db.flush()
    send_email(user.email, "You are invited to IREP Portal",
               f"Hello {user.name},\n\n{inv.invited_by_name or 'Your college'} has created an IREP Portal account for you.\n"
               f"Set your password here (the link works once, for {INVITE_HOURS} hours):\n{invite_link(token)}\n\n"
               f"If you were not expecting this, you can ignore this email.\n\n"
               f"வணக்கம் {user.name}, உங்களுக்கு IREP Portal கணக்கு உருவாக்கப்பட்டுள்ளது. மேலே உள்ள இணைப்பில் கடவுச்சொல்லை அமையுங்கள் "
               f"({INVITE_HOURS} மணி நேரம், ஒருமுறை மட்டும்).")
