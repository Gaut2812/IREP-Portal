"""Screen 07 on LiveKit: join tokens (tenant room, identity, rights), signed webhooks into
attendance (75% rule, L06), trainer moderation through the outbox, guards and production checks."""
import datetime
import json
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import httpx
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import delete, select

from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import AuditLog, JoinEvent, LiveMeeting, OutboxEvent, SessionAttendance, SessionItem, Student
from services import livekit, outbox

client = TestClient(app)
SID = "sess_livekit_it"
BATCH = "bat_aids_s5_aids"
ROOM = f"irep-col_demo_001-{SID}"


def _h(sub, role, name="x", college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": name})}


PRIYA, ARUN = _h("usr_priya_01", "student", "Priya R"), _h("usr_arun_01", "trainer", "Arun Kumar")


class FakeRoomService:
    """Just enough of LiveKit's Twirp RoomService."""

    def __init__(self):
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        token = request.headers["Authorization"].removeprefix("Bearer ")
        claims = jwt.decode(token, settings.LIVEKIT_API_SECRET, algorithms=["HS256"], options={"verify_sub": False})
        assert claims["video"]["roomAdmin"] and claims["video"]["room"] == ROOM
        body = json.loads(request.content)
        self.calls.append((method, body))
        if method == "GetParticipant":
            return httpx.Response(200, json={"identity": body["identity"], "tracks": [
                {"sid": "TR_mic", "type": "AUDIO", "source": "MICROPHONE", "muted": False},
                {"sid": "TR_cam", "type": "VIDEO", "source": "CAMERA", "muted": False}]})
        if method == "DeleteRoom" and len([c for c in self.calls if c[0] == "DeleteRoom"]) > 1:
            return httpx.Response(404, json={"code": "not_found", "msg": "room not found"})
        return httpx.Response(200, json={})


@pytest.fixture
def lk(monkeypatch):
    fake = FakeRoomService()
    monkeypatch.setattr(settings, "LIVE_CLASS_ADAPTER", "livekit")
    livekit.set_room_service_factory(lambda: livekit.RoomService("http://livekit.test", httpx.Client(transport=httpx.MockTransport(fake))))
    db = SessionLocal()
    try:
        _cleanup(db)
        start = datetime.datetime.now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=5)
        db.add(SessionItem(id=SID, college_id="col_demo_001", title="LiveKit IT: RAG review", track="AI & DS", trainer_name="Arun Kumar",
                           scheduled_start=start, scheduled_end=start + datetime.timedelta(minutes=60), duration_min=60,
                           status="Scheduled", batch_id=BATCH))
        db.commit()
    finally:
        db.close()
    yield fake
    livekit.set_room_service_factory(None)
    db = SessionLocal()
    try:
        _cleanup(db)
    finally:
        db.close()


def _cleanup(db):
    db.execute(delete(OutboxEvent).where(OutboxEvent.event_type.like("livekit.%")))
    db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id == SID))
    db.execute(delete(AuditLog).where(AuditLog.entity_id == SID))
    db.execute(delete(JoinEvent).where(JoinEvent.session_id == SID))
    db.execute(delete(SessionAttendance).where(SessionAttendance.session_id == SID))
    db.execute(delete(LiveMeeting).where(LiveMeeting.session_id == SID))
    db.execute(delete(SessionItem).where(SessionItem.id == SID))
    db.commit()


def _drain():
    return outbox.dispatch_pending(SessionLocal, limit=100_000)


def _claims(token):
    return jwt.decode(token, settings.LIVEKIT_API_SECRET, algorithms=["HS256"], options={"verify_sub": False})


def _start():
    db = SessionLocal()
    try:
        return db.get(SessionItem, SID).scheduled_start
    finally:
        db.close()


def _hook(event: str, at: datetime.datetime, identity: str = "usr_priya_01", ev_id: str = None, room: str = ROOM, sign=True):
    body = json.dumps({"event": event, "id": ev_id or f"EV_{event}_{identity}_{int(at.timestamp())}",
                       "createdAt": str(int(at.timestamp())), "room": {"name": room},
                       "participant": {"identity": identity}}).encode()
    headers = {"Content-Type": "application/webhook+json"}
    if sign:
        headers["Authorization"] = livekit.sign_webhook(body)
    return client.post("/api/v1/webhooks/livekit", content=body, headers=headers)


def _trainer_starts():
    r = client.post(f"/api/v1/sessions/{SID}/join", headers=ARUN)
    assert r.status_code == 200, r.text
    return r.json()


# ---- tokens --------------------------------------------------------------

