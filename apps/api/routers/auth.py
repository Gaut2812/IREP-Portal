"""Screen 01 Sign-in: password login with lockout, parent OTP (hashed,
expiring, rate-limited), language preference. Every outcome is audited."""
import datetime
import hashlib
import hmac
import re
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import verify_password, get_password_hash, create_access_token, get_current_user, TokenPayload, normalize_role, keycloak_mode
from models.schema import AuditLog, User, Student, OtpAttempt
from services.audit import record_audit
from services.notifications import get_notification_adapter

router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
OTP_TTL_MINUTES = 5
OTP_REQUESTS_PER_WINDOW = 5
OTP_WINDOW_MINUTES = 10
OTP_MAX_VERIFY_ATTEMPTS = 5              # per code
OTP_PHONE_FAILS_PER_HOUR = 15            # per mobile number, across codes


class LoginRequest(BaseModel):
    role: str  # student, trainer, college / college_admin, parent
    identifier: str  # email or register number
    password: str


class ParentOTPRequest(BaseModel):
    phone: str


class ParentOTPVerify(BaseModel):
    phone: str
    otp: str


class LanguageIn(BaseModel):
    language: str = Field(pattern="^(en|ta)$")


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _issue(user: User) -> AuthResponse:
    token = create_access_token({
        "sub": user.id, "email": user.email, "role": user.role, "college_id": user.college_id,
        "name": user.name, "avatar": user.avatar_initials,
    })
    return AuthResponse(access_token=token, user={
        "id": user.id, "email": user.email, "role": user.role, "name": user.name, "avatar": user.avatar_initials,
        "college_id": user.college_id, "language_pref": user.language_pref,
    })


def _as_payload(user: User) -> TokenPayload:
    return TokenPayload(sub=user.id, role=user.role, college_id=user.college_id, email=user.email, name=user.name)


def _sign_in_group(role: Optional[str]) -> Optional[str]:
    """Which sign-in card a role uses: both college roles use the college card."""
    r = normalize_role(role)
    return "college_admin" if r == "placement_officer" else r


