"""Screen 35 Trainer Message Hub: per-thread messages, read state, translation
cache, moderation with required reasons, broadcast delivery report, parent
side, tenant and role guards."""
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
from core.security import create_access_token
from models.schema import GroupMessage, ModerationAction, TranslationCache, Notification, GroupMember, Broadcast
from seed.seed_screen34 import seed_screen34
from seed.seed_screen35 import seed_screen35

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': sub})}"}


ARUN = _token("usr_arun_01", "trainer")
MEENA = _token("usr_meena_01", "trainer")
RAMESH = _token("usr_ramesh_01", "parent")
LAKSHMI = _token("usr_lakshmi_01", "parent")
KAVITHA = _token("usr_kavitha_01", "college_admin")
PRIYA = _token("usr_priya_01", "student")


def _reseed():
    db = SessionLocal()
    try:
        seed_screen34(db)
        seed_screen35(db)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def demo_state():
    _reseed()
    yield
    _reseed()


def test_thread_list_matches_pdf12():
    d = client.get("/api/v1/trainer/threads", headers=ARUN).json()
    threads = [t for t in d["threads"] if t["kind"] == "thread"]
    assert [(t["name"], t["unread"]) for t in threads] == [
        ("Mr. Ramesh K", 0), ("Mrs. Lakshmi S", 2), ("Dr. Kavitha (Coordinator)", 1), ("Placement Cell", 0)]
    assert threads[0]["role_chip"] == "Parent · Priya R"
    assert any(t["kind"] == "group" and t["name"].startswith("AI & DS") for t in d["threads"])
    assert d["moderation_open"] == 2
    assert {m["key"]: m["status_en"] for m in d["permission_matrix"]}["student_student"] == "Off"
    parents = client.get("/api/v1/trainer/threads?category=Parents", headers=ARUN).json()["threads"]
    assert {t["name"] for t in parents} == {"Mr. Ramesh K", "Mrs. Lakshmi S"}


def test_opening_a_thread_returns_its_own_messages_and_marks_read():
    d = client.get("/api/v1/threads/th_lakshmi/messages", headers=ARUN).json()
    assert d["messages"][-1]["text"] == "Will Karthik have extra coaching this Saturday?"
    assert all("Priya" not in m["text"] for m in d["messages"])
    assert d["thread"]["child"]["name"] == "Karthik S"
    threads = client.get("/api/v1/trainer/threads", headers=ARUN).json()["threads"]
    assert next(t for t in threads if t["id"] == "th_lakshmi")["unread"] == 0


def test_tamil_view_keeps_the_original_and_is_cached():
    d = client.get("/api/v1/threads/th_ramesh/messages?lang=ta", headers=ARUN).json()
    first = d["messages"][0]
    assert first["translated"] and first["text"].startswith("வணக்கம்") and first["original_text"].startswith("Hello Arun sir")
    r = client.post("/api/v1/threads/th_ramesh/messages", json={"text": "Please share the attendance letter by Friday."}, headers=ARUN).json()
    assert r["translated_to_tamil"] is True
    t1 = client.post(f"/api/v1/direct-messages/{r['message_id']}/translate?to=ta", headers=RAMESH).json()
    assert t1["original_text"] == "Please share the attendance letter by Friday." and t1["text"] != t1["original_text"]
    db = SessionLocal()
    try:
        n = db.execute(select(func.count(TranslationCache.id)).where(TranslationCache.source_text == "Please share the attendance letter by Friday.")).scalar_one()
        assert n == 1
    finally:
        db.close()


def test_reply_notifies_parent_by_in_app_and_sms():
    client.post("/api/v1/threads/th_lakshmi/messages", json={"text": "Yes, extra coaching is at 10 AM on Saturday."}, headers=ARUN)
    db = SessionLocal()
    try:
        chans = set(db.execute(select(Notification.channel).where(Notification.user_id == "usr_lakshmi_01", Notification.kind == "message",
                                                                   Notification.body_en.like("Yes, extra coaching%"))).scalars().all())
        assert chans == {"in_app", "sms"}
    finally:
        db.close()
    # parent sees it and can answer in Tamil; trainer gets an English rendering
    assert client.get("/api/v1/parent/threads", headers=LAKSHMI).json()["threads"][0]["unread"] == 1
    client.post("/api/v1/threads/th_lakshmi/messages", json={"text": "நன்றி சார்."}, headers=LAKSHMI)
    last = client.get("/api/v1/threads/th_lakshmi/messages?lang=en", headers=ARUN).json()["messages"][-1]
    assert last["original_lang"] == "ta" and last["text"] == "Thank you sir."