@pytest.mark.link("L04")
def test_join_returns_a_token_for_this_college_room(lk):
    t = _trainer_starts()
    assert t["provider"] == "livekit" and t["join_url"] is None
    assert t["livekit"]["ws_url"] == settings.LIVEKIT_WS_URL and t["livekit"]["room"] == ROOM
    c = _claims(t["livekit"]["token"])
    assert c["iss"] == settings.LIVEKIT_API_KEY and c["sub"] == "usr_arun_01"
    assert c["video"]["room"] == ROOM and c["video"]["roomAdmin"] is True
    assert "screen_share" in c["video"]["canPublishSources"]
    assert json.loads(c["metadata"])["role"] == "trainer"

    s = client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA).json()
    sc = _claims(s["livekit"]["token"])
    assert sc["sub"] == "usr_priya_01" and sc["name"] == "Priya R"          # name from the DB, not the client
    assert sc["video"]["roomAdmin"] is False
    assert sorted(sc["video"]["canPublishSources"]) == ["camera", "microphone"]
    assert sc["exp"] > datetime.datetime.now().timestamp() + 3600            # lasts until 30 min after the class

    state = client.get(f"/api/v1/live/{SID}", headers=PRIYA).json()
    assert state["provider"] == "livekit" and state["participant_count"] == 0   # clicks are not presence


@pytest.mark.link("L04")
def test_live_sessions_page_opens_join_once_the_trainer_starts(lk):
    """Screen 08: Join follows the trainer starting the class, not only the clock."""
    db = SessionLocal()
    try:
        s = db.get(SessionItem, SID)
        s.scheduled_start += datetime.timedelta(hours=3)          # well outside the 10-minute window
        s.scheduled_end += datetime.timedelta(hours=3)
        db.commit()
    finally:
        db.close()
    row = lambda: next(r for r in client.get("/api/v1/student/live", headers=PRIYA).json()["week_sessions"] if r["id"] == SID)
    assert row()["join_enabled"] is False and row()["action"] != "join"
    _trainer_starts()
    r = row()
    assert r["join_enabled"] is True and r["action"] == "join" and r["status"] == "Live"
    assert client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA).status_code == 200


def test_student_cannot_get_a_token_before_the_room_opens(lk):
    db = SessionLocal()
    try:
        s = db.get(SessionItem, SID)
        s.scheduled_start += datetime.timedelta(hours=3)
        s.scheduled_end += datetime.timedelta(hours=3)
        db.commit()
    finally:
        db.close()
    assert client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA).status_code == 409


# ---- webhooks into attendance --------------------------------------------

@pytest.mark.link("L06")
def test_webhooks_drive_presence_and_the_75_percent_rule(lk):
    _trainer_starts()
    start = _start()
    assert _hook("participant_joined", start + datetime.timedelta(minutes=1)).json()["applied"] is True
    state = client.get(f"/api/v1/live/{SID}", headers=ARUN).json()
    assert [p["user_id"] for p in state["participants"]] == ["usr_priya_01"]

    # LiveKit retries: the same event id is applied once
    again = _hook("participant_joined", start + datetime.timedelta(minutes=1))
    assert again.status_code == 200 and again.json()["applied"] is False
    _hook("participant_left", start + datetime.timedelta(minutes=50))

    db = SessionLocal()
    try:
        assert db.execute(select(JoinEvent).where(JoinEvent.session_id == SID, JoinEvent.source == "livekit")).scalars().all().__len__() == 2
        # the class happened: room_finished an hour after start finalizes attendance
        m = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == SID)).scalar_one()
        m.started_at = start
        db.commit()
    finally:
        db.close()
    r = _hook("room_finished", start + datetime.timedelta(minutes=61), identity="", ev_id="EV_room_finished")
    assert r.json()["applied"] is True
    db = SessionLocal()
    try:
        priya = db.execute(select(Student).where(Student.user_id == "usr_priya_01")).scalar_one()
        row = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == SID,
                                                         SessionAttendance.student_id == priya.id)).scalar_one()
        assert row.status == "Present" and row.minutes_present == 49 and row.source == "auto"
        others = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == SID,
                                                            SessionAttendance.student_id != priya.id)).scalars().all()
        assert others and all(o.status in ("Absent", "Excused") for o in others)
        assert db.execute(select(AuditLog).where(AuditLog.entity_id == SID, AuditLog.action == "live.room_finished")).first()
    finally:
        db.close()


def test_empty_room_closing_early_does_not_end_the_class(lk):
    """A trainer's reload or dropped network empties the room; LiveKit closes it after ~20 s.
    That must not end the class or finalize attendance before the scheduled end."""
    _trainer_starts()
    start = _start()
    r = _hook("room_finished", start + datetime.timedelta(minutes=10), identity="", ev_id="EV_rf_early")
    assert r.status_code == 200 and r.json()["applied"] is False
    db = SessionLocal()
    try:
        m = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == SID)).scalar_one()
        assert m.ended_at is None and not m.finalized
        assert not db.execute(select(SessionAttendance).where(SessionAttendance.session_id == SID)).first()
    finally:
        db.close()
    # the trainer can come straight back in
    assert client.post(f"/api/v1/sessions/{SID}/join", headers=ARUN).status_code == 200


