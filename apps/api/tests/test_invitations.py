"""Phase 5: invitations (one-time set-password link, 48 h) instead of temporary passwords; list, resend, revoke."""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from core.config import settings
from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import (AuditLog, Branch, College, Invitation, MouTerm, Notification, OutboxEvent, User)
from services import invitations as inv_svc

client = TestClient(app)
STAFF = {"Authorization": "Bearer " + create_access_token({"sub": "usr_irep_staff_01", "role": "irep_admin", "college_id": PLATFORM_TENANT})}
KAVITHA = {"Authorization": "Bearer " + create_access_token({"sub": "usr_kavitha_01", "role": "college_admin", "college_id": "col_demo_001"})}
PRIYA = {"Authorization": "Bearer " + create_access_token({"sub": "usr_priya_01", "role": "student", "college_id": "col_demo_001"})}
GOOD = "Welcome2026-irep"


def _token(created: dict) -> str:
    return created["invite_link"].split("#token=", 1)[1]


@pytest.fixture
def invited():
    """A placement officer invited by the demo college admin; everything it creates is removed afterwards."""
    tag = uuid.uuid4().hex[:8]
    email = f"new.officer.{tag}@college.example"
    r = client.post("/api/v1/college/users", json={"name": "New Officer", "email": email, "role": "placement_officer"}, headers=KAVITHA)
    assert r.status_code == 201, r.text
    body = r.json()
    yield body
    db = SessionLocal()
    try:
        db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id.in_([body["id"], body["invitation"]["id"]])))
        db.execute(delete(Notification).where(Notification.user_id == body["id"]))
        db.execute(delete(Invitation).where(Invitation.user_id == body["id"]))
        db.execute(delete(User).where(User.id == body["id"]))
        db.commit()
    finally:
        db.close()


def test_creating_an_account_returns_a_one_time_link_not_a_password(invited):
    assert "temporary_password" not in invited
    assert invited["invite_link"].startswith(settings.PUBLIC_BASE_URL.rstrip("/") + "/auth/set-password#token=")
    assert invited["invitation"]["status"] == "pending" and invited["invitation"]["invited_by"]
    db = SessionLocal()
    try:
        inv = db.get(Invitation, invited["invitation"]["id"])
        assert inv.token_hash == inv_svc.hash_token(_token(invited)) and _token(invited) not in str(inv.__dict__)   # hash only
        assert 47 <= (inv.expires_at - datetime.datetime.utcnow()).total_seconds() / 3600 <= 48
        # the token is in no outbox payload or notification
        assert all(_token(invited) not in str(e.payload) for e in db.execute(select(OutboxEvent)).scalars())
        assert not db.execute(select(func.count(Notification.id)).where(Notification.body_en.contains(_token(invited)))).scalar_one()
    finally:
        db.close()
    # the account cannot sign in before accepting
    assert client.post("/api/v1/auth/login", json={"role": "college", "identifier": invited["email"], "password": "anything"}).status_code == 401


def test_accepting_sets_the_password_signs_in_and_burns_the_link(invited):
    tok = _token(invited)
    who = client.post("/api/v1/auth/invitations/lookup", json={"token": tok}).json()
    assert who["email"] == invited["email"] and who["role"] == "placement_officer" and who["college"] and who["min_length"] == 10

    for weak, why in (("short1", "at least 10"), ("onlyletters-here", "letter and one number"), (invited["email"].split("@")[0] + "-2026", "email name")):
        r = client.post("/api/v1/auth/invitations/accept", json={"token": tok, "password": weak})
        assert r.status_code == 422 and (why is None or why in r.json()["detail"])
    r = client.post("/api/v1/auth/invitations/accept", json={"token": tok, "password": GOOD})
    assert r.status_code == 200 and r.json()["access_token"] and r.json()["user"]["role"] == "placement_officer"

    assert client.post("/api/v1/auth/invitations/accept", json={"token": tok, "password": GOOD}).status_code == 404     # once only
    assert client.post("/api/v1/auth/login", json={"role": "college", "identifier": invited["email"], "password": GOOD}).status_code == 200
    row = next(i for i in client.get("/api/v1/college/invitations", headers=KAVITHA).json()["items"] if i["id"] == invited["invitation"]["id"])
    assert row["status"] == "accepted" and row["accepted_at"]
    assert client.post(f"/api/v1/college/invitations/{row['id']}/resend", headers=KAVITHA).status_code == 409
    assert client.post(f"/api/v1/college/invitations/{row['id']}/revoke", headers=KAVITHA).status_code == 409
    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "invitation.accepted", AuditLog.entity_id == row["id"])).first()
    finally:
        db.close()


