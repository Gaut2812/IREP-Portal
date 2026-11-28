"""Security self-review (parent OTP, Keycloak admin scripts, logs): one test per finding that was fixed."""
import json
import logging
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.security import get_password_hash, verify_password
from main import app, _RedactSecrets
from models.schema import OtpAttempt
from seed.seed_screen01 import seed_screen01
from services import gateways

client = TestClient(app)
REQ, VERIFY, PHONE = "/api/v1/auth/parent/otp/request", "/api/v1/auth/parent/otp/verify", "9876543214"


@pytest.fixture(autouse=True)
def clean_otp():
    db = SessionLocal()
    try:
        seed_screen01(db)                     # clears otp_attempts
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        seed_screen01(db)
        db.commit()
    finally:
        db.close()


def _code() -> str:
    return client.post(REQ, json={"phone": PHONE}).json()["demo_otp"]


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


# --- passwords ---------------------------------------------------------------------------

def test_a_stored_hash_or_plain_value_is_never_a_password():
    h = get_password_hash("correct horse")
    assert verify_password("correct horse", h)
    assert not verify_password(h, h)                     # was accepted before: hash replay
    assert not verify_password("x", "x")                 # was accepted before: plain-text fallback
    assert not verify_password("", h) and not verify_password("x", "")


# --- OTP -----------------------------------------------------------------------------------

def test_a_new_code_cancels_the_earlier_one():
    first = _code()
    second = _code()
    if first == second:
        pytest.skip("both random codes were equal")
    assert client.post(VERIFY, json={"phone": PHONE, "otp": first}).status_code == 400
    assert client.post(VERIFY, json={"phone": PHONE, "otp": second}).status_code == 200


def test_success_does_not_count_as_a_failed_attempt():
    code = _code()
    assert client.post(VERIFY, json={"phone": PHONE, "otp": code}).status_code == 200
    db = SessionLocal()
    try:
        row = db.execute(select(OtpAttempt)).scalars().one()
        assert row.consumed and row.verify_attempts == 0
    finally:
        db.close()


def test_wrong_codes_are_capped_per_number_across_codes():
    for _ in range(3):                                   # 3 codes x 5 wrong guesses = 15
        code = _code()
        for _ in range(5):
            assert client.post(VERIFY, json={"phone": PHONE, "otp": _wrong(code)}).status_code == 400
    r = client.post(REQ, json={"phone": PHONE})
    assert r.status_code == 429                          # no fresh code to keep guessing with
    assert client.post(VERIFY, json={"phone": PHONE, "otp": "123456"}).status_code == 429


def _fresh_ip_client():
    """A client with its own address, so earlier runs' audit rows cannot shift the count."""
    import uuid
    n = uuid.uuid4().int
    return TestClient(app, client=(f"10.{n % 250}.{(n >> 8) % 250}.{(n >> 16) % 250 + 1}", 50000))


def test_requests_are_limited_per_ip(monkeypatch):
    net = _fresh_ip_client()
    monkeypatch.setattr(settings, "OTP_IP_REQUESTS_PER_WINDOW", 2)
    assert net.post(REQ, json={"phone": "9000000011"}).status_code == 200
    assert net.post(REQ, json={"phone": "9000000012"}).status_code == 200
    r = net.post(REQ, json={"phone": "9000000013"})        # a third number from the same network
    assert r.status_code == 429 and r.headers["Retry-After"] == "600"


def test_wrong_codes_are_limited_per_ip(monkeypatch):
    net = _fresh_ip_client()
    monkeypatch.setattr(settings, "OTP_IP_VERIFY_FAILS_PER_WINDOW", 1)
    code = net.post(REQ, json={"phone": PHONE}).json()["demo_otp"]
    assert net.post(VERIFY, json={"phone": PHONE, "otp": _wrong(code)}).status_code == 400
    assert net.post(VERIFY, json={"phone": PHONE, "otp": code}).status_code == 429      # even the right code


