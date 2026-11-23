"""Deactivation takes effect at once: every request and WebSocket checks "is this account still
active?" (core/active_users.py), cached in Valkey and cleared when users.is_active changes."""
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core import active_users
from core.config import settings
from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import User

client = TestClient(app)
SUPER = {"Authorization": "Bearer " + create_access_token({"sub": "usr_irep_super_01", "role": "super_admin", "college_id": PLATFORM_TENANT})}


def _h(sub, role, cid="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": cid})}


class FakeValkey:
    def __init__(self):
        self.data, self.gets = {}, 0
        self.down = False

    def get(self, k):
        if self.down:
            raise ConnectionError("down")
        self.gets += 1
        return self.data.get(k)

    def setex(self, k, ttl, v):
        if self.down:
            raise ConnectionError("down")
        self.data[k] = v

    def delete(self, *keys):
        for k in keys:
            self.data.pop(k, None)


@pytest.fixture
def valkey(monkeypatch):
    fake = FakeValkey()
    monkeypatch.setattr(active_users, "_cache", lambda: fake)
    return fake


@pytest.fixture
def staff_member():
    """A throwaway IREP staff account, removed afterwards."""
    db = SessionLocal()
    try:
        u = User(id="usr_active_test_01", college_id=PLATFORM_TENANT, email="active.test@tests.invalid", role="irep_admin",
                 name="Active Test", avatar_initials="AT", hashed_password="x")
        db.merge(u)
        db.commit()
    finally:
        db.close()
    yield "usr_active_test_01"
    db = SessionLocal()
    try:
        u = db.get(User, "usr_active_test_01")
        if u:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def test_deactivation_takes_effect_on_the_next_request(valkey, staff_member):
    me = _h(staff_member, "irep_admin", PLATFORM_TENANT)
    assert client.get("/api/v1/admin/colleges", headers=me).status_code == 200
    assert valkey.data[active_users._key(staff_member)] == b"1"                       # cached
    assert client.post(f"/api/v1/admin/staff/{staff_member}/deactivate", headers=SUPER).status_code == 200
    assert active_users._key(staff_member) not in valkey.data                         # cleared on commit
    r = client.get("/api/v1/admin/colleges", headers=me)                               # same, unexpired token
    assert r.status_code == 401 and r.json()["detail"] == "This account is deactivated"
    client.post(f"/api/v1/admin/staff/{staff_member}/reactivate", headers=SUPER)
    assert client.get("/api/v1/admin/colleges", headers=me).status_code == 200


def test_cache_answers_without_the_database(valkey, monkeypatch):
    assert active_users.is_active("usr_priya_01") is True
    monkeypatch.setattr(active_users, "_from_db", lambda uid: pytest.fail("should come from the cache"))
    assert active_users.is_active("usr_priya_01") is True


def test_cache_down_means_ask_the_database_never_fail_open(valkey, staff_member):
    valkey.data[active_users._key(staff_member)] = b"1"
    db = SessionLocal()
    try:
        db.get(User, staff_member).is_active = False
        valkey.down = True                  # the commit cannot clear the entry either
        db.commit()
    finally:
        db.close()
    assert active_users.is_active(staff_member) is False


def test_rollback_does_not_clear_or_change_anything(valkey):
    valkey.data[active_users._key("usr_priya_01")] = b"1"
    db = SessionLocal()
    try:
        db.get(User, "usr_priya_01").is_active = False
        db.rollback()
    finally:
        db.close()
    assert valkey.data[active_users._key("usr_priya_01")] == b"1"
    assert active_users.is_active("usr_priya_01") is True


def test_unknown_or_deleted_user_is_refused():
    assert client.get("/api/v1/auth/me", headers=_h("usr_never_existed", "student")).status_code == 401


def test_websockets_check_the_account_too(staff_member):
    db = SessionLocal()
    try:
        db.get(User, "usr_priya_01").is_active = False
        db.commit()
        tok = create_access_token({"sub": "usr_priya_01", "role": "student", "college_id": "col_demo_001"})
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect(f"/api/v1/ws/groups/grp_dsa?token={tok}") as ws:
                ws.receive_text()
        assert closed.value.code == 4401
    finally:
        db.get(User, "usr_priya_01").is_active = True
        db.commit()
        db.close()


def test_production_compose_wires_the_cache():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load((Path(__file__).resolve().parents[3] / "infra" / "prod" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["x-app"]["environment"]["USER_STATE_CACHE_URL"].endswith("@valkey:6379/1")
    assert settings.USER_STATE_CACHE_URL == ""            # development and tests ask the database
