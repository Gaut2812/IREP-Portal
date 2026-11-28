"""Discussions (screen 34), Phase 2: edit (15 min) and delete your own message, seen ticks, emoji reactions."""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import AuditLog, GroupMember, GroupMessage, MessageReaction, MessageReport, User

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA = _h("usr_priya_01", "student")


@pytest.fixture
def chat():
    """A group Priya is in, another student member of it, and Priya's fresh message (removed afterwards)."""
    group = client.get("/api/v1/student/discussions/groups", headers=PRIYA).json()["groups"]
    gid = next(g["id"] for g in group if not g["is_locked"])
    with SessionLocal() as db:
        other = db.execute(select(GroupMember.user_id).join(User, User.id == GroupMember.user_id)
                           .where(GroupMember.group_id == gid, GroupMember.user_id != "usr_priya_01", User.role == "student")).scalars().first()
    mid = client.post(f"/api/v1/groups/{gid}/messages", headers=PRIYA, json={"message_text": "Is BFS enough for shortest paths here?"}).json()["message_id"]
    yield gid, mid, _h(other, "student")
    with SessionLocal() as db:
        db.execute(delete(MessageReaction).where(MessageReaction.message_id == mid))
        db.execute(delete(MessageReport).where(MessageReport.message_id == mid))
        db.execute(delete(GroupMessage).where(GroupMessage.id == mid))
        db.commit()


def _mine(gid, mid, headers=PRIYA):
    return next(m for m in client.get(f"/api/v1/groups/{gid}/messages", headers=headers).json()["messages"] if m["id"] == mid)


def test_edit_within_the_window_keeps_the_original_for_moderators(chat):
    gid, mid, other = chat
    assert _mine(gid, mid)["can_edit"] is True
    assert client.patch(f"/api/v1/messages/{mid}", headers=PRIYA, json={"message_text": "Is BFS enough for shortest paths in an unweighted graph?"}).status_code == 200
    m = _mine(gid, mid)
    assert m["edited"] is True and m["message_text"].endswith("unweighted graph?")
    with SessionLocal() as db:
        assert db.get(GroupMessage, mid).original_text == "Is BFS enough for shortest paths here?"
    assert client.patch(f"/api/v1/messages/{mid}", headers=other, json={"message_text": "hijack"}).status_code == 403
    with SessionLocal() as db:
        db.get(GroupMessage, mid).created_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=20)
        db.commit()
    assert client.patch(f"/api/v1/messages/{mid}", headers=PRIYA, json={"message_text": "too late"}).status_code == 409


def test_an_edit_goes_through_moderation(chat):
    gid, mid, _ = chat
    r = client.patch(f"/api/v1/messages/{mid}", headers=PRIYA, json={"message_text": "call me on 9876543210"})
    assert r.status_code == 422                                         # phone numbers are blocked, edit or not


def test_delete_shows_a_placeholder_to_everyone(chat):
    gid, mid, other = chat
    assert client.delete(f"/api/v1/messages/{mid}", headers=other).status_code == 403
    assert client.delete(f"/api/v1/messages/{mid}", headers=PRIYA).status_code == 200
    seen_by_other = _mine(gid, mid, other)
    assert seen_by_other["is_deleted"] is True and seen_by_other["message_text"] == "This message was deleted."
    assert _mine(gid, mid)["can_edit"] is False
    with SessionLocal() as db:
        assert db.get(GroupMessage, mid).message_text.startswith("Is BFS")          # moderators can still read it
        assert db.execute(select(AuditLog.id).where(AuditLog.action == "group.message_deleted", AuditLog.entity_id == mid)).first()
    assert client.delete(f"/api/v1/messages/{mid}", headers=PRIYA).status_code == 409


def test_seen_ticks_follow_other_members_reading(chat):
    gid, mid, other = chat
    with SessionLocal() as db:   # nobody else has read since the message
        for gm in db.execute(select(GroupMember).where(GroupMember.group_id == gid, GroupMember.user_id != "usr_priya_01")).scalars():
            gm.last_read_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        db.commit()
    assert _mine(gid, mid)["seen_count"] == 0
    client.get(f"/api/v1/groups/{gid}/messages", headers=other)          # the other student opens the group
    m = _mine(gid, mid)
    assert m["seen_count"] == 1 and len(m["seen_by"]) == 1


def test_emoji_reactions_one_per_person(chat):
    gid, mid, other = chat
    assert client.post(f"/api/v1/messages/{mid}/react", headers=other, json={"emoji": "❤️"}).json()["my_emoji"] == "❤️"
    assert client.post(f"/api/v1/messages/{mid}/react", headers=other, json={"emoji": "😂"}).json()["my_emoji"] == "😂"   # replaced
    assert _mine(gid, mid)["reaction_summary"] == [{"emoji": "😂", "count": 1}]
    assert client.post(f"/api/v1/messages/{mid}/react", headers=other, json={"emoji": "😂"}).json()["my_reaction"] is False   # taken back
    assert client.post(f"/api/v1/messages/{mid}/react", headers=other, json={"emoji": "🍕"}).status_code == 422
    assert client.post(f"/api/v1/messages/{mid}/react", headers=other).json()["my_emoji"] == "👍"     # no body: a like, as before