def test_answer_is_the_same_for_registered_and_unknown_numbers(monkeypatch):
    """Same status and body (apart from the development-only demo code), and both wait for the floor."""
    import time
    monkeypatch.setattr(settings, "OTP_RESPONSE_FLOOR_MS", 300)
    slow = []

    def slow_send(*a, **k):                 # a slow mail server must not slow the answer
        time.sleep(0.5)
        slow.append(1)
    import routers.auth as auth_router
    monkeypatch.setattr(auth_router, "_deliver_parent_otp", slow_send)
    timings, bodies = [], []
    for phone in (PHONE, "9000000041"):
        t = time.monotonic()
        r = client.post(REQ, json={"phone": phone})
        timings.append(time.monotonic() - t)
        body = r.json()
        body.pop("demo_otp", None)
        bodies.append((r.status_code, body))
    assert bodies[0] == bodies[1]
    assert all(t >= 0.3 for t in timings)
    assert slow == [1]                       # only the registered number got a code (after the response)

def test_phone_is_stored_as_a_keyed_hash():
    from routers.auth import _phone_hash
    import hashlib
    assert _phone_hash(PHONE) != hashlib.sha256(f"phone|{PHONE}".encode()).hexdigest()
    assert len(_phone_hash(PHONE)) == 64 and PHONE not in _phone_hash(PHONE)


# --- delivery and logs -----------------------------------------------------------------------

def test_placeholder_parent_emails_are_not_mailed():
    assert not gateways.real_email("9876543214@parents.invalid")
    assert not gateways.real_email("") and gateways.real_email("lakshmi@example.com")


def test_access_logs_redact_tokens_and_signatures():
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', (
        "1.2.3.4:5", "GET", "/api/v1/ws/groups/g1?token=eyJhbGciOi.secret.part&x=1", "1.1", 101), None)
    _RedactSecrets().filter(rec)
    line = rec.getMessage()
    assert "eyJhbGciOi" not in line and "token=[redacted]&x=1" in line
    rec2 = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "%s", ("/media/certificates/a.png?exp=1&sig=abcdef",), None)
    _RedactSecrets().filter(rec2)
    assert "abcdef" not in rec2.getMessage()


# --- Keycloak admin scripts ------------------------------------------------------------------

class FakeKeycloak:
    """Just enough of the admin REST API for invite() and configure_keycloak."""

    def __init__(self):
        self.users, self.calls, self.token_calls = {}, [], 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.calls.append((method, path, request.content.decode() if request.content else ""))
        if path.endswith("/protocol/openid-connect/token"):
            self.token_calls += 1
            return httpx.Response(200, json={"access_token": f"t{self.token_calls}"})
        if path.endswith("/users") and method == "GET":
            name = request.url.params.get("username")
            return httpx.Response(200, json=[u for u in self.users.values() if u["username"] == name])
        if path.endswith("/users") and method == "POST":
            body = json.loads(request.content)
            uid = f"kc{len(self.users) + 1}"
            self.users[uid] = {**body, "id": uid}
            return httpx.Response(201, headers={"Location": f"http://kc/admin/realms/irep/users/{uid}"})
        if "/users/" in path and method == "PUT" and path.count("/") == 5:
            uid = path.rsplit("/", 1)[-1]
            self.users[uid] = {**self.users[uid], **json.loads(request.content)}
            return httpx.Response(204)
        if path.endswith("/role-mappings/realm") and method == "GET":
            return httpx.Response(200, json=[])
        if "/roles/" in path:
            return httpx.Response(200, json={"name": path.rsplit("/", 1)[-1], "id": "r1"})
        return httpx.Response(204)


def _admin(fake):
    from services.keycloak_admin import KeycloakAdmin
    return KeycloakAdmin("http://kc", "irep", "admin", "pw", transport=httpx.MockTransport(fake))


REP = {"username": "ops@example.in", "email": "ops@example.in", "emailVerified": False, "enabled": True,
       "firstName": "Ops", "lastName": "-", "attributes": {"irep_user_id": ["u1"], "college_id": ["irep_platform"]}}


