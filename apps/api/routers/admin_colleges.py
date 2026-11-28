"""Screen 45 · Colleges and MoU terms (IREP staff). Spec: docs/screens/45-colleges-and-mou.md

IREP staff work across colleges by design (admin sits at the edge and
configures the system); every change is audited. Everyone else gets 403.
"""
import datetime
import re
import secrets
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import SUPER, TokenPayload, get_password_hash, is_super_admin, keycloak_mode, require_role
from models.schema import Batch, Branch, College, Invoice, MouTerm, Student, User
from services.audit import record_audit
from services.invitations import INVITE_HOURS, create_invitation, get_invitation, list_invitations, resend_invitation, revoke_invitation
from services.outbox import emit, handler as outbox_handler

router = APIRouter(prefix="/admin/colleges", tags=["Screen 45 · Colleges and MoU"])
STAFF = require_role(["irep_admin"])      # IREP staff and the super admin
# MoU terms (incl. fees) and feature switches: super admin only (docs/PERMISSIONS.md)

FEATURE_DEFAULTS: Dict[str, bool] = {
    "virtual_labs": True,
    "cyber_range": False,
    "ai_study_buddy": False,
    "parent_sms": False,
    "whatsapp": False,
    "teams_live_classes": True,
}
CODE_RE = re.compile(r"^[A-Za-z0-9]{2,16}$")


