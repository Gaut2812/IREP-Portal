"""Screen 34 Discussion Groups: 1-1 student thread 403, announcement-only lock,
keyword filter, reactions, answers, reporting, retention, tenant/role guards."""
import datetime
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import User, GroupMessage, MessageReport, GroupMember
from routers.discussions import purge_expired_messages
from seed.seed_screen34 import seed_screen34

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Priya R"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


PRIYA = _token("usr_priya_01", "student")
ARUN = _token("usr_arun_01", "trainer", name="Arun Kumar")


def _uid(name):
    db = SessionLocal()
    try:
        return db.execute(select(User).filter_by(name=name)).scalars().first().id
    finally:
        db.close()


def _reseed():
    db = SessionLocal()
    try:
        seed_screen34(db)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def demo_state():
    _reseed()
    yield
    _reseed()


def test_groups_and_info_match_pdf11():
    groups = client.get("/api/v1/student/discussions/groups", headers=PRIYA).json()["groups"]
    assert [(g["name"], g["unread"]) for g in groups] == [
        ("AI & DS · Sem 5 Batch", 3), ("Track Doubts · ML", 5), ("DSA Daily Problem", 0),
        ("Team: Crop Price Predictor", 2), ("Placement Updates", 1), ("GD & Communication", 0)]
    assert next(g for g in groups if g["name"] == "Placement Updates")["is_locked"] is True
    info = client.get("/api/v1/groups/grp_doubts/info", headers=PRIYA).json()
    assert info["students"] == 42 and info["moderators"] == 2 and info["online"] == 18
    assert info["doubts_answered"] == 128
    assert [(h["name"], h["answers"]) for h in info["top_helpers"]] == [("Vikram R", 24), ("Ananya P", 19), ("Sneha N", 15)]
    assert 30 <= info["avg_trainer_reply_min"] <= 40


def test_opening_a_group_marks_it_read():
    d = client.get("/api/v1/groups/grp_doubts/messages", headers=PRIYA).json()
    assert d["group"]["moderators"] == ["Arun K.", "Meena S."] and d["group"]["pinned_note"].startswith("Post code as snippets")
    answer = next(m for m in d["messages"] if m["is_marked_as_answer"] and m["sender_role"] == "Trainer" and "Pipeline" in m["message_text"])
    assert answer["reactions"] == 12
    groups = client.get("/api/v1/student/discussions/groups", headers=PRIYA).json()["groups"]
    assert next(g for g in groups if g["name"] == "Track Doubts · ML")["unread"] == 0


def test_one_to_one_student_thread_is_forbidden():
    r = client.post("/api/v1/threads", json={"to_user_id": _uid("Sneha N")}, headers=PRIYA)
    assert r.status_code == 403 and "turned off" in r.json()["detail"]
    assert client.post("/api/v1/threads", json={"to_user_id": "usr_arun_01"}, headers=PRIYA).status_code == 403
    # trainer <-> parent is allowed
    assert client.post("/api/v1/threads", json={"to_user_id": "usr_lakshmi_01"}, headers=ARUN).status_code == 200


def test_announcement_only_group_is_read_only_for_students():
    r = client.post("/api/v1/groups/grp_placement/messages", json={"message_text": "When is the drive?"}, headers=PRIYA)
    assert r.status_code == 403
    assert client.post("/api/v1/groups/grp_placement/messages", json={"message_text": "Drive venue: Seminar hall"}, headers=ARUN).status_code == 200
    # students can still react
    mid = client.get("/api/v1/groups/grp_placement/messages", headers=PRIYA).json()["messages"][-1]["id"]
    assert client.post(f"/api/v1/messages/{mid}/react", headers=PRIYA).json()["my_reaction"] is True


