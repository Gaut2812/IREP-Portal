"""Per-IP limit on password sign-in (API), on top of the per-account lockout. The OTP per-IP limits are
in tests/test_security_review.py; Caddy's per-IP limits in infra/prod/tests/test_caddy_and_compose.py."""
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from fastapi.testclient import TestClient

from core.config import settings
from core.database import SessionLocal
from main import app
from models.schema import User
from seed.seed_screen01 import seed_screen01

LOGIN = "/api/v1/auth/login"


def _net():
    n = uuid.uuid4().int
    return TestClient(app, client=(f"10.{n % 250}.{(n >> 8) % 250}.{(n >> 16) % 250 + 1}", 50000))


def _reset_lockouts():
    db = SessionLocal()
    try:
        seed_screen01(db)
        for u in db.query(User).filter(User.failed_logins > 0):
            u.failed_logins, u.locked_until = 0, None
        db.commit()
    finally:
        db.close()


def test_password_spraying_from_one_network_is_stopped(monkeypatch):
    """Different accounts, one wrong password each: no account is locked, but the network is."""
    _reset_lockouts()
    try:
        monkeypatch.setattr(settings, "LOGIN_IP_FAILS_PER_WINDOW", 3)
        net = _net()
        for who in ("arun.k@demo.edu", "meena.s@demo.edu", "pooja.m@demo.edu"):
            assert net.post(LOGIN, json={"role": "trainer", "identifier": who, "password": "Spring2026!"}).status_code == 401
        r = net.post(LOGIN, json={"role": "trainer", "identifier": "siddharth.r@demo.edu", "password": "password123"})
        assert r.status_code == 429 and r.headers["Retry-After"] == "600"        # even the right password
        # another network is unaffected
        assert _net().post(LOGIN, json={"role": "trainer", "identifier": "siddharth.r@demo.edu",
                                        "password": "password123"}).status_code == 200
    finally:
        _reset_lockouts()


def test_successful_sign_ins_do_not_count(monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_IP_FAILS_PER_WINDOW", 2)
    net = _net()
    for _ in range(4):                                         # a lab signing many people in from one IP
        assert net.post(LOGIN, json={"role": "trainer", "identifier": "arun.k@demo.edu", "password": "password123"}).status_code == 200
