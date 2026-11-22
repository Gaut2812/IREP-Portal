"""Pilot deployment (docs/deploy/DEPLOY.md): production start-up checks, email and SMS gateways,
parent OTP by email with MSG91 as an off-by-default switch, the storage interface, the Keycloak
ops scripts and the shape of infra/prod."""
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.config import settings
from core.database import SessionLocal
from core.production import allowed_demo, problems
from main import app
from models.schema import AuditLog, OtpAttempt, User
from seed.seed_screen01 import seed_screen01
from services import gateways
from services.storage import LocalStorage, S3Storage, get_storage

client = TestClient(app)
REPO = Path(__file__).resolve().parents[3]
PARENT_ID, PARENT_PHONE = "usr_lakshmi_01", "9876543214"


def _prod(**over):
    good = dict(
        ENVIRONMENT="production", AUTH_PROVIDER="keycloak", JWT_SECRET_KEY="a" * 64,
        PUBLIC_BASE_URL="https://portal.example.in", KEYCLOAK_URL="https://id.example.in",
        DATABASE_URL="postgresql+psycopg2://irep:x@postgres:5432/irep", GITHUB_WEBHOOK_SECRET="b" * 64,
        ALLOW_DEMO_ADAPTERS="judge0,labs,study_buddy", JUDGE0_ADAPTER="fake", LAB_ADAPTER="fake",
        STUDY_BUDDY_ADAPTER="fake", LIVE_CLASS_ADAPTER="teams", GRAPH_TENANT_ID="t", GRAPH_CLIENT_ID="c",
        GRAPH_CLIENT_SECRET="s", NOTIFY_ADAPTER="live", SMTP_HOST="smtp.example.in", SMTP_FROM="no-reply@example.in",
        SMS_PROVIDER="off", PARENT_OTP_CHANNEL="email", STORAGE_ADAPTER="local", OUTBOX_RUNNER="celery",
    )
    good.update(over)
    return settings.model_copy(update=good)


# --- production start-up checks --------------------------------------------------------------

def test_pilot_configuration_passes_with_demo_adapters_outside_the_pilot():
    s = _prod()
    assert problems(s) == []
    assert allowed_demo(s) == {"judge0", "labs", "study_buddy"}


def test_development_defaults_are_refused_in_production():
    dev = {"ENVIRONMENT": "production", "AUTH_PROVIDER": "local", "DATABASE_URL": "sqlite:///irep.db",
           "PUBLIC_BASE_URL": "http://localhost:3000", "NOTIFY_ADAPTER": "fake", "SMTP_HOST": "",
           "OUTBOX_RUNNER": "thread", "JWT_SECRET_KEY": "irep_super_secret_jwt_key_2026_antigravity",
           "GITHUB_WEBHOOK_SECRET": "dev_github_webhook_secret"}      # same on SQLite and the PostgreSQL CI job
    found = "\n".join(problems(settings.model_copy(update=dev)))
    for needle in ("AUTH_PROVIDER must be keycloak", "JWT_SECRET_KEY", "PUBLIC_BASE_URL", "PostgreSQL",
                   "NOTIFY_ADAPTER must be live", "SMTP_HOST", "OUTBOX_RUNNER", "GITHUB_WEBHOOK_SECRET"):
        assert needle in found, needle


