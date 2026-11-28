"""Tests: accept the invitation an account-creation call returned (Phase 5 replaced temporary passwords)."""
from fastapi.testclient import TestClient

from main import app

_client = TestClient(app)
_done: dict = {}
PASSWORD = "Welcome2026-irep"


def set_password(created: dict, password: str = PASSWORD) -> str:
    """Accept the link in ``created['invite_link']`` once and return the password (cached per account)."""
    key = created.get("id") or created.get("email")
    if key in _done:
        return _done[key]
    token = created["invite_link"].split("#token=", 1)[1]
    r = _client.post("/api/v1/auth/invitations/accept", json={"token": token, "password": password})
    assert r.status_code == 200, r.text
    _done[key] = password
    return password