def test_webhook_signature_and_tenant_checks(lk):
    _trainer_starts()
    at = _start() + datetime.timedelta(minutes=1)
    assert _hook("participant_joined", at, sign=False).status_code == 401
    body = b'{"event":"participant_joined"}'
    forged = jwt.encode({"iss": settings.LIVEKIT_API_KEY, "sha256": livekit.body_hash(body),
                         "exp": int(datetime.datetime.now().timestamp()) + 60}, "wrong-secret", algorithm="HS256")
    assert client.post("/api/v1/webhooks/livekit", content=body, headers={"Authorization": forged}).status_code == 401
    # a valid signature over a different body is refused
    other = livekit.sign_webhook(b'{"event":"room_finished"}')
    assert client.post("/api/v1/webhooks/livekit", content=body, headers={"Authorization": other}).status_code == 401

    # unknown room, and a user from another college in our room, change nothing
    assert _hook("participant_joined", at, room="irep-col_other_999-x").json()["applied"] is False
    assert _hook("participant_joined", at, identity="usr_not_in_this_college").json()["applied"] is False


# ---- ending and moderation through the outbox ----------------------------

def test_trainer_end_finalizes_and_deletes_the_room_after_commit(lk):
    _trainer_starts()
    _hook("participant_joined", _start())
    r = client.post(f"/api/v1/sessions/{SID}/end", headers=ARUN)
    assert r.status_code == 200 and "present" in r.json()["attendance"]
    assert lk.calls == []                                          # nothing external inside the request
    _drain()
    assert [c[0] for c in lk.calls] == ["DeleteRoom"] and lk.calls[0][1] == {"room": ROOM}
    # the webhook that follows does not finalize twice
    _hook("room_finished", datetime.datetime.now(), identity="", ev_id="EV_rf2")
    db = SessionLocal()
    try:
        assert len(db.execute(select(AuditLog).where(AuditLog.entity_id == SID, AuditLog.action == "live.room_finished")).all()) == 0
    finally:
        db.close()


def test_moderation_is_audited_and_sent_by_the_outbox(lk):
    _trainer_starts()
    url = f"/api/v1/live/{SID}/participants/usr_priya_01/moderate"
    r = client.post(url, json={"action": "grant_share"}, headers=ARUN)
    assert r.status_code == 200 and r.json()["share_grants"] == ["usr_priya_01"]
    tok = client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA).json()["livekit"]["token"]
    assert "screen_share" in _claims(tok)["video"]["canPublishSources"]        # a rejoin keeps the grant
    assert client.get(f"/api/v1/live/{SID}", headers=PRIYA).json()["share_granted"] is True

    client.post(url, json={"action": "mute"}, headers=ARUN)
    client.post(url, json={"action": "revoke_share"}, headers=ARUN)
    assert lk.calls == []
    _drain()
    methods = [c[0] for c in lk.calls]
    assert methods == ["UpdateParticipant", "GetParticipant", "MutePublishedTrack", "UpdateParticipant"]
    assert lk.calls[2][1]["track_sid"] == "TR_mic"                               # only the microphone
    assert "SCREEN_SHARE" in lk.calls[0][1]["permission"]["can_publish_sources"]
    assert "SCREEN_SHARE" not in lk.calls[3][1]["permission"]["can_publish_sources"]
    db = SessionLocal()
    try:
        assert len(db.execute(select(AuditLog).where(AuditLog.entity_id == SID, AuditLog.action == "live.moderate")).all()) == 3
    finally:
        db.close()

    assert client.post(url, json={"action": "explode"}, headers=ARUN).status_code == 422


def test_guards(lk):
    _trainer_starts()
    url = f"/api/v1/live/{SID}/participants/usr_priya_01/moderate"
    assert client.post(url, json={"action": "mute"}, headers=PRIYA).status_code == 403              # students cannot moderate
    parent = _h("usr_ramesh_01", "parent")
    assert client.post(f"/api/v1/sessions/{SID}/join", headers=parent).status_code == 403
    other = _h("usr_priya_01", "student", college_id="col_other_999")
    assert client.post(f"/api/v1/sessions/{SID}/join", headers=other).status_code == 404           # other college
    other_trainer = _h("usr_arun_01", "trainer", college_id="col_other_999")
    assert client.post(url, json={"action": "mute"}, headers=other_trainer).status_code == 404
    assert client.post(f"/api/v1/live/{SID}/participants/usr_nobody/moderate", json={"action": "mute"}, headers=ARUN).status_code == 404


# ---- production --------------------------------------------------------------

def test_production_refuses_dev_livekit_keys(monkeypatch):
    from core.production import problems
    monkeypatch.setattr(settings, "LIVE_CLASS_ADAPTER", "livekit")
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "devkey")
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", "irep_dev_livekit_secret_not_for_production")
    monkeypatch.setattr(settings, "LIVEKIT_WS_URL", "ws://localhost:7880")
    out = " ".join(problems(settings))
    assert "LIVEKIT_API_SECRET" in out and "wss://" in out
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "APIirep2026")
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", "x" * 40)
    monkeypatch.setattr(settings, "LIVEKIT_WS_URL", "wss://live.irep.example")
    out = " ".join(problems(settings))
    assert "LIVEKIT" not in out and "LIVE_CLASS_ADAPTER must be" not in out
