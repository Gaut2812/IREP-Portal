"""Keycloak access-token verification (Master Plan: one sign-in for portal, labs and Teams trainers).

Keycloak issues RS256 access tokens. We verify signature (realm JWKS),
issuer, audience and expiry, then map the claims onto the TokenPayload every
router already uses:

    irep_user_id  -> sub          (user attribute mapper; users.id in the portal DB)
    college_id    -> college_id   (user attribute mapper; tenancy)
    realm role    -> role         (exactly one of IREP_ROLES)

The realm (infra/keycloak/realm-irep.json) only lets admins edit those two
attributes, so a user cannot move themselves to another college.
"""
import threading
import time
from typing import Callable, Optional

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt

IREP_ROLES = ("student", "trainer", "parent", "college_admin", "irep_admin")


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


class KeycloakVerifier:
    def __init__(self, issuer: str, audience: str, *, jwks_url: Optional[str] = None,
                 fetch: Optional[Callable[[str], dict]] = None, cache_seconds: int = 300):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.jwks_url = jwks_url or f"{self.issuer}/protocol/openid-connect/certs"
        self._fetch = fetch or (lambda url: httpx.get(url, timeout=5).raise_for_status().json())
        self._cache_seconds = cache_seconds
        self._jwks: Optional[dict] = None
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def _keys(self, force: bool = False) -> dict:
        with self._lock:
            stale = time.monotonic() - self._fetched_at > self._cache_seconds
            if force or self._jwks is None or stale:
                try:
                    self._jwks = self._fetch(self.jwks_url)
                    self._fetched_at = time.monotonic()
                except Exception as exc:  # noqa: BLE001
                    if self._jwks is None:
                        raise HTTPException(status_code=503, detail="Sign-in service unavailable") from exc
            return self._jwks

    def _decode(self, token: str, jwks: dict) -> dict:
        return jwt.decode(token, jwks, algorithms=["RS256"], audience=self.audience, issuer=self.issuer,
                          options={"verify_at_hash": False})

    def claims(self, token: str) -> dict:
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except JWTError as exc:
            raise _unauthorized() from exc
        jwks = self._keys()
        if kid and not any(k.get("kid") == kid for k in jwks.get("keys", [])):
            jwks = self._keys(force=True)          # Keycloak rotated its signing key
        try:
            return self._decode(token, jwks)
        except JWTError as exc:
            raise _unauthorized() from exc

    def payload(self, token: str):
        from core.security import TokenPayload   # local import: security imports this module

        c = self.claims(token)
        roles = [r for r in (c.get("realm_access") or {}).get("roles", []) if r in IREP_ROLES]
        if len(roles) != 1:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="This account needs exactly one IREP role in Keycloak")
        user_id, college_id = c.get("irep_user_id"), c.get("college_id")
        if not user_id or not college_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="This account is not linked to a portal user and college")
        name = c.get("name") or c.get("preferred_username") or ""
        initials = "".join(p[0] for p in name.split()[:2]).upper() or "IR"
        return TokenPayload(sub=user_id, email=c.get("email"), role=roles[0], college_id=college_id,
                            name=name, avatar=initials, exp=c.get("exp"))


_verifier: Optional[KeycloakVerifier] = None


def get_verifier() -> KeycloakVerifier:
    global _verifier
    if _verifier is None:
        from core.config import settings
        _verifier = KeycloakVerifier(settings.KEYCLOAK_ISSUER, settings.KEYCLOAK_AUDIENCE)
    return _verifier


def set_verifier(v: Optional[KeycloakVerifier]) -> None:
    """Tests swap in a verifier with a local key set."""
    global _verifier
    _verifier = v