def test_thread_access_is_limited_to_its_participants():
    assert client.get("/api/v1/threads/th_ramesh/messages", headers=LAKSHMI).status_code == 404
    assert client.post("/api/v1/threads/th_ramesh/messages", json={"text": "hi"}, headers=LAKSHMI).status_code == 404
    assert client.get("/api/v1/threads/th_ramesh/messages", headers=MEENA).status_code == 404
    assert client.get("/api/v1/threads/th_kavitha/messages", headers=KAVITHA).status_code == 200
    assert client.get("/api/v1/threads/th_ramesh/messages", headers=_token("usr_arun_01", "trainer", "col_other_999")).status_code == 404
    assert client.get("/api/v1/trainer/threads", headers=PRIYA).status_code == 403
    assert client.get("/api/v1/threads/th_ramesh/messages", headers=PRIYA).status_code == 403


def test_parent_can_only_start_threads_with_their_childs_trainers():
    assert client.post("/api/v1/threads", json={"to_user_id": "usr_pooja_01"}, headers=RAMESH).status_code == 403
    assert client.post("/api/v1/threads", json={"to_user_id": "usr_arun_01"}, headers=RAMESH).json()["thread_id"] == "th_ramesh"


def test_moderation_remove_requires_a_reason_and_is_recorded():
    q = client.get("/api/v1/trainer/moderation", headers=ARUN).json()
    assert [i["reason"] for i in q["items"]] == ["External test answers leak link", "Inappropriate comment"]
    rid = q["items"][0]["id"]
    assert client.post(f"/api/v1/trainer/moderation/{rid}", json={"action": "remove"}, headers=ARUN).status_code == 422
    assert client.post(f"/api/v1/trainer/moderation/{rid}", json={"action": "remove", "reason": "Shares graded test answers"}, headers=ARUN).json()["status"] == "actioned"
    db = SessionLocal()
    try:
        assert db.execute(select(GroupMessage).filter_by(id="msg_seed_r01")).scalar_one().is_removed is True
        act = db.execute(select(ModerationAction).filter_by(report_id=rid)).scalar_one()
        assert act.action == "remove" and act.reason == "Shares graded test answers" and act.actor_user_id == "usr_arun_01"
    finally:
        db.close()
    # students see the placeholder; a handled report cannot be actioned twice
    msgs = client.get("/api/v1/groups/grp_batch/messages", headers=PRIYA).json()["messages"]
    assert next(m for m in msgs if m["id"] == "msg_seed_r01")["is_removed"] is True
    assert client.post(f"/api/v1/trainer/moderation/{rid}", json={"action": "keep"}, headers=ARUN).status_code == 404
    assert client.get("/api/v1/trainer/moderation", headers=ARUN).json()["count"] == 1


def test_moderation_mute_and_keep():
    q = client.get("/api/v1/trainer/moderation", headers=ARUN).json()["items"]
    gd = next(i for i in q if i["group"].startswith("GD"))
    assert client.post(f"/api/v1/trainer/moderation/{gd['id']}", json={"action": "mute", "reason": "Disrespectful to a classmate"}, headers=ARUN).status_code == 200
    db = SessionLocal()
    try:
        author = db.execute(select(GroupMessage.sender_user_id).filter_by(id="msg_seed_r02")).scalar_one()
        assert db.execute(select(GroupMember).filter_by(group_id="grp_gd", user_id=author)).scalar_one().muted_until is not None
    finally:
        db.close()
    other = next(i for i in q if i["id"] != gd["id"])
    assert client.post(f"/api/v1/trainer/moderation/{other['id']}", json={"action": "keep"}, headers=ARUN).json()["status"] == "dismissed"
    assert client.get("/api/v1/trainer/moderation", headers=PRIYA).status_code == 403


def test_broadcast_delivery_report_counts_real_recipients():
    r = client.post("/api/v1/broadcasts", json={"audience": "both", "batch_ids": ["bat_aids_s5_aids"], "title": "Saturday lab", "body": "Lab 3 at 10 AM."}, headers=ARUN).json()
    assert r["delivery"]["students"] == 50 and r["delivery"]["parents"] == 1 and r["delivery"]["parents_sms"] == 1
    assert r["delivery"]["total_recipients"] == 51
    allb = client.post("/api/v1/broadcasts", json={"audience": "students", "title": "Quiz moved", "body": "Friday 2 PM."}, headers=ARUN).json()
    assert allb["delivery"]["students"] == 248 and allb["delivery"]["parents"] == 0
    assert client.post("/api/v1/broadcasts", json={"audience": "both", "batch_ids": ["bat_it_s5"], "title": "x" * 5, "body": "not mine"}, headers=ARUN).status_code == 403
    db = SessionLocal()
    try:
        assert db.execute(select(func.count(Broadcast.id))).scalar_one() == 2
    finally:
        db.close()
    hist = client.get("/api/v1/trainer/broadcasts", headers=ARUN).json()
    assert hist["broadcasts"][0]["title"] == "Quiz moved" and len(hist["batches"]) == 5
