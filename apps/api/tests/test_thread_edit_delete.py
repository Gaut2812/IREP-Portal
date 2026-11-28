"""Phase 4 (C2.10 for threads): the sender edits within 15 minutes or deletes for everyone; the text is kept for audit."""
import datetime

from sqlalchemy import select

from core.database import SessionLocal
from models.schema import AuditLog, DirectMessage
from tests.test_screen_35_message_hub import ARUN, KAVITHA, LAKSHMI, MEENA, PRIYA, _token, client, demo_state  # noqa: F401


def _send(thread, text, headers):
    r = client.post(f"/api/v1/threads/{thread}/messages", json={"text": text}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["message_id"]


def _msg(thread, mid, headers, lang="en"):
    return next(m for m in client.get(f"/api/v1/threads/{thread}/messages?lang={lang}", headers=headers).json()["messages"] if m["id"] == mid)


def test_sender_edits_and_the_other_side_sees_edited():
    mid = _send("th_lakshmi", "Coaching is at 10 AM", ARUN)
    mine = _msg("th_lakshmi", mid, ARUN)
    assert mine["can_edit"] and mine["can_delete"] and not mine["edited"]
    theirs = _msg("th_lakshmi", mid, LAKSHMI)
    assert not theirs["can_edit"] and not theirs["can_delete"]

    assert client.patch(f"/api/v1/direct-messages/{mid}", json={"text": "Coaching is at 11 AM"}, headers=ARUN).status_code == 200
    seen = _msg("th_lakshmi", mid, LAKSHMI)
    assert seen["edited"] and seen["original_text"] == "Coaching is at 11 AM"
    # Tamil view follows the edit (translated again)
    assert _msg("th_lakshmi", mid, LAKSHMI, "ta")["text"] != "Coaching is at 10 AM"

    db = SessionLocal()
    try:
        m = db.get(DirectMessage, mid)
        assert m.first_text == "Coaching is at 10 AM" and m.edited_at is not None
        assert db.execute(select(AuditLog).where(AuditLog.action == "thread.message_edited")).first()
    finally:
        db.close()


def test_edit_window_closes_after_15_minutes():
    mid = _send("th_lakshmi", "Bring the report card", ARUN)
    db = SessionLocal()
    try:
        db.get(DirectMessage, mid).created_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=16)
        db.commit()
    finally:
        db.close()
    assert _msg("th_lakshmi", mid, ARUN)["can_edit"] is False
    assert client.patch(f"/api/v1/direct-messages/{mid}", json={"text": "x"}, headers=ARUN).status_code == 409
    assert client.delete(f"/api/v1/direct-messages/{mid}", headers=ARUN).status_code == 200      # delete has no window


def test_delete_for_everyone_hides_the_text_everywhere():
    mid = _send("th_lakshmi", "Wrong child, sorry", ARUN)
    assert client.delete(f"/api/v1/direct-messages/{mid}", headers=ARUN).json()["deleted"] is True
    for h in (ARUN, LAKSHMI):
        m = _msg("th_lakshmi", mid, h)
        assert m["deleted"] and m["text"] == "" and m["original_text"] == "" and not m["can_edit"]
    threads = client.get("/api/v1/parent/threads", headers=LAKSHMI).json()["threads"]
    assert all("Wrong child" not in t["last_message"] for t in threads)
    assert client.post(f"/api/v1/direct-messages/{mid}/translate?to=ta", headers=LAKSHMI).status_code == 404
    assert client.delete(f"/api/v1/direct-messages/{mid}", headers=ARUN).status_code == 404       # already gone
    db = SessionLocal()
    try:
        assert db.get(DirectMessage, mid).first_text == "Wrong child, sorry"
        assert db.execute(select(AuditLog).where(AuditLog.action == "thread.message_deleted")).first()
    finally:
        db.close()


def test_only_the_sender_in_their_own_college_can_change_it():
    mid = _send("th_lakshmi", "Saturday class confirmed", ARUN)
    assert client.patch(f"/api/v1/direct-messages/{mid}", json={"text": "hacked"}, headers=LAKSHMI).status_code == 403   # not theirs
    assert client.delete(f"/api/v1/direct-messages/{mid}", headers=LAKSHMI).status_code == 403
    assert client.delete(f"/api/v1/direct-messages/{mid}", headers=MEENA).status_code == 404       # not her thread
    assert client.delete(f"/api/v1/direct-messages/{mid}", headers=_token("usr_arun_01", "trainer", "col_other_999")).status_code == 404
    assert client.delete(f"/api/v1/direct-messages/{mid}", headers=PRIYA).status_code == 403
    assert client.patch(f"/api/v1/direct-messages/{mid}", json={"text": ""}, headers=ARUN).status_code == 422


def test_college_admin_edits_own_message_in_a_college_thread():
    mid = _send("th_kavitha", "Meeting at 3", KAVITHA)
    assert client.patch(f"/api/v1/direct-messages/{mid}", json={"text": "Meeting at 4"}, headers=KAVITHA).status_code == 200
    assert _msg("th_kavitha", mid, KAVITHA)["edited"]
