"""Live Keycloak round trip (opt-in): KEYCLOAK_IT=1 with infra/keycloak running
and `python seed/sync_keycloak.py` done.

Does what the browser does: authorization-code + PKCE against the real login
form, then calls the API in AUTH_PROVIDER=keycloak mode with that token.
"""
import base64
import hashlib
import html
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from typing import Optional

import httpx
import pytest

pytestmark = pytest.mark.skipif(os.getenv("KEYCLOAK_IT") != "1", reason="set KEYCLOAK_IT=1 with Keycloak running")

KC = os.getenv("KEYCLOAK_URL", "http://localhost:8081")
ISSUER = f"{KC}/realms/irep"
REDIRECT = "http://localhost:3000/auth/callback"


def totp(secret: str, offset: int = 0) -> str:
    """RFC 6238 (HMAC-SHA1, 6 digits, 30 s): what an authenticator app shows. `secret` is Keycloak's
    raw secret (the hidden totpSecret field); the app gets the same bytes base32-encoded."""
    import hmac
    import struct
    import time
    h = hmac.new(secret.encode(), struct.pack(">Q", int(time.time() // 30) + offset), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def _form(page: str) -> str:
    return html.unescape(re.search(r'<form[^>]*action="([^"]+)"', page).group(1))


def staff_sign_in(username: str, password: str, *, secret: Optional[str] = None, avoid: Optional[str] = None) -> dict:
    """Sign in as IREP staff (two-factor). First time (secret=None): set up the authenticator and return
    its secret with the tokens. Later: answer the OTP prompt with a fresh code."""
    import time
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    with httpx.Client(follow_redirects=False, timeout=15) as s:
        def cookie():
            return {"Cookie": "; ".join(f"{c.name}={c.value}" for c in s.cookies.jar)}

        def follow(r):
            # Keycloak may redirect to its own pages (e.g. the required "configure OTP" action)
            while r.status_code == 302 and not r.headers["location"].startswith(REDIRECT):
                r = s.get(r.headers["location"], headers=cookie())
            return r

        def post(action, data):
            return follow(s.post(action, data=data, headers=cookie()))
        r = s.get(f"{ISSUER}/protocol/openid-connect/auth", params={
            "client_id": "irep-web", "response_type": "code", "scope": "openid", "redirect_uri": REDIRECT,
            "state": "st", "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "login"})
        r = post(_form(r.text), {"username": username, "password": password, "credentialId": ""})
        assert r.status_code == 200, f"expected the two-factor step, got {r.status_code}"
        if secret is None:                                   # authenticator set-up page
            secret = re.search(r'name="totpSecret"\s+value="([^"]+)"', r.text).group(1)
            code = totp(secret)
            r = post(_form(r.text), {"totp": code, "totpSecret": secret, "userLabel": "ci"})
        else:                                                # OTP prompt
            assert 'name="otp"' in r.text
            while totp(secret) == avoid:                     # Keycloak refuses the same code twice
                time.sleep(1)
            code = totp(secret)
            r = post(_form(r.text), {"otp": code, "login": "Sign In"})
        assert r.status_code == 302, r.text[:300]
        code_param = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
        tok = s.post(f"{ISSUER}/protocol/openid-connect/token", data={
            "grant_type": "authorization_code", "client_id": "irep-web", "code": code_param,
            "redirect_uri": REDIRECT, "code_verifier": verifier})
        tok.raise_for_status()
        return {**tok.json(), "secret": secret, "used": code}


def browser_sign_in(username: str, password: str) -> dict:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    with httpx.Client(follow_redirects=False, timeout=15) as s:
        r = s.get(f"{ISSUER}/protocol/openid-connect/auth", params={
            "client_id": "irep-web", "response_type": "code", "scope": "openid", "redirect_uri": REDIRECT,
            "state": "st", "code_challenge": challenge, "code_challenge_method": "S256"})
        assert r.status_code == 200, r.text[:300]
        action = html.unescape(re.search(r'action="([^"]+)"', r.text).group(1))
        # Keycloak's session cookies are Secure; browsers still send them to
        # http://localhost, httpx does not, so forward them as a browser would.
        cookie = "; ".join(f"{c.name}={c.value}" for c in s.cookies.jar)
        r = s.post(action, data={"username": username, "password": password, "credentialId": ""},
                   headers={"Cookie": cookie})
        if r.status_code != 302:
            return {"error": "login_failed", "status": r.status_code}
        loc = r.headers["location"]
        assert loc.startswith(REDIRECT), loc
        code = parse_qs(urlparse(loc).query)["code"][0]
        tok = s.post(f"{ISSUER}/protocol/openid-connect/token", data={
            "grant_type": "authorization_code", "client_id": "irep-web", "code": code,
            "redirect_uri": REDIRECT, "code_verifier": verifier})
        tok.raise_for_status()
        return tok.json()


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from core import keycloak
    from core.config import settings
    from main import app

    monkeypatch.setattr(settings, "AUTH_PROVIDER", "keycloak")
    monkeypatch.setattr(settings, "KEYCLOAK_URL", KC)
    keycloak.set_verifier(None)
    yield TestClient(app)
    keycloak.set_verifier(None)


def test_student_signs_in_through_keycloak_and_reaches_their_dashboard(api):
    tokens = browser_sign_in("priya.r@demo.edu", "password123")
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = api.get("/api/v1/auth/me", headers=h).json()
    assert (me["id"], me["role"], me["college_id"]) == ("usr_priya_01", "student", "col_demo_001")
    assert api.get("/api/v1/student/dashboard", headers=h).json()["student"]["id"] == "std_priya_01"
    assert api.get("/api/v1/trainer/dashboard", headers=h).status_code == 403


def test_trainer_and_college_roles_come_from_the_realm(api):
    for user, ok, denied in [("arun.k@demo.edu", "/api/v1/trainer/dashboard", "/api/v1/college/overview"),
                             ("admin@demo.edu", "/api/v1/college/overview", "/api/v1/trainer/dashboard")]:
        h = {"Authorization": f"Bearer {browser_sign_in(user, 'password123')['access_token']}"}
        assert api.get(ok, headers=h).status_code == 200
        assert api.get(denied, headers=h).status_code == 403


def test_irep_staff_reach_screen_45_with_a_keycloak_token(api):
    """IREP staff must use two-factor (ops/configure_keycloak.py): the first sign-in sets up the
    authenticator but its token (amr=pwd) is refused; a sign-in with a code is accepted."""
    first = staff_sign_in("staff@irep.demo", "password123")
    r = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {first['access_token']}"})
    assert r.status_code == 401 and r.headers["X-IREP-Reason"] == "two_factor_required"
    again = staff_sign_in("staff@irep.demo", "password123", secret=first["secret"], avoid=first["used"])
    h = {"Authorization": f"Bearer {again['access_token']}"}
    me = api.get("/api/v1/auth/me", headers=h).json()
    assert (me["role"], me["college_id"]) == ("irep_admin", "irep_platform")
    assert api.get("/api/v1/admin/colleges", headers=h).status_code == 200
    # college routes admit staff (legacy super_admin), but the platform tenant holds no
    # college data: no student data without a logged support session (§5.4)
    assert api.get("/api/v1/college/overview", headers=h).json()["kpis"]["students_enrolled"]["value"] == 0


def test_wrong_password_gets_no_code():
    assert browser_sign_in("priya.r@demo.edu", "wrong-password")["error"] == "login_failed"


def test_password_grant_is_disabled_for_the_web_client():
    r = httpx.post(f"{ISSUER}/protocol/openid-connect/token", data={
        "grant_type": "password", "client_id": "irep-web", "username": "priya.r@demo.edu", "password": "password123"})
    assert r.status_code in (400, 401)
