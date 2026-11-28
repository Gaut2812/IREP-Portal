"""Live classroom controls (screen 07), Phase 3: chat with pins, raised hands, reactions, spotlight, mute all."""
import datetime
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import LiveChatMessage, LiveHand, LiveMeeting, LiveReaction, SessionItem

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


ARUN, PRIYA = _h("usr_arun_01", "trainer"), _h("usr_priya_01", "student")


@pytest.fixture
def live():
    """A class of Priya's batch, started now (fake provider)."""
    sid, now = f"sess_t_ctl_{uuid.uuid4().hex[:6]}", datetime.datetime.now().replace(microsecond=0)
    with SessionLocal() as db:
        db.add(SessionItem(id=sid, college_id="col_demo_001", title="Controls test", batch_id="bat_aids_s5_aids", trainer_name="Arun Kumar",
                           scheduled_start=now - datetime.timedelta(minutes=5), scheduled_end=now + datetime.timedelta(minutes=55),
                           duration_min=60, session_type="Live", status="Scheduled"))
        db.flush()
        db.add(LiveMeeting(id=f"lm_{sid}", college_id="col_demo_001", session_id=sid, provider="fake", started_at=now - datetime.timedelta(minutes=4)))
        db.commit()
    yield sid
    with SessionLocal() as db:
        for model in (LiveChatMessage, LiveHand, LiveReaction, LiveMeeting):
            db.execute(delete(model).where(model.session_id == sid))
        db.execute(delete(SessionItem).where(SessionItem.id == sid))
        db.commit()


def _state(sid, headers):
    return client.get(f"/api/v1/live/{sid}", headers=headers).json()


def test_chat_is_moderated_and_the_trainer_pins(live):
    assert client.post(f"/api/v1/live/{live}/chat", headers=PRIYA, json={"text": "Is the slide deck shared?"}).status_code == 200
    assert client.post(f"/api/v1/live/{live}/chat", headers=PRIYA, json={"text": "call me 9876543210"}).status_code == 422
    msg = _state(live, ARUN)["chat"][-1]
    assert msg["author"] == "Priya R" and msg["role"] == "student"
    assert client.post(f"/api/v1/live/{live}/chat/{msg['id']}/pin", headers=PRIYA).status_code == 403
    assert client.post(f"/api/v1/live/{live}/chat/{msg['id']}/pin", headers=ARUN).json()["pinned"] is True
    assert _state(live, PRIYA)["pinned"][0]["text"] == "Is the slide deck shared?"


def test_hands_queue_in_order_and_the_trainer_lowers(live):
    assert client.post(f"/api/v1/live/{live}/hand", headers=PRIYA, json={"raised": True}).status_code == 200
    st = _state(live, ARUN)
    assert [h["name"] for h in st["hands"]] == ["Priya R"] and _state(live, PRIYA)["my_hand"] is True
    assert client.post(f"/api/v1/live/{live}/hands/usr_priya_01/lower", headers=PRIYA).status_code == 403
    assert client.post(f"/api/v1/live/{live}/hands/usr_priya_01/lower", headers=ARUN).status_code == 200
    assert _state(live, PRIYA)["my_hand"] is False


def test_reactions_spotlight_and_mute_all(live):
    assert client.post(f"/api/v1/live/{live}/react", headers=PRIYA, json={"emoji": "👏"}).status_code == 200
    assert client.post(f"/api/v1/live/{live}/react", headers=PRIYA, json={"emoji": "🍕"}).status_code == 422
    assert {"emoji": "👏", "count": 1} in _state(live, ARUN)["reactions"]
    assert client.post(f"/api/v1/live/{live}/spotlight", headers=PRIYA, json={"user_id": "usr_priya_01"}).status_code == 403
    assert client.post(f"/api/v1/live/{live}/spotlight", headers=ARUN, json={"user_id": "usr_priya_01"}).status_code == 200
    assert _state(live, PRIYA)["spotlight"]["name"] == "Priya R"
    client.post(f"/api/v1/live/{live}/spotlight", headers=ARUN, json={"user_id": None})
    assert _state(live, PRIYA)["spotlight"] is None
    assert client.post(f"/api/v1/live/{live}/mute-all", headers=ARUN).json()["success"] is True
    assert client.post(f"/api/v1/live/{live}/mute-all", headers=PRIYA).status_code == 403


def test_controls_need_a_live_class_of_my_college(live):
    with SessionLocal() as db:
        db.get(LiveMeeting, f"lm_{live}").ended_at = datetime.datetime.now()
        db.commit()
    assert client.post(f"/api/v1/live/{live}/chat", headers=PRIYA, json={"text": "hello"}).status_code == 409
    assert client.post(f"/api/v1/live/{live}/chat", headers=_h("usr_priya_01", "student", "col_other_999"), json={"text": "hi"}).status_code == 404
