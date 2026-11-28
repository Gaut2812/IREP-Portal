"""Screen 07 on LiveKit (LIVE_CLASS_ADAPTER=livekit): open-source audio, video and screen share.

- Join tokens are HS256 JWTs minted here (no network call). The room name carries the
  college id and identity is `users.id`, both from the verified caller, never the client.
- LiveKit calls POST /webhooks/livekit with a JWT in `Authorization` whose `sha256`
  claim is the base64 sha256 of the body. participant_joined/left become JoinEvents
  (source="livekit"), room_finished finalizes attendance (75% rule, L06).
- Server calls (end the room, mute, remove, change screen-share permission) go through
  the outbox (rule 3) to LiveKit's RoomService (Twirp over HTTP). Handlers are idempotent.
"""
import base64
import datetime
import hashlib
import hmac
import json
import time
from typing import Optional

import httpx
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import JoinEvent, LiveMeeting, SessionItem, User
from services.outbox import emit, handler as outbox_handler

PROVIDER = "livekit"
STUDENT_SOURCES = ["camera", "microphone"]
SHARE_SOURCES = ["screen_share", "screen_share_audio"]
MODERATION_ACTIONS = ("mute", "remove", "grant_share", "revoke_share")


class LiveKitError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def room_name(session: SessionItem) -> str:
    return f"irep-{session.college_id}-{session.id}"[:128]


def _jwt(claims: dict, ttl_seconds: int) -> str:
    now = int(time.time())
    body = {"iss": settings.LIVEKIT_API_KEY, "nbf": now - 10, "exp": now + ttl_seconds, **claims}
    return jwt.encode(body, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def join_token(session: SessionItem, meeting: LiveMeeting, user: User, role: str,
               now: Optional[datetime.datetime] = None) -> str:
    """Token for one person in one class. Trainers moderate and share; students get
    camera and mic, and screen share only when the trainer granted it."""
    now = now or datetime.datetime.now()
    end = session.scheduled_end or session.scheduled_start + datetime.timedelta(minutes=session.duration_min)
    expires = max(end + datetime.timedelta(minutes=30), now + datetime.timedelta(minutes=15))
    is_trainer = role == "trainer"
    sources = STUDENT_SOURCES + SHARE_SOURCES if is_trainer or user.id in (meeting.share_grants or []) else STUDENT_SOURCES
    video = {"room": meeting.external_meeting_id, "roomJoin": True, "canSubscribe": True, "canPublish": True,
             "canPublishData": True, "canPublishSources": sources, "roomAdmin": is_trainer}
    metadata = {"role": "trainer" if is_trainer else "student", "initials": user.avatar_initials or ""}
    return _jwt({"sub": user.id, "name": user.name, "video": video, "metadata": json.dumps(metadata)},
                max(60, int((expires - now).total_seconds())))


def _admin_token(room: str, *, create: bool = False) -> str:
    video = {"room": room, "roomAdmin": True}
    if create:
        video["roomCreate"] = True             # DeleteRoom needs roomCreate
    return _jwt({"video": video}, 300)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def body_hash(body: bytes) -> str:
    return base64.b64encode(hashlib.sha256(body).digest()).decode()


def sign_webhook(body: bytes) -> str:
    """What livekit-server sends in `Authorization` (used by tests and the dev simulator)."""
    return _jwt({"sha256": body_hash(body)}, 300)


def verify_webhook(body: bytes, authorization: Optional[str]) -> bool:
    if not authorization:
        return False
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    try:
        claims = jwt.decode(token, settings.LIVEKIT_API_SECRET, algorithms=["HS256"],
                            options={"verify_aud": False, "verify_sub": False})
    except JWTError:
        return False
    if claims.get("iss") != settings.LIVEKIT_API_KEY:
        return False
    return hmac.compare_digest(str(claims.get("sha256", "")), body_hash(body))


def _event_time(payload: dict) -> datetime.datetime:
    raw = payload.get("createdAt") or payload.get("created_at")
    try:
        return datetime.datetime.fromtimestamp(int(raw))      # campus-local naive, like session times
    except (TypeError, ValueError):
        return datetime.datetime.now()


def handle_webhook(db: Session, payload: dict) -> dict:
    """Apply one LiveKit webhook. Returns {"session_id", "event", "applied"}; never raises for
    rooms or people we do not know (LiveKit would only retry)."""
    from services.live_class import finalize_session
    from services.audit import record_audit

    event = payload.get("event") or ""
    room = (payload.get("room") or {}).get("name") or ""
    m = db.execute(select(LiveMeeting).where(LiveMeeting.external_meeting_id == room,
                                             LiveMeeting.provider == PROVIDER)).scalar_one_or_none()
    if m is None:
        return {"session_id": None, "event": event, "applied": False}
    s = db.execute(select(SessionItem).where(SessionItem.id == m.session_id,
                                             SessionItem.college_id == m.college_id)).scalar_one_or_none()
    if s is None:
        return {"session_id": None, "event": event, "applied": False}
    at = _event_time(payload)
    ext_id = (payload.get("id") or "")[:64] or None

    if event in ("participant_joined", "participant_left"):
        identity = (payload.get("participant") or {}).get("identity") or ""
        user = db.execute(select(User).where(User.id == identity, User.college_id == s.college_id)).scalar_one_or_none()
        if user is None:
            return {"session_id": s.id, "event": event, "applied": False}      # not one of this college's users
        if ext_id and db.execute(select(JoinEvent.id).where(JoinEvent.external_id == ext_id)).first():
            return {"session_id": s.id, "event": event, "applied": False}      # retry of an event we already have
        kind = "joined" if event == "participant_joined" else "left"
        if kind == "joined" and not m.started_at:
            m.started_at = at
        db.add(JoinEvent(id=f"je_lk_{hashlib.sha1((ext_id or f'{identity}{at}{kind}').encode()).hexdigest()[:24]}",
                         college_id=s.college_id, session_id=s.id, user_id=user.id, event=kind, at=at,
                         source=PROVIDER, external_id=ext_id))
        try:
            db.flush()
        except IntegrityError:                                                 # concurrent retry won the race
            db.rollback()
            return {"session_id": s.id, "event": event, "applied": False}
        return {"session_id": s.id, "event": event, "applied": True}

    if event == "room_finished":
        # LiveKit closes a room ~20 s after the last person leaves. Before the scheduled end that is a
        # reload or a dropped network, not the end of the class: the room is recreated on the next join.
        # Only the trainer's End button, or the room closing after the scheduled end, ends the class.
        scheduled_end = s.scheduled_end or s.scheduled_start + datetime.timedelta(minutes=s.duration_min)
        if not m.ended_at and at < scheduled_end:
            return {"session_id": s.id, "event": event, "applied": False}
        if not m.ended_at:
            m.ended_at = at
        if not m.finalized:
            summary = finalize_session(db, s, m, at)
            record_audit(db, None, "live.room_finished", "session", s.id, summary, college_id=s.college_id)
        return {"session_id": s.id, "event": event, "applied": True}

    return {"session_id": s.id, "event": event, "applied": False}


# ---------------------------------------------------------------------------
# RoomService (called only from outbox handlers)
# ---------------------------------------------------------------------------

class RoomService:
    def __init__(self, base_url: str, client: Optional[httpx.Client] = None):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=10)

    def call(self, method: str, room: str, body: dict, *, create: bool = False) -> dict:
        r = self.client.post(f"{self.base_url}/twirp/livekit.RoomService/{method}", json=body,
                             headers={"Authorization": f"Bearer {_admin_token(room, create=create)}"})
        if r.status_code == 404 or (r.status_code >= 400 and _twirp_code(r) == "not_found"):
            return {"not_found": True}
        if r.status_code >= 400:
            raise LiveKitError(f"LiveKit {method} failed: {r.status_code} {r.text[:200]}")
        return r.json() if r.content else {}


