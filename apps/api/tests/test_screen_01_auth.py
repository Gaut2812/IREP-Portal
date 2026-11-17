"""Screen 01 Sign-in: role-matched password login, lockout after five
failures, hashed/expiring/rate-limited parent OTP, language preference,
audit trail."""
import datetime
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from main import app
from core.database import SessionLocal
from models.schema import User, OtpAttempt, AuditLog
from seed.seed_screen01 import seed_screen01

client = TestClient(app)
LOGIN = "/api/v1/auth/login"
SID = {"role": "trainer", "identifier": "siddharth.r@demo.edu"}


def _reset():
    db = SessionLocal()
    try:
        seed_screen01(db)
        u = db.execute(select(User).filter_by(id="usr_lakshmi_01")).scalar_one()
        u.language_pref = "en"
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_auth_state():
    _reset()
    yield
    _reset()


def test_password_login_requires_matching_role_and_real_password():
    assert client.post(LOGIN, json={**SID, "password": "password123"}).status_code == 200
    # the old "password123 logs you in as someone" fallback is gone
    r = client.post(LOGIN, json={"role": "trainer", "identifier": "nobody@demo.edu", "password": "password123"})
    assert r.status_code == 401 and r.json()["detail"].startswith("Invalid credentials")
    # right password, wrong role: same generic answer
    assert client.post(LOGIN, json={"role": "college", "identifier": "siddharth.r@demo.edu", "password": "password123"}).status_code == 401
    # parents cannot use the password form
    assert client.post(LOGIN, json={"role": "parent", "identifier": "ramesh.k@example.com", "password": "password123"}).status_code == 401


def test_five_wrong_passwords_lock_the_account():
    for i in range(4):
        r = client.post(LOGIN, json={**SID, "password": "wrong"})
        assert r.status_code == 401 and f"{4 - i} attempt" in r.json()["detail"]
    r = client.post(LOGIN, json={**SID, "password": "wrong"})
    assert "locked" in r.json()["detail"]
    # even the correct password is refused while locked
    r = client.post(LOGIN, json={**SID, "password": "password123"})
    assert r.status_code == 401 and "Try again in" in r.json()["detail"]
    db = SessionLocal()
    try:
        u = db.execute(select(User).filter_by(id="usr_sid_01")).scalar_one()
        assert u.locked_until > datetime.datetime.utcnow() + datetime.timedelta(minutes=14)
        u.locked_until = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)   # lock expires
        db.commit()
        assert db.execute(select(func.count(AuditLog.id)).where(AuditLog.action == "auth.account_locked", AuditLog.entity_id == "usr_sid_01")).scalar_one() >= 1
    finally:
        db.close()
    assert client.post(LOGIN, json={**SID, "password": "password123"}).status_code == 200


def test_successful_login_resets_the_failure_counter():
    for _ in range(3):
        client.post(LOGIN, json={**SID, "password": "wrong"})
    assert client.post(LOGIN, json={**SID, "password": "password123"}).status_code == 200
    r = client.post(LOGIN, json={**SID, "password": "wrong"})
    assert "4 attempts left" in r.json()["detail"]


def test_otp_is_stored_hashed_and_single_use():
    otp = client.post("/api/v1/auth/parent/otp/request", json={"phone": "98765 43214"}).json()["demo_otp"]
    db = SessionLocal()
    try:
        row = db.execute(select(OtpAttempt).order_by(OtpAttempt.created_at.desc())).scalars().first()
        assert otp not in row.otp_hash and "9876543214" not in row.phone_hash
    finally:
        db.close()
    assert client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": otp}).json()["user"]["id"] == "usr_lakshmi_01"
    assert client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": otp}).status_code == 400


def test_wrong_otp_attempts_are_limited():
    otp = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543214"}).json()["demo_otp"]
    wrong = "000000" if otp != "000000" else "111111"
    for i in range(5):
        r = client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": wrong})
        assert r.status_code == 400 and f"{4 - i} attempt" in r.json()["detail"]
    assert client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": otp}).status_code == 429


def test_expired_otp_is_rejected():
    otp = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543214"}).json()["demo_otp"]
    db = SessionLocal()
    try:
        row = db.execute(select(OtpAttempt).order_by(OtpAttempt.created_at.desc())).scalars().first()
        row.expires_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    r = client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": otp})
    assert r.status_code == 400 and "expired" in r.json()["detail"]


def test_otp_requests_are_rate_limited_per_phone():
    for _ in range(5):
        assert client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543214"}).status_code == 200
    r = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543214"})
    assert r.status_code == 429 and r.headers["Retry-After"] == "600"
    # another number is unaffected
    assert client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543210"}).status_code == 200
    assert client.post("/api/v1/auth/parent/otp/request", json={"phone": "12345"}).status_code == 422


def test_unknown_number_gets_no_account():
    r = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9000000001"})
    assert r.status_code == 200 and "If this number is registered" in r.json()["message"]
    v = client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9000000001", "otp": r.json()["demo_otp"]})
    assert v.status_code == 404


def test_language_preference_is_saved():
    otp = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543214"}).json()["demo_otp"]
    token = client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": otp}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.put("/api/v1/auth/me/language", json={"language": "ta"}, headers=h).json()["language_pref"] == "ta"
    assert client.put("/api/v1/auth/me/language", json={"language": "fr"}, headers=h).status_code == 422
    otp = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876543214"}).json()["demo_otp"]
    assert client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876543214", "otp": otp}).json()["user"]["language_pref"] == "ta"
