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

import httpx
import pytest

pytestmark = pytest.mark.skipif(os.getenv("KEYCLOAK_IT") != "1", reason="set KEYCLOAK_IT=1 with Keycloak running")

KC = os.getenv("KEYCLOAK_URL", "http://localhost:8081")
ISSUER = f"{KC}/realms/irep"
REDIRECT = "http://localhost:3000/auth/callback"


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


def test_wrong_password_gets_no_code():
    assert browser_sign_in("priya.r@demo.edu", "wrong-password")["error"] == "login_failed"


def test_password_grant_is_disabled_for_the_web_client():
    r = httpx.post(f"{ISSUER}/protocol/openid-connect/token", data={
        "grant_type": "password", "client_id": "irep-web", "username": "priya.r@demo.edu", "password": "password123"})
    assert r.status_code in (400, 401)
