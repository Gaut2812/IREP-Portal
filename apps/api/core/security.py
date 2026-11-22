import datetime
import bcrypt
from typing import Optional, List
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/token", auto_error=False)

class TokenPayload(BaseModel):
    sub: str
    email: Optional[str] = None
    role: str
    college_id: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    exp: Optional[int] = None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """bcrypt only (constant-time inside checkpw). A stored value that is not a bcrypt hash never
    matches: no plain-text fallback, so a leaked hash cannot be replayed as a password."""
    if not plain_password or not hashed_password or not hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[TokenPayload]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        return TokenPayload(**payload)
    except JWTError:
        return None

def keycloak_mode() -> bool:
    return settings.AUTH_PROVIDER.lower() == "keycloak"


def _payload_from_token(token: str) -> Optional[TokenPayload]:
    """Local HS256 token, or (AUTH_PROVIDER=keycloak) a Keycloak RS256 token.

    In Keycloak mode a local token is honoured only for parents, who still
    sign in with the API's OTP until Keycloak gets SMS OTP.
    """
    if keycloak_mode():
        try:
            alg = jwt.get_unverified_header(token).get("alg")
        except JWTError:
            return None
        if alg == "RS256":
            from core.keycloak import get_verifier
            return get_verifier().payload(token)   # raises 401/403 itself
        local = decode_access_token(token)
        return local if local and local.role == "parent" else None
    return decode_access_token(token)


DEMO_PROFILES = {
    "student": dict(sub="usr_priya_01", email="priya.r@demo.edu", role="student", name="Priya R", avatar="PR"),
    "trainer": dict(sub="usr_arun_01", email="arun.k@demo.edu", role="trainer", name="Arun Kumar", avatar="AK"),
    "college_admin": dict(sub="usr_kavitha_01", email="admin@demo.edu", role="college_admin", name="Dr. Kavitha", avatar="DC"),
    "parent": dict(sub="usr_ramesh_01", email="ramesh.k@example.com", role="parent", name="Mr. Ramesh K", avatar="RK"),
}
# The web app uses short role names ("college", "admin"). IREP staff are "irep_admin";
# "super_admin" sits above them (docs/PERMISSIONS.md): it passes every irep_admin check and alone
# manages staff accounts, MoU terms, feature switches, billing, deletion approvals and support sessions.
ROLE_ALIASES = {"college": "college_admin", "admin": "irep_admin"}
STAFF_ROLES = ("irep_admin", "super_admin")
# IREP staff are not in any college: their token carries the platform tenant.
PLATFORM_TENANT = "irep_platform"


def normalize_role(role: Optional[str]) -> Optional[str]:
    if not role:
        return role
    return ROLE_ALIASES.get(role, role)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_demo_role: Optional[str] = Header(default=None, alias="X-Demo-Role"),
) -> TokenPayload:
    """Resolve the caller from the bearer JWT.

    Development only: a missing or undecodable token falls back to a seeded
    demo profile. The role comes from the optional X-Demo-Role header and
    defaults to the demo student, which keeps local smoke tests and the
    Playwright specs working without a login round-trip. In production an
    invalid token is always a 401.
    """
    payload = _payload_from_token(token) if token else None
    if payload:
        # A deactivated (or deleted) account is refused at once, not when its token expires.
        from starlette.concurrency import run_in_threadpool
        from core.active_users import is_active
        if not await run_in_threadpool(is_active, payload.sub):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This account is deactivated",
                                headers={"WWW-Authenticate": "Bearer"})
        return payload

    # A token that is present but invalid or expired is always a 401, even in
    # development: falling back to the demo student would show one user
    # another user's data (e.g. notifications).
    if token or settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = normalize_role((x_demo_role or "student").strip().lower()) or "student"
    profile = DEMO_PROFILES.get(role, DEMO_PROFILES["student"])
    return TokenPayload(college_id=settings.DEFAULT_COLLEGE_ID, **profile)


def require_role(allowed_roles: List[str]):
    def role_checker(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        allowed = {normalize_role(r) for r in allowed_roles}
        if "irep_admin" in allowed:
            allowed.add("super_admin")                 # super_admin is above IREP staff
        if normalize_role(current_user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


def is_staff(role: Optional[str]) -> bool:
    return normalize_role(role) in STAFF_ROLES


def is_super_admin(user: TokenPayload) -> bool:
    return normalize_role(user.role) == "super_admin"


# Only the super admin: staff accounts, MoU terms, feature switches, billing, deletion approvals,
# support sessions. Every request a super admin makes is also audited (main.py).
SUPER = require_role(["super_admin"])


def websocket_user(token: Optional[str]) -> Optional[TokenPayload]:
    """The caller of a WebSocket (?token=...): the same checks as a request (local or Keycloak
    token, then "still active"). None means close the socket with 4401."""
    if not token:
        return None
    try:
        payload = _payload_from_token(token)
    except HTTPException:
        return None
    if payload is None:
        return None
    from core.active_users import is_active
    return payload if is_active(payload.sub) else None
