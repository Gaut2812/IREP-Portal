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
    try:
        # Check if stored as plain text for demo fallback
        if plain_password == hashed_password:
            return True
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return plain_password == hashed_password

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

DEMO_PROFILES = {
    "student": dict(sub="usr_priya_01", email="priya.r@demo.edu", role="student", name="Priya R", avatar="PR"),
    "trainer": dict(sub="usr_arun_01", email="arun.k@demo.edu", role="trainer", name="Arun Kumar", avatar="AK"),
    "college_admin": dict(sub="usr_kavitha_01", email="admin@demo.edu", role="college_admin", name="Dr. Kavitha", avatar="DC"),
    "parent": dict(sub="usr_ramesh_01", email="ramesh.k@example.com", role="parent", name="Mr. Ramesh K", avatar="RK"),
}
# The web app uses the short role name "college"; the API role is college_admin.
ROLE_ALIASES = {"college": "college_admin"}


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
    payload = decode_access_token(token) if token else None
    if payload:
        return payload

    if settings.ENVIRONMENT.lower() == "production":
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
        if normalize_role(current_user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker
