"""Phase 4: parent RSVP can be changed until the college's deadline (with an optional reason for "no"), and the
college sees who holds which earned certificate (decision D1)."""
import datetime

import pytest
from sqlalchemy import select

from core.database import SessionLocal
from models.schema import AuditLog, Event
from tests.test_screen_42_17_14 import (KAVITHA, LAKSHMI, OTHER_COLLEGE, PRIYA, RAMESH, ARUN, _at, _create, client,  # noqa: F401
                                        events)

PUBLISHABLE = {"title_ta": "பெற்றோர் திறந்த நாள்", "location": "Seminar hall"}


def _published(made, **kw):
    eid = _create(made, **PUBLISHABLE, **kw)
    assert client.post(f"/api/v1/college/events/{eid}/publish", headers=KAVITHA).status_code == 200
    return eid


@pytest.mark.link("L05")
def test_parent_changes_the_reply_and_the_reason_reaches_the_college_without_a_name(events):
    eid = _published(events, rsvp_deadline=_at(24 * 4))
    row = next(e for e in client.get("/api/v1/parent/events", headers=RAMESH).json()["upcoming"] if e["id"] == eid)
    assert row["can_rsvp"] and row["rsvp_closes_at"].startswith(_at(24 * 4)[:13])

    assert client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "yes", "guests": 2}, headers=RAMESH).json()["reason"] is None
    r = client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "no", "guests": 3, "reason": "  Travelling that week "}, headers=RAMESH)
    assert r.status_code == 200 and r.json()["guests"] == 0 and r.json()["reason"] == "Travelling that week"
    # a reason is only kept for "no"
    assert client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "maybe", "reason": "x"}, headers=LAKSHMI).json()["reason"] is None

    detail = client.get(f"/api/v1/college/events/{eid}", headers=KAVITHA).json()
    assert detail["rsvp"] == {"yes": 0, "maybe": 1, "no": 1, "guests": 0}
    assert detail["decline_reasons"] == ["Travelling that week"] and "ramesh" not in str(detail).lower()
    assert detail["rsvp_deadline"].startswith(_at(24 * 4)[:13])

    mine = next(e for e in client.get("/api/v1/parent/events", headers=RAMESH).json()["upcoming"] if e["id"] == eid)
    assert mine["rsvp_status"] == "no" and mine["reason"] == "Travelling that week" and mine["replied_at"]

    db = SessionLocal()
    try:
        last = db.execute(select(AuditLog).where(AuditLog.action == "event.rsvp", AuditLog.entity_id == eid)
                          .order_by(AuditLog.created_at.desc())).scalars().first()
        assert last is not None
    finally:
        db.close()


def test_replies_close_at_the_deadline(events):
    eid = _published(events, rsvp_deadline=_at(24 * 2))
    assert client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "yes"}, headers=RAMESH).status_code == 200
    db = SessionLocal()
    try:
        db.get(Event, eid).rsvp_deadline = datetime.datetime.now() - datetime.timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    row = next(e for e in client.get("/api/v1/parent/events", headers=RAMESH).json()["upcoming"] if e["id"] == eid)
    assert row["can_rsvp"] is False and row["rsvp_status"] == "yes"
    r = client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "no"}, headers=RAMESH)
    assert r.status_code == 409 and "closed" in r.json()["detail"]


def test_deadline_must_be_before_the_start(events):
    body = {"title_en": "Open day", "starts_at": _at(24), "rsvp_deadline": _at(48), "audience": "parents"}
    assert client.post("/api/v1/college/events", json=body, headers=KAVITHA).status_code == 422


def test_college_sees_who_holds_which_certificate():
    r = client.get("/api/v1/college/certifications/holders", headers=KAVITHA)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1 and body["holders"]
    h = body["holders"][0]
    assert {"name", "register_no", "batch", "title", "issuer", "issued_on"} <= set(h)
    assert not {"proof_key", "proof_url", "decision_note", "proof_filename"} & set(h)          # never files or notes

    one = h["name"].split()[0]
    found = client.get(f"/api/v1/college/certifications/holders?search={one}", headers=KAVITHA).json()
    assert found["holders"] and all(one.lower() in (x["name"] + x["register_no"] + x["title"]).lower() for x in found["holders"])
    by_issuer = client.get(f"/api/v1/college/certifications/holders?issuer={h['issuer']}", headers=KAVITHA).json()
    assert by_issuer["holders"] and all(x["issuer"] == h["issuer"] for x in by_issuer["holders"])

    db = SessionLocal()
    try:
        assert db.execute(select(AuditLog).where(AuditLog.action == "college.certificate_holders_read")).first()
    finally:
        db.close()


def test_certificate_holders_guards():
    for h in (PRIYA, ARUN, RAMESH):
        assert client.get("/api/v1/college/certifications/holders", headers=h).status_code == 403
    other = client.get("/api/v1/college/certifications/holders", headers=OTHER_COLLEGE)
    assert other.status_code == 200 and other.json()["holders"] == []                         # nothing from another college