@pytest.mark.parametrize("over, needle", [
    ({"ALLOW_DEMO_ADAPTERS": "judge0,auth"}, "unknown names: auth"),
    ({"ALLOW_DEMO_ADAPTERS": "labs,study_buddy"}, "JUDGE0_ADAPTER must be judge0"),
    ({"SMS_PROVIDER": "msg91"}, "MSG91_AUTH_KEY"),
    ({"SMS_PROVIDER": "twilio"}, "SMS_PROVIDER must be off, fast2sms or msg91"),
    ({"PARENT_OTP_CHANNEL": "sms"}, "PARENT_OTP_CHANNEL=sms needs SMS_PROVIDER=fast2sms or msg91"),
    ({"STORAGE_ADAPTER": "s3"}, "STORAGE_ADAPTER must be local"),
    ({"GRAPH_CLIENT_SECRET": ""}, "LIVE_CLASS_ADAPTER=teams needs"),
    ({"LIVE_CLASS_ADAPTER": "fake"}, "LIVE_CLASS_ADAPTER must be teams"),
    ({"KEYCLOAK_URL": "http://id.example.in"}, "KEYCLOAK_URL must be the https"),
])
def test_each_unsafe_setting_is_named(over, needle):
    assert any(needle in p for p in problems(_prod(**over))), problems(_prod(**over))


def test_sms_switch_and_classroom_fallback_are_valid_choices():
    assert problems(_prod(SMS_PROVIDER="msg91", MSG91_AUTH_KEY="k", MSG91_TEMPLATE_ID="t1",
                          MSG91_OTP_TEMPLATE_ID="t2", PARENT_OTP_CHANNEL="sms")) == []
    assert problems(_prod(LIVE_CLASS_ADAPTER="fake", ALLOW_DEMO_ADAPTERS="judge0,labs,study_buddy,live_classes")) == []


# --- gateways --------------------------------------------------------------------------------

class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.calls = host, port, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, msg):
        FakeSMTP.sent.append((self.calls[:], msg))


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.in")
    monkeypatch.setattr(settings, "SMTP_FROM", "IREP Portal <no-reply@example.in>")
    monkeypatch.setattr(settings, "SMTP_USER", "mailer")
    monkeypatch.setattr(settings, "SMTP_STARTTLS", True)
    real = gateways.send_email
    monkeypatch.setattr(gateways, "send_email", lambda to, subject, body: real(to, subject, body, smtp_factory=FakeSMTP))
    return FakeSMTP


class Who:
    def __init__(self, email=None, phone=None):
        self.email, self.phone = email, phone


def test_email_uses_starttls_and_login(smtp):
    gateways.deliver(Who(email="a@b.in"), "email", "Leave approved", "See the portal")
    calls, msg = smtp.sent[0]
    assert calls == ["starttls", ("login", "mailer")]
    assert msg["To"] == "a@b.in" and msg["Subject"] == "Leave approved" and "See the portal" in msg.get_content()


def test_sms_goes_by_email_while_the_switch_is_off(smtp, monkeypatch):
    monkeypatch.setattr(settings, "SMS_PROVIDER", "off")
    assert gateways.deliver(Who(email="p@b.in", phone="9876543214"), "sms", "Event tomorrow", None) == "delivered:email"
    assert smtp.sent[0][1]["To"] == "p@b.in"
    assert gateways.deliver(Who(phone="9876543214"), "sms", "Event", None) == "skipped:no_email"


def test_msg91_flow_request_when_switched_on(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"type": "success", "message": "ok"})

    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "key123")
    gateways.send_sms("98765 43214", "tmpl_otp", {"otp": "123456"}, client=httpx.Client(transport=httpx.MockTransport(handler)))
    body = seen[0].read().decode()
    assert seen[0].headers["authkey"] == "key123"
    assert '"template_id":"tmpl_otp"' in body.replace(" ", "") and '"mobiles":"919876543214"' in body.replace(" ", "")

    def failing(request):
        return httpx.Response(200, json={"type": "error", "message": "template not approved"})

    with pytest.raises(gateways.GatewayError):
        gateways.send_sms("9876543214", "t", {}, client=httpx.Client(transport=httpx.MockTransport(failing)))
    with pytest.raises(gateways.GatewayError):
        gateways._indian_mobile("+44 20 7946 0958")


# --- parent OTP over email -------------------------------------------------------------------