def _twirp_code(r: httpx.Response) -> str:
    try:
        return (r.json() or {}).get("code", "")
    except ValueError:
        return ""


_factory = None


def get_room_service() -> RoomService:
    return _factory() if _factory else RoomService(settings.LIVEKIT_URL)


def set_room_service_factory(factory) -> None:
    """Tests swap in a RoomService over httpx.MockTransport."""
    global _factory
    _factory = factory


def queue_end_room(db: Session, session: SessionItem, meeting: LiveMeeting) -> None:
    emit(db, "livekit.end_room", {"room": meeting.external_meeting_id}, college_id=session.college_id,
         entity_type="session", entity_id=session.id)


def queue_moderation(db: Session, session: SessionItem, meeting: LiveMeeting, user_id: str, action: str) -> None:
    emit(db, "livekit.moderate", {"room": meeting.external_meeting_id, "identity": user_id, "action": action},
         college_id=session.college_id, entity_type="session", entity_id=session.id)


@outbox_handler("livekit.end_room")
def _end_room(db: Session, event) -> None:
    room = event.payload["room"]
    get_room_service().call("DeleteRoom", room, {"room": room}, create=True)      # gone already = done


@outbox_handler("livekit.moderate")
def _moderate(db: Session, event) -> None:
    p = event.payload
    room, identity, action = p["room"], p["identity"], p["action"]
    svc = get_room_service()
    if action == "remove":
        svc.call("RemoveParticipant", room, {"room": room, "identity": identity})
    elif action == "mute":
        info = svc.call("GetParticipant", room, {"room": room, "identity": identity})
        for t in info.get("tracks") or []:
            if (t.get("source") in ("MICROPHONE", 2) or t.get("type") in ("AUDIO", 0)) and not t.get("muted"):
                svc.call("MutePublishedTrack", room, {"room": room, "identity": identity, "track_sid": t["sid"], "muted": True})
    elif action in ("grant_share", "revoke_share"):
        sources = ["CAMERA", "MICROPHONE"] + (["SCREEN_SHARE", "SCREEN_SHARE_AUDIO"] if action == "grant_share" else [])
        svc.call("UpdateParticipant", room, {"room": room, "identity": identity, "permission": {
            "can_subscribe": True, "can_publish": True, "can_publish_data": True, "can_publish_sources": sources}})