def _find_user(db: Session, identifier: str) -> Optional[User]:
    ident = identifier.strip()
    if "@" in ident:
        return db.execute(select(User).filter_by(email=ident.lower())).scalar_one_or_none() or db.execute(select(User).filter_by(email=ident)).scalar_one_or_none()
    student = db.execute(select(Student).filter_by(register_no=ident)).scalar_one_or_none()
    return db.execute(select(User).filter_by(id=student.user_id)).scalar_one_or_none() if student else None


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Wrong role or unknown account gets the same message as a wrong password
    (no account probing). Five failures lock the account for 15 minutes."""
    if keycloak_mode():
        # one password store: Keycloak owns staff and student credentials
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Password sign-in moved to single sign-on. Use 'Sign in with IREP account'.")
    now = datetime.datetime.utcnow()
    user = _find_user(db, req.identifier)
    ip = _client_ip(request)
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials. Check your ID and password.")
    if not user or _sign_in_group(user.role) != _sign_in_group(req.role) or user.role == "parent":
        record_audit(db, None, "auth.login_failed", "user", user.id if user else None, {"reason": "unknown_or_role", "role": req.role}, college_id=user.college_id if user else "unknown", ip_address=ip)
        db.commit()
        raise invalid
    if user.locked_until and user.locked_until > now:
        mins = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        record_audit(db, None, "auth.login_locked", "user", user.id, None, college_id=user.college_id, ip_address=ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Account locked after too many failed attempts. Try again in {mins} minutes.")
    if not verify_password(req.password, user.hashed_password):
        user.failed_logins = (user.failed_logins or 0) + 1
        left = MAX_FAILED_LOGINS - user.failed_logins
        action = "auth.login_failed"
        if left <= 0:
            user.locked_until, user.failed_logins, action = now + datetime.timedelta(minutes=LOCKOUT_MINUTES), 0, "auth.account_locked"
        record_audit(db, None, action, "user", user.id, {"reason": "password"}, college_id=user.college_id, ip_address=ip)
        db.commit()
        if left <= 0:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Account locked after too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid credentials. {left} attempt{'s' if left != 1 else ''} left before the account is locked.")
    if not user.is_active:
        # checked only after the password, so a deactivated account cannot be probed
        record_audit(db, None, "auth.login_inactive", "user", user.id, None, college_id=user.college_id, ip_address=ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This account is deactivated. Contact your college office.")
    user.failed_logins, user.locked_until = 0, None
    record_audit(db, _as_payload(user), "auth.login", "user", user.id, {"method": "password"}, ip_address=ip)
    db.commit()
    return _issue(user)


# ---- parent OTP ----
def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10:
        raise HTTPException(status_code=422, detail="Enter a 10-digit mobile number")
    return digits


def _phone_hash(phone: str) -> str:
    """Keyed hash: the mobile number is never stored; without the server key it cannot be brute-forced."""
    return hmac.new(settings.JWT_SECRET_KEY.encode(), f"phone|{phone}".encode(), hashlib.sha256).hexdigest()


def _too_many(n: int, limit: int, minutes: int, what: str) -> None:
    if n >= limit:
        raise HTTPException(status_code=429, detail=f"Too many {what}. Try again in {minutes} minutes.",
                            headers={"Retry-After": str(minutes * 60)})


def _ip_count(db: Session, action: str, ip: Optional[str], since: datetime.datetime) -> int:
    if not ip:
        return 0
    return db.execute(select(func.count(AuditLog.id)).where(AuditLog.action == action, AuditLog.ip_address == ip,
                                                            AuditLog.created_at >= since)).scalar_one()


def _phone_fails(db: Session, ph: str, now: datetime.datetime) -> int:
    return db.execute(select(func.coalesce(func.sum(OtpAttempt.verify_attempts), 0)).where(
        OtpAttempt.phone_hash == ph, OtpAttempt.created_at >= now - datetime.timedelta(hours=1))).scalar_one()


def _parent_by_phone(db: Session, phone: str) -> Optional[User]:
    # deactivated parents are treated like an unknown number
    return db.execute(select(User).filter_by(role="parent", phone=phone, is_active=True)).scalars().first()


@router.post("/parent/otp/request")
def request_parent_otp(req: ParentOTPRequest, request: Request, db: Session = Depends(get_db)):
    phone = _normalize_phone(req.phone)
    ph = _phone_hash(phone)
    now = datetime.datetime.utcnow()
    recent = db.execute(select(func.count(OtpAttempt.id)).where(OtpAttempt.phone_hash == ph, OtpAttempt.created_at >= now - datetime.timedelta(minutes=OTP_WINDOW_MINUTES))).scalar_one()
    parent = _parent_by_phone(db, phone)
    college_id = parent.college_id if parent else "unknown"
    ip = _client_ip(request)
    window = now - datetime.timedelta(minutes=OTP_WINDOW_MINUTES)
    limited = (recent >= OTP_REQUESTS_PER_WINDOW
               or _ip_count(db, "auth.otp_requested", ip, window) >= settings.OTP_IP_REQUESTS_PER_WINDOW
               or _phone_fails(db, ph, now) >= OTP_PHONE_FAILS_PER_HOUR)
    if limited:
        record_audit(db, None, "auth.otp_rate_limited", "phone", ph[:16], None, college_id=college_id, ip_address=ip)
        db.commit()
        _too_many(1, 1, OTP_WINDOW_MINUTES, "OTP requests")
    # a new code replaces every earlier one for this number
    db.execute(update(OtpAttempt).where(OtpAttempt.phone_hash == ph, OtpAttempt.consumed.is_(False)).values(consumed=True))
    otp = f"{secrets.randbelow(1_000_000):06d}"                  # CSPRNG
    db.add(OtpAttempt(id=f"otp_{uuid.uuid4().hex[:20]}", college_id=college_id, phone_hash=ph, otp_hash=get_password_hash(otp),
                      expires_at=now + datetime.timedelta(minutes=OTP_TTL_MINUTES), created_at=now, updated_at=now))
    channel = None
    if parent:
        # Sent directly (never through the outbox): an outbox row would hold the code in plain text.
        # Email by default; SMS only when PARENT_OTP_CHANNEL=sms and SMS_PROVIDER=msg91.
        if (settings.NOTIFY_ADAPTER or "fake").lower() == "live":
            from services.gateways import GatewayError, send_parent_otp
            try:
                channel = send_parent_otp(parent, otp, OTP_TTL_MINUTES)
            except GatewayError:
                db.rollback()
                raise HTTPException(status_code=503, detail="We could not send the code just now. Try again in a minute or contact the college office.")
        else:
            get_notification_adapter().deliver(parent, "sms", "IREP sign-in OTP", f"Your IREP OTP is {otp}. Valid for {OTP_TTL_MINUTES} minutes.")
            channel = "demo"
    record_audit(db, None, "auth.otp_requested", "phone", ph[:16], {"known": bool(parent), "channel": channel}, college_id=college_id, ip_address=_client_ip(request))
    db.commit()
    where = "to the email address registered with the college" if settings.PARENT_OTP_CHANNEL.lower() == "email" else "by SMS"
    where_ta = "கல்லூரியில் பதிவு செய்த மின்னஞ்சலுக்கு" if settings.PARENT_OTP_CHANNEL.lower() == "email" else "SMS மூலம்"
    out = {"success": True, "message": f"If this number is registered, a code has been sent {where}. It is valid for {OTP_TTL_MINUTES} minutes.",
           "message_ta": f"இந்த எண் பதிவு செய்யப்பட்டிருந்தால், குறியீடு {where_ta} அனுப்பப்பட்டது. இது {OTP_TTL_MINUTES} நிமிடங்கள் செல்லுபடியாகும்.",
           "expires_in": OTP_TTL_MINUTES * 60, "channel": settings.PARENT_OTP_CHANNEL.lower()}
    if settings.ENVIRONMENT == "development":
        out["demo_otp"] = otp
    return out


@router.post("/parent/otp/verify", response_model=AuthResponse)
def verify_parent_otp(req: ParentOTPVerify, request: Request, db: Session = Depends(get_db)):
    phone = _normalize_phone(req.phone)
    ph = _phone_hash(phone)
    now = datetime.datetime.utcnow()
    ip = _client_ip(request)
    _too_many(_ip_count(db, "auth.otp_failed", ip, now - datetime.timedelta(minutes=OTP_WINDOW_MINUTES)),
              settings.OTP_IP_VERIFY_FAILS_PER_WINDOW, OTP_WINDOW_MINUTES, "wrong codes from this network")
    _too_many(_phone_fails(db, ph, now), OTP_PHONE_FAILS_PER_HOUR, 60, "wrong codes for this number")
    attempt = db.execute(select(OtpAttempt).filter_by(phone_hash=ph, consumed=False).order_by(OtpAttempt.created_at.desc())).scalars().first()
    if not attempt or attempt.expires_at < now:
        raise HTTPException(status_code=400, detail="OTP expired or not requested. Request a new OTP.")
    # Reserve one attempt atomically before checking, so parallel guesses cannot exceed the limit.
    reserved = db.execute(update(OtpAttempt).where(OtpAttempt.id == attempt.id, OtpAttempt.consumed.is_(False),
                                                   OtpAttempt.verify_attempts < OTP_MAX_VERIFY_ATTEMPTS)
                          .values(verify_attempts=OtpAttempt.verify_attempts + 1)).rowcount
    db.commit()
    if not reserved:
        raise HTTPException(status_code=429, detail="Too many wrong OTP attempts. Request a new OTP.")
    db.refresh(attempt)
    code = req.otp.strip()
    if not re.fullmatch(r"\d{6}", code) or not verify_password(code, attempt.otp_hash):    # bcrypt: constant time
        left = OTP_MAX_VERIFY_ATTEMPTS - attempt.verify_attempts
        record_audit(db, None, "auth.otp_failed", "phone", ph[:16], {"left": left}, college_id=attempt.college_id, ip_address=ip)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Incorrect OTP. {left} attempt{'s' if left != 1 else ''} left.")
    # single use: only one request can flip consumed for this code
    if not db.execute(update(OtpAttempt).where(OtpAttempt.id == attempt.id, OtpAttempt.consumed.is_(False))
                      .values(consumed=True, verify_attempts=OtpAttempt.verify_attempts - 1)).rowcount:
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired or not requested. Request a new OTP.")
    parent = _parent_by_phone(db, phone)
    if not parent:
        db.commit()
        raise HTTPException(status_code=404, detail="This mobile number is not linked to a parent account. Contact the college office.")
    record_audit(db, _as_payload(parent), "auth.login", "user", parent.id, {"method": "otp"}, ip_address=_client_ip(request))
    db.commit()
    return _issue(parent)


@router.get("/me")
def get_me(current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    """The caller's token claims plus the portal profile (id, language) the
    web app stores after sign-in. Used after the Keycloak redirect."""
    out = current_user.model_dump()
    user = db.execute(select(User).filter_by(id=current_user.sub, college_id=current_user.college_id)).scalar_one_or_none()
    out["id"] = current_user.sub
    out["language_pref"] = user.language_pref if user else "en"
    if user:
        out["name"] = out.get("name") or user.name
        out["avatar"] = out.get("avatar") or user.avatar_initials
    return out


@router.get("/config")
def auth_config():
    """Public sign-in settings for the web app (no secrets)."""
    if not keycloak_mode():
        return {"provider": "local"}
    return {"provider": "keycloak", "issuer": settings.KEYCLOAK_ISSUER, "client_id": "irep-web",
            "parent_sign_in": "otp"}


@router.put("/me/language")
def set_language(req: LanguageIn, current_user: TokenPayload = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.execute(select(User).filter_by(id=current_user.sub, college_id=current_user.college_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.language_pref = req.language
    record_audit(db, current_user, "user.language", "user", user.id, {"language": req.language})
    db.commit()
    return {"success": True, "language_pref": user.language_pref}