def test_post_code_snippet_filter_react_and_report():
    r = client.post("/api/v1/groups/grp_doubts/messages", json={"message_text": "How do I plot a confusion matrix?", "code_snippet": "from sklearn.metrics import confusion_matrix"}, headers=PRIYA)
    assert r.status_code == 200
    mid = r.json()["message_id"]
    msgs = client.get("/api/v1/groups/grp_doubts/messages", headers=PRIYA).json()["messages"]
    mine = next(m for m in msgs if m["id"] == mid)
    assert mine["is_mine"] and mine["code_snippet"].startswith("from sklearn")
    assert client.post("/api/v1/groups/grp_doubts/messages", json={"message_text": "here are the test answers for Friday"}, headers=PRIYA).status_code == 422
    # toggle reaction
    other = next(m for m in msgs if m["sender_name"] == "Vikram R")
    assert client.post(f"/api/v1/messages/{other['id']}/react", headers=PRIYA).json()["my_reaction"] is True
    assert client.post(f"/api/v1/messages/{other['id']}/react", headers=PRIYA).json()["my_reaction"] is False
    # report: once, not own, reaches moderators' queue
    assert client.post(f"/api/v1/messages/{mid}/report", json={"reason": "spam"}, headers=PRIYA).status_code == 422
    rep = client.post(f"/api/v1/messages/{other['id']}/report", json={"reason": "Off-topic link"}, headers=PRIYA)
    assert rep.status_code == 200
    assert client.post(f"/api/v1/messages/{other['id']}/report", json={"reason": "again"}, headers=PRIYA).json()["already"] is True
    db = SessionLocal()
    try:
        assert db.execute(select(MessageReport).filter_by(message_id=other["id"], status="open")).scalar_one().reason == "Off-topic link"
    finally:
        db.close()


def test_only_moderators_mark_answers():
    msgs = client.get("/api/v1/groups/grp_doubts/messages", headers=PRIYA).json()["messages"]
    target = next(m for m in msgs if m["sender_name"] == "Ananya P")
    assert client.post(f"/api/v1/messages/{target['id']}/mark-answer", headers=PRIYA).status_code == 403
    assert client.post(f"/api/v1/messages/{target['id']}/mark-answer", headers=ARUN).json()["is_marked_as_answer"] is True


def test_muted_member_cannot_post():
    db = SessionLocal()
    try:
        m = db.execute(select(GroupMember).filter_by(group_id="grp_doubts", user_id="usr_priya_01")).scalar_one()
        m.muted_until = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        db.commit()
    finally:
        db.close()
    assert client.post("/api/v1/groups/grp_doubts/messages", json={"message_text": "hello"}, headers=PRIYA).status_code == 403
    assert client.get("/api/v1/groups/grp_doubts/messages", headers=PRIYA).json()["me"]["can_post"] is False


def test_retention_policy_purges_old_messages():
    db = SessionLocal()
    try:
        old = datetime.datetime.utcnow() - datetime.timedelta(days=400)
        db.add(GroupMessage(id="msg_test_old", college_id="col_demo_001", group_id="grp_gd", sender_name="X", sender_role="Student",
                            sender_initials="X", message_text="ancient", created_at=old, updated_at=old))
        db.commit()
        assert purge_expired_messages(db, "col_demo_001") >= 1
        db.commit()
        assert db.execute(select(GroupMessage).filter_by(id="msg_test_old")).scalar_one_or_none() is None
        assert db.execute(select(GroupMessage).filter_by(id="msg_01")).scalar_one_or_none() is not None
    finally:
        db.close()
    assert client.post("/api/v1/admin/jobs/chat-retention", headers=PRIYA).status_code == 403


def test_guards():
    outsider = _token(_uid("Divya M"), "student", name="Divya M")
    assert client.get("/api/v1/groups/grp_doubts/messages", headers=outsider).status_code == 404
    assert client.post("/api/v1/groups/grp_doubts/messages", json={"message_text": "hi"}, headers=outsider).status_code == 404
    assert client.get("/api/v1/student/discussions/groups", headers=_token("usr_ramesh_01", "parent")).status_code == 403
    assert client.get("/api/v1/groups/grp_doubts/messages", headers=_token("usr_priya_01", "student", college_id="col_other_999")).status_code == 404