# ---- payloads ----
class CollegeIn(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    code: str
    city: str = Field(min_length=2, max_length=128)
    state: str = Field(min_length=2, max_length=128)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        if not CODE_RE.match(v.strip()):
            raise ValueError("Code must be 2-16 letters or digits")
        return v.strip().upper()


class FeaturesIn(BaseModel):
    features: Dict[str, bool]


class MouIn(BaseModel):
    starts_on: datetime.date
    ends_on: datetime.date
    students_cap: int = Field(gt=0, le=100_000)
    lab_hours_per_student: int = Field(ge=0, le=2_000, default=40)
    ai_calls_per_day: int = Field(ge=0, le=1_000, default=30)
    storage_gb: int = Field(ge=0, le=100_000, default=50)
    fee_per_student_inr: int = Field(ge=0, le=10_000_000, default=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    activate: bool = True


class AdminIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=32)


# ---- helpers ----
def _college(db: Session, college_id: str) -> College:
    c = db.get(College, college_id)
    if c is None:
        raise HTTPException(status_code=404, detail="College not found")
    return c


def _features(c: College) -> Dict[str, bool]:
    return {**FEATURE_DEFAULTS, **{k: bool(v) for k, v in (c.features or {}).items() if k in FEATURE_DEFAULTS}}


def _mou_out(m: MouTerm) -> dict:
    return {"id": m.id, "starts_on": m.starts_on.isoformat(), "ends_on": m.ends_on.isoformat(), "students_cap": m.students_cap,
            "lab_hours_per_student": m.lab_hours_per_student, "ai_calls_per_day": m.ai_calls_per_day, "storage_gb": m.storage_gb,
            "fee_per_student_inr": m.fee_per_student_inr, "status": m.status, "notes": m.notes}


def _admins(db: Session, college_id: str):
    return db.execute(select(User).where(User.college_id == college_id, User.role == "college_admin").order_by(User.name)).scalars().all()


def _refresh_status(db: Session, c: College) -> None:
    """Onboarding until the college has an active MoU and a college admin."""
    if c.status == "suspended":
        return
    has_mou = db.execute(select(MouTerm.id).where(MouTerm.college_id == c.id, MouTerm.status == "active")).first() is not None
    has_admin = bool(_admins(db, c.id))
    c.status = "active" if has_mou and has_admin else "onboarding"


# ---- endpoints ----
@router.get("")
def list_colleges(current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    colleges = db.execute(select(College).order_by(College.name)).scalars().all()
    students = dict(db.execute(select(Student.college_id, func.count(Student.id)).group_by(Student.college_id)).all())
    admins = dict(db.execute(select(User.college_id, func.count(User.id)).where(User.role == "college_admin").group_by(User.college_id)).all())
    active = {m.college_id: m for m in db.execute(select(MouTerm).where(MouTerm.status == "active")).scalars()}
    return {"colleges": [{
        "id": c.id, "name": c.name, "code": c.code, "city": c.city, "state": c.state, "status": c.status,
        "students": students.get(c.id, 0), "admins": admins.get(c.id, 0),
        "mou_ends_on": active[c.id].ends_on.isoformat() if c.id in active else None,
        "students_cap": active[c.id].students_cap if c.id in active else None,
    } for c in colleges]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_college(req: CollegeIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    if db.execute(select(College.id).where(func.upper(College.code) == req.code)).first():
        raise HTTPException(status_code=409, detail=f"A college with code {req.code} already exists")
    cid = f"col_{req.code.lower()}_{uuid.uuid4().hex[:6]}"
    c = College(id=cid, college_id=cid, name=req.name.strip(), code=req.code, city=req.city.strip(), state=req.state.strip(),
                status="onboarding", features=dict(FEATURE_DEFAULTS))
    db.add(c)
    db.flush()
    record_audit(db, current_user, "college.created", "college", cid, {"code": req.code, "name": c.name}, college_id=cid)
    db.commit()
    return {"id": cid, "status": c.status}


@router.get("/{college_id}")
def college_detail(college_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    mous = db.execute(select(MouTerm).where(MouTerm.college_id == c.id).order_by(MouTerm.created_at.desc())).scalars().all()
    students = db.execute(select(func.count(Student.id)).where(Student.college_id == c.id)).scalar_one()
    return {
        "college": {"id": c.id, "name": c.name, "code": c.code, "city": c.city, "state": c.state, "status": c.status, "students": students},
        "features": _features(c),
        "mou_terms": [_mou_out(m) for m in mous],
        "admins": [{"id": u.id, "name": u.name, "email": u.email, "phone": u.phone} for u in _admins(db, c.id)],
        "can_manage": is_super_admin(current_user),       # MoU terms and feature switches
    }


@router.put("/{college_id}/features")
def set_features(college_id: str, req: FeaturesIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    unknown = sorted(set(req.features) - set(FEATURE_DEFAULTS))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown feature switches: {', '.join(unknown)}")
    before = _features(c)
    after = {**before, **req.features}
    c.features = after
    changed = {k: v for k, v in after.items() if before.get(k) != v}
    record_audit(db, current_user, "college.features_changed", "college", c.id, {"changed": changed}, college_id=c.id)
    db.commit()
    return {"features": _features(c)}


@router.post("/{college_id}/mou", status_code=status.HTTP_201_CREATED)
def create_mou(college_id: str, req: MouIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    if req.ends_on <= req.starts_on:
        raise HTTPException(status_code=422, detail="The MoU must end after it starts")
    m = MouTerm(id=f"mou_{uuid.uuid4().hex[:16]}", college_id=c.id, starts_on=req.starts_on, ends_on=req.ends_on,
                students_cap=req.students_cap, lab_hours_per_student=req.lab_hours_per_student, ai_calls_per_day=req.ai_calls_per_day,
                storage_gb=req.storage_gb, fee_per_student_inr=req.fee_per_student_inr, notes=req.notes,
                status="draft", created_by=current_user.sub)
    db.add(m)
    db.flush()
    record_audit(db, current_user, "mou.created", "mou", m.id, _mou_out(m), college_id=c.id)
    if req.activate:
        _activate(db, current_user, c, m)
    db.commit()
    return _mou_out(m)


@router.post("/{college_id}/mou/{mou_id}/activate")
def activate_mou(college_id: str, mou_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    m = db.execute(select(MouTerm).where(MouTerm.id == mou_id, MouTerm.college_id == c.id)).scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="MoU not found")
    _activate(db, current_user, c, m)
    db.commit()
    return _mou_out(m)


@router.delete("/{college_id}/mou/{mou_id}")
def delete_mou(college_id: str, mou_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    """Delete a draft or superseded MoU. The active one sets quotas and billing: activate another one first.
    An MoU an invoice was billed against stays (the invoice must keep its terms)."""
    c = _college(db, college_id)
    m = db.execute(select(MouTerm).where(MouTerm.id == mou_id, MouTerm.college_id == c.id)).scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="MoU not found")
    if m.status == "active":
        raise HTTPException(status_code=409, detail="This is the active MoU; activate another MoU before deleting it")
    if db.execute(select(Invoice.id).where(Invoice.mou_id == m.id)).first():
        raise HTTPException(status_code=409, detail="Invoices were billed against this MoU, so it is kept on record")
    record_audit(db, current_user, "mou.deleted", "mou", m.id, _mou_out(m), college_id=c.id)
    db.delete(m)
    db.commit()
    return {"success": True}


@router.delete("/{college_id}")
def delete_college(college_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    """Delete a college that holds no people or records yet (for example, one created by mistake). A college
    with users, students, structure or invoices is refused: personal data leaves only through a deletion request."""
    c = _college(db, college_id)
    in_use = {
        "users": db.execute(select(func.count(User.id)).where(User.college_id == c.id)).scalar_one(),
        "students": db.execute(select(func.count(Student.id)).where(Student.college_id == c.id)).scalar_one(),
        "branches": db.execute(select(func.count(Branch.id)).where(Branch.college_id == c.id)).scalar_one(),
        "batches": db.execute(select(func.count(Batch.id)).where(Batch.college_id == c.id)).scalar_one(),
        "invoices": db.execute(select(func.count(Invoice.id)).where(Invoice.college_id == c.id)).scalar_one(),
    }
    used = {k: v for k, v in in_use.items() if v}
    if used:
        detail = ", ".join(f"{v} {k}" for k, v in used.items())
        raise HTTPException(status_code=409, detail=f"This college still has {detail}; only an empty college can be deleted")
    for m in db.execute(select(MouTerm).where(MouTerm.college_id == c.id)).scalars():
        db.delete(m)
    db.flush()
    record_audit(db, current_user, "college.deleted", "college", c.id, {"code": c.code, "name": c.name}, college_id=c.id)
    db.delete(c)
    db.commit()
    return {"success": True}


def _activate(db: Session, user: TokenPayload, c: College, m: MouTerm) -> None:
    for old in db.execute(select(MouTerm).where(MouTerm.college_id == c.id, MouTerm.status == "active", MouTerm.id != m.id)).scalars():
        old.status = "superseded"
    m.status = "active"
    db.flush()
    record_audit(db, user, "mou.activated", "mou", m.id, {"students_cap": m.students_cap, "ends_on": m.ends_on.isoformat()}, college_id=c.id)
    _refresh_status(db, c)


@router.post("/{college_id}/admins", status_code=status.HTTP_201_CREATED)
def create_college_admin(college_id: str, req: AdminIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    email = req.email.strip().lower()
    if db.execute(select(User.id).where(func.lower(User.email) == email)).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    name = req.name.strip()
    initials = "".join(p[0] for p in name.split()[:2]).upper() or "CA"
    u = User(id=f"usr_{uuid.uuid4().hex[:16]}", college_id=c.id, email=email, name=name, phone=req.phone, role="college_admin",
             avatar_initials=initials, language_pref="en",
             # unusable until the invitation is accepted (Keycloak mode: Keycloak owns the credential)
             hashed_password=get_password_hash(secrets.token_urlsafe(32)))
    db.add(u)
    db.flush()
    record_audit(db, current_user, "college.admin_created", "user", u.id, {"email": email}, college_id=c.id)
    invite = create_invitation(db, u, current_user)        # Phase 5: a set-password link, not a temporary password
    _refresh_status(db, c)
    db.commit()
    return {"id": u.id, "email": email, "college_status": c.status, **invite}


@router.get("/{college_id}/invitations")
def college_invitations_for_staff(college_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    return {"items": list_invitations(db, c.id), "valid_hours": INVITE_HOURS}


@router.post("/{college_id}/invitations/{invitation_id}/resend")
def staff_resend_invitation(college_id: str, invitation_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    out = resend_invitation(db, get_invitation(db, c.id, invitation_id), current_user)
    db.commit()
    return out


@router.post("/{college_id}/invitations/{invitation_id}/revoke")
def staff_revoke_invitation(college_id: str, invitation_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    c = _college(db, college_id)
    out = revoke_invitation(db, get_invitation(db, c.id, invitation_id), current_user)
    db.commit()
    return out


@outbox_handler("identity.invite_user")
def _invite_in_keycloak(db: Session, event) -> None:
    """Provision the portal user in Keycloak (required actions: set password, verify email)."""
    import os
    from services.keycloak_admin import admin_from_env

    u = db.get(User, event.payload["user_id"])
    if u is None:
        return
    first, _, last = (u.name or u.email).partition(" ")
    rep = {"username": u.email, "email": u.email, "emailVerified": False, "enabled": True, "firstName": first, "lastName": last or "-",
           "attributes": {"irep_user_id": [u.id], "college_id": [u.college_id]}}
    admin_from_env().invite(rep, u.role, send_email=os.getenv("KEYCLOAK_INVITE_EMAIL", "false").lower() == "true",
                            resend=bool((event.payload or {}).get("resend")))