def test_an_expired_link_says_so_and_resend_gives_a_new_one(invited):
    old = _token(invited)
    db = SessionLocal()
    try:
        db.get(Invitation, invited["invitation"]["id"]).expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    r = client.post("/api/v1/auth/invitations/lookup", json={"token": old})
    assert r.status_code == 410 and "send it again" in r.json()["detail"]
    row = next(i for i in client.get("/api/v1/college/invitations", headers=KAVITHA).json()["items"] if i["id"] == invited["invitation"]["id"])
    assert row["status"] == "expired"

    again = client.post(f"/api/v1/college/invitations/{row['id']}/resend", headers=KAVITHA).json()
    new = _token(again)
    assert new != old and again["invitation"]["status"] == "pending" and again["invitation"]["resends"] == 1
    assert client.post("/api/v1/auth/invitations/lookup", json={"token": old}).status_code == 404                   # old link dead
    assert client.post("/api/v1/auth/invitations/accept", json={"token": new, "password": GOOD}).status_code == 200


def test_revoke_kills_the_link_and_deactivates_the_unused_account(invited):
    iid = invited["invitation"]["id"]
    out = client.post(f"/api/v1/college/invitations/{iid}/revoke", headers=KAVITHA).json()
    assert out["invitation"]["status"] == "revoked"
    assert client.post("/api/v1/auth/invitations/lookup", json={"token": _token(invited)}).status_code == 404
    db = SessionLocal()
    try:
        assert db.get(User, invited["id"]).is_active is False
    finally:
        db.close()
    # sending it again reactivates the account with a fresh link
    again = client.post(f"/api/v1/college/invitations/{iid}/resend", headers=KAVITHA).json()
    assert again["invitation"]["status"] == "pending"
    assert client.post("/api/v1/auth/invitations/accept", json={"token": _token(again), "password": GOOD}).status_code == 200


def test_live_email_mints_the_token_in_the_mailer_only(invited, monkeypatch):
    """NOTIFY_ADAPTER=live: the response has no link, the outbox payload has no token, the email has the link."""
    sent = []
    monkeypatch.setattr(settings, "NOTIFY_ADAPTER", "live")
    monkeypatch.setattr("services.gateways.send_email", lambda to, subject, body, **_: sent.append((to, body)))
    out = client.post(f"/api/v1/college/invitations/{invited['invitation']['id']}/resend", headers=KAVITHA).json()
    assert "invite_link" not in out and "email" in out["invite"]
    db = SessionLocal()
    try:
        ev = db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "invite.send", OutboxEvent.entity_id == invited["invitation"]["id"])
                        .order_by(OutboxEvent.created_at.desc())).scalars().first()
        assert set(ev.payload) == {"invitation_id", "seq"}
        assert db.get(Invitation, invited["invitation"]["id"]).token_hash is None                                  # old link dead now
        inv_svc._send_invitation_email(db, ev)
        inv_svc._send_invitation_email(db, ev)                                                                      # idempotent
        db.commit()
    finally:
        db.close()
    assert len(sent) == 1 and sent[0][0] == invited["email"]
    token = sent[0][1].split("#token=", 1)[1].split()[0]
    assert client.post("/api/v1/auth/invitations/accept", json={"token": token, "password": GOOD}).status_code == 200


def test_guards_and_tenancy(invited):
    iid = invited["invitation"]["id"]
    assert client.get("/api/v1/college/invitations", headers=PRIYA).status_code == 403
    assert client.post(f"/api/v1/college/invitations/{iid}/revoke", headers=PRIYA).status_code == 403
    other = {"Authorization": "Bearer " + create_access_token({"sub": "usr_kavitha_01", "role": "college_admin", "college_id": "col_other_test"})}
    assert client.post(f"/api/v1/college/invitations/{iid}/revoke", headers=other).status_code in (401, 404)
    assert all(i["id"] != iid for i in client.get("/api/v1/admin/colleges/col_other_test/invitations", headers=STAFF).json().get("items", []))
    # IREP staff see and manage the college's invitations from 45
    items = client.get("/api/v1/admin/colleges/col_demo_001/invitations", headers=STAFF).json()["items"]
    assert any(i["id"] == iid for i in items)
    assert client.post("/api/v1/admin/colleges/col_demo_001/invitations/inv_nope/resend", headers=STAFF).status_code == 404
    assert client.post("/api/v1/auth/invitations/lookup", json={"token": "x" * 40}).status_code == 404


def test_keycloak_mode_keeps_keycloaks_link(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "keycloak")
    assert client.post("/api/v1/auth/invitations/lookup", json={"token": "x" * 40}).status_code == 410
    assert client.post("/api/v1/auth/invitations/accept", json={"token": "x" * 40, "password": GOOD}).status_code == 410