def test_invite_is_idempotent_and_never_resets_an_existing_account():
    fake = FakeKeycloak()
    kc = _admin(fake)
    kc.invite(REP, "irep_admin", send_email=True)
    user = next(iter(fake.users.values()))
    assert user["requiredActions"] == ["UPDATE_PASSWORD", "VERIFY_EMAIL", "CONFIGURE_TOTP"]       # staff: OTP from day one
    emails = [c for c in fake.calls if c[1].endswith("execute-actions-email")]
    assert len(emails) == 1
    # the user finishes setup; then the script (or an outbox retry) runs again
    user.update({"requiredActions": [], "emailVerified": True})
    kc.invite(REP, "irep_admin", send_email=True)
    assert user["requiredActions"] == [] and user["emailVerified"] is True
    assert len([c for c in fake.calls if c[1].endswith("execute-actions-email")]) == 1
    kc.invite(REP, "irep_admin", send_email=True, resend=True)       # explicit
    assert len([c for c in fake.calls if c[1].endswith("execute-actions-email")]) == 2


def test_admin_token_is_refreshed_after_expiry():
    fake = FakeKeycloak()
    kc = _admin(fake)
    expired = {"once": True}
    inner = fake.__call__

    def flaky(request):
        if expired["once"] and "/users" in request.url.path:
            expired["once"] = False
            return httpx.Response(401)
        return inner(request)

    kc.http._transport = httpx.MockTransport(flaky)
    assert kc.find_user("nobody") is None
    assert fake.token_calls == 2


def test_configure_keycloak_sends_only_its_own_fields(monkeypatch):
    import ops.configure_keycloak as ck
    fake = FakeKeycloak()

    def clients(request):
        if request.url.path.endswith("/clients") and request.method == "GET":
            return httpx.Response(200, json=[{"id": "c1", "clientId": "irep-web", "attributes": {}}])
        return fake(request)

    from services.keycloak_admin import KeycloakAdmin
    monkeypatch.setattr(ck, "admin_from_env", lambda: KeycloakAdmin("http://kc", "irep", "a", "b", transport=httpx.MockTransport(clients)))
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    # roles and the two-factor flow were verified against a real Keycloak 26.0.7 (docs/PERMISSIONS.md)
    monkeypatch.setattr(ck, "ensure_roles", lambda kc: None)
    monkeypatch.setattr(ck, "ensure_2fa_flow", lambda kc: None)
    monkeypatch.setattr(ck, "ensure_amr", lambda kc, client: None)
    assert ck.main() == 0
    realm_put = next(c for c in fake.calls if c[0] == "PUT" and c[1] == "/admin/realms/irep")
    body = json.loads(realm_put[2])
    assert "smtpServer" not in body and "users" not in body and body["sslRequired"] in ("all", "external")
    assert not any(c[0] == "GET" and c[1] == "/admin/realms/irep" for c in fake.calls)


def test_demo_user_sync_refuses_production(monkeypatch, capsys):
    import seed.sync_keycloak as sk
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(sys, "argv", ["sync_keycloak.py", "--all"])
    monkeypatch.setattr(sk, "admin_from_env", lambda: pytest.fail("must not contact Keycloak"))
    assert sk.main() == 2
    assert "refuses to run" in capsys.readouterr().out


def test_public_demo_mode_shows_the_parent_code_but_needs_a_sign_in(monkeypatch):
    """infra/demo runs ENVIRONMENT=demo: parents see their code on screen, but no anonymous demo profile."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "demo")
    r = client.post(REQ, json={"phone": PHONE})
    assert r.status_code == 200 and r.json().get("demo_otp")
    assert client.get("/api/v1/auth/me", headers={"X-Demo-Role": "super_admin"}).status_code == 401
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert "demo_otp" not in client.post(REQ, json={"phone": "9000000042"}).json()