@pytest.fixture
def live_otp(smtp, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFY_ADAPTER", "live")
    monkeypatch.setattr(settings, "PARENT_OTP_CHANNEL", "email")
    monkeypatch.setattr(settings, "SMS_PROVIDER", "off")
    db = SessionLocal()
    try:
        seed_screen01(db)
        db.execute(delete(OtpAttempt))
        db.commit()
    finally:
        db.close()
    yield smtp
    db = SessionLocal()
    try:
        u = db.get(User, PARENT_ID)
        u.email = "lakshmi.s@example.com"
        db.execute(delete(OtpAttempt))
        db.commit()
    finally:
        db.close()


def test_parent_code_is_emailed_and_works(live_otp):
    r = client.post("/api/v1/auth/parent/otp/request", json={"phone": PARENT_PHONE})
    assert r.status_code == 200
    body = r.json()
    assert body["channel"] == "email" and "email address registered with the college" in body["message"]
    assert "மின்னஞ்சல" in body["message_ta"]
    _, msg = live_otp.sent[0]
    assert msg["To"] == "lakshmi.s@example.com"
    code = next(w.rstrip(".") for w in msg.get_content().split() if w.rstrip(".").isdigit() and len(w.rstrip(".")) == 6)
    v = client.post("/api/v1/auth/parent/otp/verify", json={"phone": PARENT_PHONE, "otp": code})
    assert v.status_code == 200 and v.json()["user"]["id"] == PARENT_ID
    db = SessionLocal()
    try:
        audit = db.execute(select(AuditLog).filter_by(action="auth.otp_requested").order_by(AuditLog.created_at.desc())).scalars().first()
        assert audit.detail["channel"] == "email" and code not in str(audit.detail)
    finally:
        db.close()


def test_mail_failure_is_a_503_and_leaves_no_code(live_otp, monkeypatch):
    def down(*a, **k):
        raise gateways.GatewayError("smtp down")
    monkeypatch.setattr(gateways, "send_email", down)
    r = client.post("/api/v1/auth/parent/otp/request", json={"phone": PARENT_PHONE})
    assert r.status_code == 503
    db = SessionLocal()
    try:
        assert db.execute(select(OtpAttempt)).first() is None
    finally:
        db.close()


def test_parent_without_email_gets_the_same_answer(live_otp):
    db = SessionLocal()
    try:
        db.get(User, PARENT_ID).email = ""
        db.commit()
    finally:
        db.close()
    r = client.post("/api/v1/auth/parent/otp/request", json={"phone": PARENT_PHONE})
    unknown = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9000000002"})
    assert r.status_code == unknown.status_code == 200 and r.json()["message"] == unknown.json()["message"]
    assert live_otp.sent == []


# --- storage interface -----------------------------------------------------------------------

def test_local_storage_round_trip_and_key_checks(tmp_path):
    s = LocalStorage(str(tmp_path))
    s.put("certificates/col_a/std_1/c.png", b"png-bytes", "image/png")
    assert s.exists("certificates/col_a/std_1/c.png") and s.get("certificates/col_a/std_1/c.png") == b"png-bytes"
    assert s.size("certificates/col_a/std_1/c.png") == 9 and s.content_type("x/report.pdf") == "application/pdf"
    assert not list(tmp_path.rglob("*.part"))
    s.delete("certificates/col_a/std_1/c.png")
    assert not s.exists("certificates/col_a/std_1/c.png")
    for bad in ("../etc/passwd", "/abs/path", "a/../../b", "a b.png", ""):
        with pytest.raises(ValueError):
            s.exists(bad)


def test_storage_adapter_switch(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_ADAPTER", "local")
    assert isinstance(get_storage(), LocalStorage) and get_storage().root == tmp_path.resolve()
    monkeypatch.setenv("STORAGE_ADAPTER", "s3")
    with pytest.raises(NotImplementedError):
        get_storage()
    assert not S3Storage.__abstractmethods__          # the S3 slot implements the full interface


# --- ops scripts -----------------------------------------------------------------------------

def test_keycloak_realm_is_pointed_at_the_portal_domain(monkeypatch):
    from ops.configure_keycloak import client_changes, realm_changes
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://portal.example.in")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.in")
    monkeypatch.setattr(settings, "SMTP_FROM", "no-reply@example.in")
    monkeypatch.setattr(settings, "SMTP_USER", "mailer")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "pw")
    r = realm_changes()
    assert r["sslRequired"] == "all" and r["smtpServer"]["host"] == "smtp.example.in" and r["smtpServer"]["auth"] == "true"
    c = client_changes({"clientId": "irep-web", "redirectUris": ["http://localhost:3000/auth/callback"],
                        "attributes": {"post.logout.redirect.uris": "http://localhost:3000/login"}})
    assert c["redirectUris"] == ["https://portal.example.in/auth/callback"] and c["webOrigins"] == ["https://portal.example.in"]
    assert c["attributes"]["post.logout.redirect.uris"] == "https://portal.example.in/login"
    assert "localhost" not in str(c)


def test_bootstrap_admin_is_idempotent_and_platform_scoped():
    from core.security import PLATFORM_TENANT
    from ops.bootstrap_admin import ensure_staff
    db = SessionLocal()
    try:
        a = ensure_staff(db, "Pilot.Ops@Example.in", "Pilot Ops")
        b = ensure_staff(db, "pilot.ops@example.in", "Pilot Ops")
        assert a.id == b.id and a.role == "irep_admin" and a.college_id == PLATFORM_TENANT and a.email == "pilot.ops@example.in"
        with pytest.raises(SystemExit):
            ensure_staff(db, "priya.r@demo.edu", "Not staff")
        db.delete(a)
        db.commit()
    finally:
        db.close()


# --- infra/prod ------------------------------------------------------------------------------

def test_only_caddy_is_reachable_from_outside():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load((REPO / "infra" / "prod" / "docker-compose.yml").read_text(encoding="utf-8"))
    published = {name for name, svc in compose["services"].items() if svc.get("ports")}
    assert published == {"caddy"}
    assert compose["services"]["keycloak"]["command"][0] == "start"          # production mode, not start-dev
    api_env = compose["x-app"]["environment"]
    assert api_env["ENVIRONMENT"] == "production" and api_env["OUTBOX_RUNNER"] == "celery"


def test_env_example_names_every_production_secret():
    example = (REPO / "infra" / "prod" / ".env.example").read_text(encoding="utf-8")
    keys = {line.split("=", 1)[0] for line in example.splitlines() if "=" in line and not line.lstrip().startswith("#")}
    for k in ("POSTGRES_PASSWORD", "KC_DB_PASSWORD", "VALKEY_PASSWORD", "JWT_SECRET_KEY", "KEYCLOAK_ADMIN_PASSWORD",
              "GITHUB_WEBHOOK_SECRET", "SMTP_PASSWORD", "MSG91_AUTH_KEY", "GRAPH_CLIENT_SECRET", "SMS_PROVIDER",
              "PARENT_OTP_CHANNEL", "ALLOW_DEMO_ADAPTERS", "BACKUP_REMOTE"):
        assert k in keys, k
    assert "SMS_PROVIDER=off" in example and "PARENT_OTP_CHANNEL=email" in example
    assert not (REPO / "infra" / "prod" / ".env").exists() or ".env" in (REPO / ".gitignore").read_text()


def test_teams_check_names_the_missing_admin_step(capsys):
    from ops.teams_check import run
    from services.teams import GraphClient

    def graph(request):
        if "oauth2" in request.url.path:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        if "/events" in request.url.path:
            return httpx.Response(200, json={"value": []})
        return httpx.Response(403, json={"error": {"code": "Forbidden", "message": "No application access policy found"}})

    g = GraphClient("tenant", "client", "secret", transport=httpx.MockTransport(graph))
    assert run("trainer@college.onmicrosoft.com", graph=g) == 1
    out = capsys.readouterr().out
    assert "ok    token" in out and "ok    calendar" in out and "FAIL  meetings" in out and "access policy" in out


def test_trainer_teams_account_can_be_set_and_cleared():
    from ops.set_teams_upn import set_upn
    db = SessionLocal()
    try:
        before = db.execute(select(User).filter_by(role="trainer")).scalars().first()
        from models.schema import Trainer
        t = db.execute(select(Trainer).filter_by(user_id=before.id)).scalar_one()
        old = t.teams_upn
        assert set_upn(db, before.email.upper(), "Sid@College.onmicrosoft.com").teams_upn == "sid@college.onmicrosoft.com"
        assert set_upn(db, before.email, None).teams_upn is None
        t.teams_upn = old
        db.commit()
        with pytest.raises(SystemExit):
            set_upn(db, "priya.r@demo.edu", "x@y")          # a student, not a trainer
    finally:
        db.close()


# --- Fast2SMS --------------------------------------------------------------------------------

def _fast2sms(seen, reply=None, status=200):
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json=reply if reply is not None else {"return": True, "request_id": "r1", "message": ["SMS sent successfully."]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fast2sms_posts_with_the_key_in_the_header_only(monkeypatch):
    import json as _json
    monkeypatch.setattr(settings, "FAST2SMS_API_KEY", "test-key-not-real")
    monkeypatch.setattr(settings, "FAST2SMS_ROUTE", "q")
    seen = []
    gateways.send_fast2sms("+91 98765 43214", message="Leave approved", client=_fast2sms(seen))
    req = seen[0]
    assert req.method == "POST" and str(req.url) == "https://www.fast2sms.com/dev/bulkV2"
    assert req.headers["authorization"] == "test-key-not-real" and "test-key-not-real" not in str(req.url)
    body = _json.loads(req.content)
    assert body == {"route": "q", "message": "Leave approved", "language": "english", "flash": 0, "numbers": "9876543214"}


def test_fast2sms_otp_route_and_errors(monkeypatch):
    import json as _json
    monkeypatch.setattr(settings, "FAST2SMS_API_KEY", "k")
    monkeypatch.setattr(settings, "FAST2SMS_OTP_ROUTE", "otp")
    seen = []
    gateways.send_fast2sms("9876543214", message="x", otp="482913", client=_fast2sms(seen))
    assert _json.loads(seen[0].content) == {"route": "otp", "variables_values": "482913", "numbers": "9876543214"}
    with pytest.raises(gateways.GatewayError) as e:
        gateways.send_fast2sms("9876543214", message="x", client=_fast2sms([], {"return": False, "status_code": 412, "message": "Invalid Authentication"}, 412))
    assert "k" != str(e.value) and "Invalid Authentication" in str(e.value)
    monkeypatch.setattr(settings, "FAST2SMS_API_KEY", "")
    with pytest.raises(gateways.GatewayError):
        gateways.send_fast2sms("9876543214", message="x")


def test_parent_code_by_fast2sms(monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "SMS_PROVIDER", "fast2sms")
    monkeypatch.setattr(settings, "PARENT_OTP_CHANNEL", "sms")
    monkeypatch.setattr(gateways, "send_fast2sms", lambda phone, message=None, otp=None: sent.append((phone, message, otp)))
    assert gateways.send_parent_otp(Who(email="p@x.in", phone="9876543214"), "123456", 5) == "sms"
    assert sent == [("9876543214", "123456 is your IREP sign-in code. Valid for 5 minutes. Do not share it.", "123456")]
    assert gateways.deliver(Who(email="p@x.in", phone="9876543214"), "sms", "Event", "Tomorrow") == "delivered"
    assert sent[1][1].startswith("Event")


def test_fast2sms_production_settings():
    assert problems(_prod(SMS_PROVIDER="fast2sms", FAST2SMS_API_KEY="k", PARENT_OTP_CHANNEL="sms")) == []
    assert any("FAST2SMS_API_KEY" in p for p in problems(_prod(SMS_PROVIDER="fast2sms", FAST2SMS_API_KEY="")))
