"""Screen 34 moderation (S10): contact details and off-platform invites are refused, a
college's own terms block or flag (flagged posts reach the L18 queue), flood control."""
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
from models.schema import GroupMessage, MessageReport, ModerationTerm
from services.moderation import check_text

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN, KAVITHA = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_kavitha_01", "college_admin")
GROUP = "/api/v1/groups/grp_doubts/messages"


@pytest.fixture(autouse=True)
def clean():
    yield
    db = SessionLocal()
    try:
        mine = list(db.execute(select(GroupMessage.id).where(GroupMessage.sender_user_id == "usr_priya_01",
                                                             GroupMessage.message_text.like("S10 %"))).scalars())
        db.execute(delete(MessageReport).where(MessageReport.message_id.in_(mine or ["_"])))
        db.execute(delete(GroupMessage).where(GroupMessage.id.in_(mine or ["_"])))
        db.execute(delete(ModerationTerm).where(ModerationTerm.college_id == "col_demo_001"))
        db.commit()
    finally:
        db.close()


def test_contact_details_and_invite_links_are_refused():
    for text, words in (("S10 call me 9876543210", "phone numbers"), ("S10 mail priya.r@demo.edu", "email"),
                        ("S10 join chat.whatsapp.com/AbCdEf", "Invite links")):
        r = client.post(GROUP, json={"message_text": text}, headers=PRIYA)
        assert r.status_code == 422 and words in r.json()["detail"], text
    assert check_text(None, None, "Complexity is O(n log n) for 100000 items") is None          # numbers are fine


def test_college_terms_block_or_flag_to_the_moderation_queue():
    assert client.post("/api/v1/college/moderation/terms", json={"term": "bunk", "action": "block"}, headers=KAVITHA).status_code == 201
    assert client.post("/api/v1/college/moderation/terms", json={"term": "proxy attendance", "action": "flag"}, headers=KAVITHA).status_code == 201
    assert client.post("/api/v1/college/moderation/terms", json={"term": "bunk"}, headers=KAVITHA).status_code == 409
    assert client.post("/api/v1/college/moderation/terms", json={"term": "x y", "action": "hide"}, headers=KAVITHA).status_code == 422
    assert client.post("/api/v1/college/moderation/terms", json={"term": "abc"}, headers=ARUN).status_code == 403

    r = client.post(GROUP, json={"message_text": "S10 let us bunk the lab"}, headers=PRIYA)
    assert r.status_code == 422 and "college" in r.json()["detail"]
    assert client.post(GROUP, json={"message_text": "S10 bunker is a word"}, headers=PRIYA).status_code == 200     # whole words only
    ok = client.post(GROUP, json={"message_text": "S10 can someone give proxy attendance?"}, headers=PRIYA)
    assert ok.status_code == 200
    queue = client.get("/api/v1/trainer/moderation", headers=ARUN).json()["items"]
    assert any(i["reason"] == "Auto-flag: 'proxy attendance'" and "proxy attendance" in i["snippet"] for i in queue)    # L18

    terms = client.get("/api/v1/college/moderation/terms", headers=KAVITHA).json()["terms"]
    assert {t["term"] for t in terms} == {"bunk", "proxy attendance"}
    tid = next(t["id"] for t in terms if t["term"] == "bunk")
    assert client.delete(f"/api/v1/college/moderation/terms/{tid}", headers=_h("usr_kavitha_01", "college_admin", "col_other_test")).status_code == 404
    assert client.delete(f"/api/v1/college/moderation/terms/{tid}", headers=KAVITHA).status_code == 200


def test_flood_control():
    for _ in range(2):
        assert client.post(GROUP, json={"message_text": "S10 anyone there?"}, headers=PRIYA).status_code == 200
    assert client.post(GROUP, json={"message_text": "S10 anyone there?"}, headers=PRIYA).status_code == 429
