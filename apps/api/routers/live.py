"""Screen 07: Live Classroom."""
import datetime
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db, SessionLocal
from core.security import require_role, TokenPayload, decode_access_token, websocket_user, normalize_role
from core.tenant import get_student_for_user, get_trainer_for_user, get_trainer_batch_ids
from models.schema import (
    SessionItem, LiveMeeting, JoinEvent, LivePoll, LivePollVote, QaQuestion, QaUpvote, User, Batch, Recording, Student,
    LiveChatMessage, LiveHand, LiveReaction,
)
from services.live_class import (
    get_live_adapter, ensure_meeting, record_join_event, user_presence, finalize_session, webhook_signature,
)
from services.live_sessions import join_enabled
from services.realtime import hub, publish_sync
from services.audit import record_audit
from services.teams import confirm_unmatched, queue_attendance_pull
from services import livekit

router = APIRouter(tags=["Live Classroom"])

LIVE_ROLES = ["student", "trainer"]
POLL_COLORS = ["red", "teal", "blue", "amber", "purple"]


class PollVoteRequest(BaseModel):
    option: str


class PollCreateRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    options: List[str] = Field(min_length=2, max_length=5)


class QuestionRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)


class ModerateRequest(BaseModel):
    action: str = Field(pattern="^(mute|remove|grant_share|revoke_share)$")


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _session_for_user(session_id: str, user: TokenPayload, db: Session) -> SessionItem:
    """Students reach only their batch's sessions, trainers only assigned batches."""
    s = db.execute(select(SessionItem).filter_by(id=session_id, college_id=user.college_id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    role = normalize_role(user.role)
    if role == "student":
        st = get_student_for_user(user, db)
        if s.batch_id and st.batch_id != s.batch_id:
            raise HTTPException(status_code=404, detail="Session not found")
    elif role == "trainer":
        tr = get_trainer_for_user(user, db)
        if s.batch_id and s.batch_id not in get_trainer_batch_ids(tr, db):
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")
    return s


def _meeting(db: Session, session: SessionItem) -> Optional[LiveMeeting]:
    return db.execute(select(LiveMeeting).filter_by(session_id=session.id)).scalar_one_or_none()


def _meeting_state(m: Optional[LiveMeeting]) -> str:
    if not m or not m.started_at:
        return "not_started"
    return "ended" if m.ended_at else "live"


def _publish(session_id: str, kind: str) -> None:
    publish_sync(f"live:{session_id}", {"type": kind, "session_id": session_id, "at": _now().isoformat()})


def _elapsed_label(sec: int) -> str:
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def build_state(db: Session, s: SessionItem, user: TokenPayload, now: Optional[datetime.datetime] = None) -> dict:
    now = now or _now()
    m = _meeting(db, s)
    state = _meeting_state(m)
    role = normalize_role(user.role)
    batch = db.execute(select(Batch).filter_by(id=s.batch_id)).scalar_one_or_none() if s.batch_id else None

    elapsed = 0
    if m and m.started_at:
        elapsed = int(((m.ended_at or now) - m.started_at).total_seconds())

    # participants currently in the room: last event per user is "joined"
    q = select(JoinEvent.user_id, JoinEvent.event, JoinEvent.at).where(JoinEvent.session_id == s.id)
    if m and m.provider == "livekit":
        q = q.where(JoinEvent.source == "livekit")      # who is really connected, from LiveKit's webhooks
    rows = db.execute(q.order_by(JoinEvent.at)).all()
    last = {}
    for uid, ev, at in rows:
        last[uid] = ev
    in_room = [uid for uid, ev in last.items() if ev == "joined"] if state == "live" else []
    users = {u.id: u for u in db.execute(select(User).where(User.id.in_(in_room or ["__none__"]))).scalars().all()}
    participants = []
    for uid in in_room:
        u = users.get(uid)
        if not u:
            continue
        participants.append({"user_id": uid, "name": u.name, "initials": u.avatar_initials,
                             "role": "trainer" if u.role == "trainer" else "student", "is_you": uid == user.sub})
    participants.sort(key=lambda p: (p["role"] != "trainer", not p["is_you"], p["name"]))

    # poll
    poll = db.execute(select(LivePoll).filter_by(session_id=s.id).order_by(LivePoll.created_at.desc())).scalars().first()
    poll_payload = None
    if poll:
        counts = dict(db.execute(select(LivePollVote.option_key, func.count(LivePollVote.id)).where(LivePollVote.poll_id == poll.id).group_by(LivePollVote.option_key)).all())
        total = sum(counts.values())
        mine = db.execute(select(LivePollVote.option_key).filter_by(poll_id=poll.id, user_id=user.sub)).scalar_one_or_none()
        poll_payload = {
            "id": poll.id, "question": poll.question, "is_open": poll.is_open, "total_votes": total, "my_vote": mine,
            "options": [{"key": o["key"], "text": o["text"], "color": o.get("color", "blue"), "votes": counts.get(o["key"], 0),
                         "pct": int(round(100 * counts.get(o["key"], 0) / total)) if total else 0} for o in poll.options],
        }

    # Q&A sorted by upvotes
    qs = db.execute(select(QaQuestion).filter_by(session_id=s.id, is_hidden=False)).scalars().all()
    up = dict(db.execute(select(QaUpvote.question_id, func.count(QaUpvote.id)).where(QaUpvote.question_id.in_([q.id for q in qs] or ["_"])).group_by(QaUpvote.question_id)).all())
    my_up = set(db.execute(select(QaUpvote.question_id).where(QaUpvote.user_id == user.sub)).scalars().all())
    qa = sorted([{
        "id": q.id, "author": q.author_name, "text": q.text, "upvotes": up.get(q.id, 0), "my_upvote": q.id in my_up,
        "answered_at": (f"{q.answered_at_sec // 60}:{q.answered_at_sec % 60:02d}" if q.answered_at_sec is not None else None),
    } for q in qs], key=lambda q: (-q["upvotes"], q["text"]))

    presence = user_presence(db, s, user.sub, now, m) if role == "student" else None
    on_track = None
    if presence is not None:
        remaining = max(0, s.duration_min - elapsed // 60) if state == "live" else 0
        on_track = presence["marked_present"] or (presence["minutes_present"] + remaining >= presence["threshold_minutes"] and presence["is_in_room"])

    controls = _controls_state(db, s, m, user, now)
    adapter = get_live_adapter()
    return {
        **controls,
        "session_id": s.id, "title": s.title,
        "subtext": " · ".join(x for x in [s.track, f"Sem {batch.semester}" if batch else None, f"Week {s.week_no}" if s.week_no else None, s.scheduled_start.strftime("%a")] if x),
        "trainer": s.trainer_name, "role": role, "provider": m.provider if m else adapter.name,
        "meeting": {"state": state, "started_at": m.started_at.isoformat() if m and m.started_at else None,
                    "ended_at": m.ended_at.isoformat() if m and m.ended_at else None, "is_recording": bool(m and m.is_recording and state == "live")},
        "timer": {"elapsed_sec": elapsed, "duration_sec": s.duration_min * 60, "label": f"{_elapsed_label(elapsed)} / {_elapsed_label(s.duration_min * 60)}"},
        "schedule": {"starts_at": s.scheduled_start.isoformat(), "ends_at": s.scheduled_end.isoformat(), "join_window_open": join_enabled(s, now)},
        "can_join": state == "live" or (role == "student" and join_enabled(s, now) and state != "ended") or (role == "trainer" and state != "ended"),
        "stage": {
            "sharing_user": m.sharing_user_name if m else None, "file": m.shared_file if m else None, "source": m.shared_source if m else None,
            "code": m.shared_code if m else None, "flow_title": m.flow_title if m else None, "flow_steps": (m.flow_steps if m else []) or [],
        },
        "participants": participants[:5], "more_participants": max(0, len(participants) - 5), "participant_count": len(participants),
        "all_participants": participants if role == "trainer" else [],
        "poll": poll_payload, "qa": qa,
        "attendance": presence, "attendance_on_track": on_track,
        # S13: the trainer's read-only lab view for this class (hidden once the class has ended)
        "share_granted": bool(m and role == "student" and user.sub in (m.share_grants or [])),
        "share_grants": list(m.share_grants or []) if m and role == "trainer" else [],
        "spectate": {"url": s.spectate_url, "label": s.spectate_label} if s.spectate_url and state != "ended" else None,
    }


LIVE_REACTIONS = ("👍", "👏", "❤️", "😂", "😮", "🎉")
REACTION_SHOW_SEC = 8


def _controls_state(db: Session, s: SessionItem, m: Optional[LiveMeeting], user: TokenPayload, now: datetime.datetime) -> dict:
    """Chat (pinned first), the raised-hand queue, recent reactions and the spotlight, for the class view."""
    chat = db.execute(select(LiveChatMessage).where(LiveChatMessage.session_id == s.id)
                      .order_by(LiveChatMessage.created_at.desc()).limit(60)).scalars().all()[::-1]
    hands = db.execute(select(LiveHand, User.name).join(User, User.id == LiveHand.user_id)
                       .where(LiveHand.session_id == s.id).order_by(LiveHand.raised_at)).all()
    since = datetime.datetime.utcnow() - datetime.timedelta(seconds=REACTION_SHOW_SEC)
    reactions = db.execute(select(LiveReaction.emoji, func.count(LiveReaction.id)).where(
        LiveReaction.session_id == s.id, LiveReaction.created_at >= since).group_by(LiveReaction.emoji)).all()
    spot = None
    if m and m.spotlight_user_id:
        u = db.get(User, m.spotlight_user_id)
        spot = {"user_id": m.spotlight_user_id, "name": u.name if u else ""}
    return {
        "chat": [{"id": c.id, "author": c.author_name, "role": c.author_role, "text": c.text, "pinned": c.pinned,
                  "mine": c.user_id == user.sub, "at": c.created_at.isoformat()} for c in chat],
        "pinned": [{"id": c.id, "author": c.author_name, "text": c.text} for c in chat if c.pinned],
        "hands": [{"user_id": h.user_id, "name": name, "raised_at": h.raised_at.isoformat()} for h, name in hands],
        "my_hand": any(h.user_id == user.sub for h, _ in hands),
        "reactions": [{"emoji": e, "count": n} for e, n in reactions],
        "reaction_choices": list(LIVE_REACTIONS),
        "spotlight": spot,
    }


def _live_class(session_id: str, user: TokenPayload, db: Session) -> tuple:
    s = _session_for_user(session_id, user, db)
    m = _meeting(db, s)
    if m is None or not m.started_at or m.ended_at:
        raise HTTPException(status_code=409, detail="The class is not live")
    return s, m


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class HandIn(BaseModel):
    raised: bool = True


class ReactIn(BaseModel):
    emoji: str = Field(max_length=8)


class SpotlightIn(BaseModel):
    user_id: Optional[str] = None


@router.post("/live/{session_id}/chat")
def live_chat(session_id: str, req: ChatIn, current_user: TokenPayload = Depends(require_role(["student", "trainer"])), db: Session = Depends(get_db)):
    """In-class chat. The college's moderation words apply, as in discussion groups."""
    from services.moderation import REASONS, check_text
    s, _ = _live_class(session_id, current_user, db)
    verdict = check_text(db, s.college_id, req.text)
    if verdict and verdict[0] == "block":
        raise HTTPException(status_code=422, detail=REASONS[verdict[1]])
    u = db.get(User, current_user.sub)
    msg = LiveChatMessage(id=f"lc_{uuid.uuid4().hex[:16]}", college_id=s.college_id, session_id=s.id, user_id=current_user.sub,
                          author_name=u.name if u else current_user.name, author_role=normalize_role(current_user.role), text=req.text.strip())
    db.add(msg)
    db.commit()
    _publish(s.id, "chat")
    return {"success": True, "id": msg.id}


@router.post("/live/{session_id}/chat/{message_id}/pin")
def pin_chat(session_id: str, message_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    s, _ = _live_class(session_id, current_user, db)
    msg = db.execute(select(LiveChatMessage).where(LiveChatMessage.id == message_id, LiveChatMessage.session_id == s.id)).scalar_one_or_none()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.pinned = not msg.pinned
    db.commit()
    _publish(s.id, "chat")
    return {"success": True, "pinned": msg.pinned}


@router.post("/live/{session_id}/hand")
def raise_hand(session_id: str, req: HandIn, current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    """Raise or lower my hand; the trainer sees the queue in the order hands went up."""
    s, _ = _live_class(session_id, current_user, db)
    row = db.execute(select(LiveHand).where(LiveHand.session_id == s.id, LiveHand.user_id == current_user.sub)).scalar_one_or_none()
    if req.raised and row is None:
        db.add(LiveHand(id=f"lh_{uuid.uuid4().hex[:16]}", college_id=s.college_id, session_id=s.id, user_id=current_user.sub,
                        raised_at=datetime.datetime.utcnow()))
    elif not req.raised and row is not None:
        db.delete(row)
    db.commit()
    _publish(s.id, "hands")
    return {"success": True, "raised": req.raised}


@router.post("/live/{session_id}/hands/{user_id}/lower")
def lower_hand(session_id: str, user_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    s, _ = _live_class(session_id, current_user, db)
    row = db.execute(select(LiveHand).where(LiveHand.session_id == s.id, LiveHand.user_id == user_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="That hand is not raised")
    db.delete(row)
    db.commit()
    _publish(s.id, "hands")
    return {"success": True}


@router.post("/live/{session_id}/react")
def live_react(session_id: str, req: ReactIn, current_user: TokenPayload = Depends(require_role(["student", "trainer"])), db: Session = Depends(get_db)):
    s, _ = _live_class(session_id, current_user, db)
    if req.emoji not in LIVE_REACTIONS:
        raise HTTPException(status_code=422, detail="Pick one of the offered reactions")
    db.add(LiveReaction(id=f"lr_{uuid.uuid4().hex[:16]}", college_id=s.college_id, session_id=s.id, user_id=current_user.sub, emoji=req.emoji))
    db.commit()
    _publish(s.id, "reaction")
    return {"success": True}


@router.post("/live/{session_id}/spotlight")
def spotlight(session_id: str, req: SpotlightIn, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    """Put one participant on the main stage for everyone (or clear it with user_id null)."""
    s, m = _live_class(session_id, current_user, db)
    if req.user_id:
        target = db.execute(select(User).where(User.id == req.user_id, User.college_id == s.college_id)).scalar_one_or_none()
        if target is None:
            raise HTTPException(status_code=404, detail="Participant not found")
    m.spotlight_user_id = req.user_id
    record_audit(db, current_user, "live.spotlight", "session", s.id, {"user_id": req.user_id})
    db.commit()
    _publish(s.id, "spotlight")
    return {"success": True, "spotlight_user_id": req.user_id}


@router.post("/live/{session_id}/mute-all")
def mute_all(session_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    """Mute every student in the room (LiveKit is told through the outbox after commit)."""
    s, m = _live_class(session_id, current_user, db)
    students = [p["user_id"] for p in build_state(db, s, current_user)["all_participants"] if p["role"] == "student"]
    if m.provider == "livekit":
        for uid in students:
            livekit.queue_moderation(db, s, m, uid, "mute")
    record_audit(db, current_user, "live.mute_all", "session", s.id, {"muted": len(students)})
    db.commit()
    _publish(s.id, "participants")
    return {"success": True, "muted": len(students)}


@router.get("/trainer/live/sessions")
def trainer_live_sessions(days_back: int = 14, days_ahead: int = 14, current_user: TokenPayload = Depends(require_role(["trainer"])),
                          db: Session = Depends(get_db)):
    """The trainer's live classroom hub: classes of my batches from two weeks back to two weeks ahead, each with its
    meeting state, so a class can be started, rejoined or reviewed (the sidebar used to open one fixed class)."""
    from models.schema import SessionAttendance
    tr = get_trainer_for_user(current_user, db)
    batches = get_trainer_batch_ids(tr, db)
    now = _now()
    days_back, days_ahead = max(0, min(days_back, 60)), max(0, min(days_ahead, 60))
    rows = db.execute(select(SessionItem).where(
        SessionItem.college_id == current_user.college_id, SessionItem.batch_id.in_(batches or ["_"]),
        SessionItem.scheduled_start >= now - datetime.timedelta(days=days_back),
        SessionItem.scheduled_start <= now + datetime.timedelta(days=days_ahead)).order_by(SessionItem.scheduled_start)).scalars().all()
    ids = [r.id for r in rows]
    meetings = {m.session_id: m for m in db.execute(select(LiveMeeting).where(LiveMeeting.session_id.in_(ids or ["_"]))).scalars()}
    att = {}
    for sid, status_, n in db.execute(select(SessionAttendance.session_id, SessionAttendance.status, func.count(SessionAttendance.id))
                                      .where(SessionAttendance.session_id.in_(ids or ["_"])).group_by(SessionAttendance.session_id, SessionAttendance.status)):
        att.setdefault(sid, {})[status_] = n
    recs = {r.session_id: r.id for r in db.execute(select(Recording).where(Recording.session_id.in_(ids or ["_"]), Recording.status == "ready")).scalars()}
    names = dict(db.execute(select(Batch.id, Batch.name).where(Batch.id.in_(batches or ["_"]))).all())

    def out(s: SessionItem) -> dict:
        state = "cancelled" if s.status == "Cancelled" else _meeting_state(meetings.get(s.id))
        if state == "not_started" and s.scheduled_end <= now:
            state = "missed_start"                     # the time passed and nobody started it
        a = att.get(s.id, {})
        return {"id": s.id, "title": s.title, "batch": names.get(s.batch_id), "starts_at": s.scheduled_start.isoformat(),
                "ends_at": s.scheduled_end.isoformat(), "room": s.room, "type": s.session_type, "state": state,
                "can_start": state == "not_started" and s.scheduled_start - datetime.timedelta(minutes=30) <= now < s.scheduled_end,
                "present": a.get("Present", 0) + a.get("Late", 0), "marked": sum(a.values()), "recording_id": recs.get(s.id)}

    items = [out(s) for s in rows]
    live = [i for i in items if i["state"] == "live"]
    upcoming = [i for i in items if i["state"] == "not_started"]
    past = [i for i in reversed(items) if i["state"] in ("ended", "missed_start", "cancelled")]
    return {"live": live, "upcoming": upcoming, "past": past}


@router.get("/live/{session_id}")
def get_live_state(session_id: str, current_user: TokenPayload = Depends(require_role(LIVE_ROLES)), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    return build_state(db, s, current_user)


@router.post("/sessions/{session_id}/join")
def join_session(session_id: str, current_user: TokenPayload = Depends(require_role(LIVE_ROLES)), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    now = _now()
    m = ensure_meeting(db, s)
    role = normalize_role(current_user.role)
    if m.ended_at:
        raise HTTPException(status_code=409, detail="This session has ended")
    if role == "trainer":
        if not m.started_at:
            m.started_at = now
            record_audit(db, current_user, "live.start", "session", s.id)
    elif not m.started_at and not join_enabled(s, now):
        raise HTTPException(status_code=409, detail="The room opens 10 minutes before the session starts")
    if m.provider == "teams":
        # attendance comes from the Teams report; the click is kept for support only
        record_join_event(db, s, current_user.sub, "joined", now, source="click")
        db.commit()
        if not m.join_url:
            raise HTTPException(status_code=409, detail="The Teams meeting is still being set up. Try again in a minute.")
        return {"success": True, "session_id": s.id, "join_url": m.join_url, "provider": "teams", "meeting_state": _meeting_state(m)}
    if m.provider == "livekit":
        # attendance comes from LiveKit's webhooks; the click is kept for support only
        me = db.execute(select(User).where(User.id == current_user.sub, User.college_id == current_user.college_id)).scalar_one_or_none()
        if me is None:
            raise HTTPException(status_code=404, detail="User not found")
        record_join_event(db, s, current_user.sub, "joined", now, source="click")
        token = livekit.join_token(s, m, me, role, now)
        db.commit()
        return {"success": True, "session_id": s.id, "join_url": None, "provider": "livekit", "meeting_state": _meeting_state(m),
                "livekit": {"ws_url": settings.LIVEKIT_WS_URL, "token": token, "room": m.external_meeting_id}}
    record_join_event(db, s, current_user.sub, "joined", now)
    db.commit()
    _publish(s.id, "participants")
    adapter = get_live_adapter()
    url = adapter.join_url(m.external_meeting_id, current_user.sub, current_user.name or "", role)
    return {"success": True, "session_id": s.id, "join_url": url, "provider": adapter.name, "meeting_state": _meeting_state(m)}


@router.post("/sessions/{session_id}/leave")
def leave_session(session_id: str, current_user: TokenPayload = Depends(require_role(LIVE_ROLES)), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    m = _meeting(db, s)
    source = "click" if m and m.provider in ("teams", "livekit") else "portal"
    record_join_event(db, s, current_user.sub, "left", _now(), source=source)
    db.commit()
    _publish(s.id, "participants")
    return {"success": True}


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    m = ensure_meeting(db, s)
    if not m.started_at:
        raise HTTPException(status_code=409, detail="The session has not started")
    now = _now()
    if m.provider == "teams":
        # Teams publishes the attendance report a few minutes after the meeting:
        # the outbox pulls it and applies the 75% rule then.
        if not m.ended_at:
            m.ended_at = now
        queue_attendance_pull(db, s)
        record_audit(db, current_user, "live.end", "session", s.id, {"attendance": "pending_teams_report"})
        db.commit()
        _publish(s.id, "ended")
        return {"success": True, "attendance": {"pending": True}}
    if not m.ended_at:
        m.ended_at = now
        if m.provider == "livekit":
            livekit.queue_end_room(db, s, m)      # disconnects everyone, after commit (rule 3)
        else:
            get_live_adapter().end_meeting(m.external_meeting_id)
    summary = finalize_session(db, s, m, now)
    record_audit(db, current_user, "live.end", "session", s.id, summary)
    db.commit()
    _publish(s.id, "ended")
    return {"success": True, "attendance": summary}


# ---- Teams attendance: names the report could not match (trainer confirms) ----
class ConfirmAttendeeIn(BaseModel):
    index: int
    student_id: str


@router.get("/trainer/sessions/{session_id}/teams-unmatched")
def teams_unmatched(session_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    m = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == s.id)).scalar_one_or_none()
    rows = (m.unmatched_attendees or []) if m else []
    return {"session_id": s.id, "pulled_at": m.attendance_pulled_at.isoformat() if m and m.attendance_pulled_at else None,
            "unmatched": [{"index": i, "name": r["name"], "email": r.get("email"), "minutes": r.get("minutes", 0)} for i, r in enumerate(rows)]}


@router.post("/trainer/sessions/{session_id}/teams-unmatched/confirm")
def teams_confirm(session_id: str, req: ConfirmAttendeeIn, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    m = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == s.id)).scalar_one_or_none()
    student = db.execute(select(Student).where(Student.id == req.student_id, Student.college_id == current_user.college_id,
                                               Student.batch_id == s.batch_id)).scalar_one_or_none()
    if m is None or student is None:
        raise HTTPException(status_code=404, detail="Session or student not found in this batch")
    try:
        summary = confirm_unmatched(db, s, m, req.index, student)
    except IndexError:
        raise HTTPException(status_code=404, detail="That attendee is no longer waiting for confirmation")
    record_audit(db, current_user, "attendance.teams_confirmed", "session", s.id, {"student_id": student.id})
    db.commit()
    return {"success": True, "attendance": summary}


@router.post("/live/{session_id}/polls")
def create_poll(session_id: str, req: PollCreateRequest, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    for p in db.execute(select(LivePoll).filter_by(session_id=s.id, is_open=True)).scalars().all():
        p.is_open = False
    keys = "abcde"
    poll = LivePoll(id=f"poll_{uuid.uuid4().hex[:14]}", college_id=s.college_id, session_id=s.id, question=req.question.strip(),
                    options=[{"key": keys[i], "text": o.strip(), "color": POLL_COLORS[i % len(POLL_COLORS)]} for i, o in enumerate(req.options)],
                    is_open=True, created_by=current_user.sub)
    db.add(poll)
    db.commit()
    _publish(s.id, "poll")
    return {"success": True, "poll_id": poll.id}


@router.post("/live/{session_id}/poll/vote")
def vote_live_poll(session_id: str, req: PollVoteRequest, current_user: TokenPayload = Depends(require_role(LIVE_ROLES)), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    poll = db.execute(select(LivePoll).filter_by(session_id=s.id, is_open=True).order_by(LivePoll.created_at.desc())).scalars().first()
    if not poll:
        raise HTTPException(status_code=404, detail="No open poll")
    if req.option not in {o["key"] for o in poll.options}:
        raise HTTPException(status_code=422, detail="Unknown option")
    vote = db.execute(select(LivePollVote).filter_by(poll_id=poll.id, user_id=current_user.sub)).scalar_one_or_none()
    if vote:
        raise HTTPException(status_code=409, detail="You have already voted")
    db.add(LivePollVote(id=f"pv_{uuid.uuid4().hex[:16]}", college_id=s.college_id, poll_id=poll.id, user_id=current_user.sub, option_key=req.option))
    db.commit()
    _publish(s.id, "poll")
    return {"success": True, "message": "Vote recorded."}


@router.post("/live/{session_id}/qa")
def ask_question(session_id: str, req: QuestionRequest, current_user: TokenPayload = Depends(require_role(LIVE_ROLES)), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    from services.moderation import contains_blocked
    if contains_blocked(req.text):
        raise HTTPException(status_code=422, detail="Please rephrase: the message contains blocked words")
    q = QaQuestion(id=f"qa_{uuid.uuid4().hex[:14]}", college_id=s.college_id, session_id=s.id, author_user_id=current_user.sub,
                   author_name=current_user.name or "Student", text=req.text.strip())
    db.add(q)
    db.commit()
    _publish(s.id, "qa")
    return {"success": True, "question_id": q.id}


@router.post("/live/{session_id}/qa/{question_id}/upvote")
def upvote_question(session_id: str, question_id: str, current_user: TokenPayload = Depends(require_role(LIVE_ROLES)), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    q = db.execute(select(QaQuestion).filter_by(id=question_id, session_id=s.id)).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    existing = db.execute(select(QaUpvote).filter_by(question_id=q.id, user_id=current_user.sub)).scalar_one_or_none()
    if existing:
        db.delete(existing)   # toggle
        upvoted = False
    else:
        db.add(QaUpvote(id=f"qu_{uuid.uuid4().hex[:16]}", college_id=s.college_id, question_id=q.id, user_id=current_user.sub))
        upvoted = True
    db.commit()
    _publish(s.id, "qa")
    count = db.execute(select(func.count(QaUpvote.id)).filter_by(question_id=q.id)).scalar_one()
    return {"success": True, "upvoted": upvoted, "upvotes": count}


@router.post("/live/{session_id}/qa/{question_id}/answered")
def mark_answered(session_id: str, question_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    q = db.execute(select(QaQuestion).filter_by(id=question_id, session_id=s.id)).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    m = _meeting(db, s)
    q.answered_at_sec = int((_now() - m.started_at).total_seconds()) if m and m.started_at else 0
    db.commit()
    _publish(s.id, "qa")
    return {"success": True, "answered_at_sec": q.answered_at_sec}


@router.post("/live/{session_id}/participants/{user_id}/moderate")
def moderate_participant(session_id: str, user_id: str, req: ModerateRequest,
                         current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    """Trainer controls on a LiveKit class: mute, remove, allow or revoke screen share.
    Recorded and audited here; LiveKit is told by the outbox after commit."""
    s = _session_for_user(session_id, current_user, db)
    m = _meeting(db, s)
    if m is None or m.provider != "livekit":
        raise HTTPException(status_code=409, detail="Participant controls need the LiveKit classroom")
    if not m.started_at or m.ended_at:
        raise HTTPException(status_code=409, detail="The class is not live")
    target = db.execute(select(User).where(User.id == user_id, User.college_id == s.college_id)).scalar_one_or_none()
    if target is None or target.id == current_user.sub:
        raise HTTPException(status_code=404, detail="Participant not found")
    grants = list(m.share_grants or [])
    if req.action == "grant_share" and target.id not in grants:
        grants.append(target.id)
    elif req.action == "revoke_share" and target.id in grants:
        grants.remove(target.id)
    m.share_grants = grants
    livekit.queue_moderation(db, s, m, target.id, req.action)
    record_audit(db, current_user, "live.moderate", "session", s.id, {"user_id": target.id, "action": req.action})
    db.commit()
    _publish(s.id, "participants")
    return {"success": True, "action": req.action, "share_grants": grants}


@router.post("/webhooks/livekit")
async def livekit_webhook(request: Request, authorization: Optional[str] = Header(default=None)):
    """LiveKit server callbacks, signed with LIVEKIT_API_SECRET (JWT with the body's sha256)."""
    body = await request.body()
    if not livekit.verify_webhook(body, authorization):
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    db = SessionLocal()
    try:
        result = livekit.handle_webhook(db, payload)
        db.commit()
    finally:
        db.close()
    if result["session_id"] and result["applied"]:
        kind = "ended" if result["event"] == "room_finished" else "participants"
        await hub.publish(f"live:{result['session_id']}", {"type": kind, "session_id": result["session_id"]})
    return {"success": True, **result}


@router.post("/webhooks/bbb")
async def bbb_webhook(request: Request, x_bbb_signature: Optional[str] = Header(default=None, alias="X-BBB-Signature")):
    """BigBlueButton callbacks (signed with BBB_SECRET). Events:
    user-joined / user-left -> join_events; meeting-ended -> finalize attendance;
    rap-publish-ended -> recording row."""
    body = await request.body()
    if not x_bbb_signature or x_bbb_signature != webhook_signature(body):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = json.loads(body or b"{}")
    event = payload.get("event")
    meeting_id = payload.get("meeting_id", "")
    session_id = meeting_id[len("irep-"):] if meeting_id.startswith("irep-") else meeting_id
    at = datetime.datetime.fromisoformat(payload["at"]) if payload.get("at") else _now()
    db = SessionLocal()
    try:
        s = db.execute(select(SessionItem).filter_by(id=session_id)).scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail="Unknown meeting")
        m = ensure_meeting(db, s)
        if event in ("user-joined", "user-left"):
            if not m.started_at and event == "user-joined":
                m.started_at = at
            record_join_event(db, s, payload["user_id"], "joined" if event == "user-joined" else "left", at, source="webhook")
        elif event == "meeting-ended":
            m.ended_at = m.ended_at or at
            finalize_session(db, s, m, at)
        elif event == "rap-publish-ended":
            rid = f"rec_{s.id}"[:64]
            if not db.execute(select(Recording).filter_by(id=rid)).first():
                from services.quotas import can_store_recording
                size_mb = max(0, int(payload.get("size_mb") or 0))
                fits = can_store_recording(db, s.college_id, size_mb)         # L36: the MoU's storage_gb
                db.add(Recording(id=rid, college_id=s.college_id, session_id=s.id, batch_id=s.batch_id, title=s.title,
                                 storage_key=payload.get("storage_key") or f"recordings/{s.id}.mp4",
                                 duration_min=int(payload.get("duration_min") or s.duration_min), chapters=[],
                                 recorded_on=at.date(), status="ready" if fits else "over_quota", size_mb=size_mb))
        else:
            return {"success": True, "ignored": event}
        db.commit()
    finally:
        db.close()
    await hub.publish(f"live:{session_id}", {"type": event, "session_id": session_id})
    return {"success": True, "event": event}


@router.websocket("/ws/live/{session_id}")
async def live_socket(websocket: WebSocket, session_id: str, token: Optional[str] = None):
    """Push channel: clients get {type} pings and refetch state."""
    payload = websocket_user(token)          # local or Keycloak token, and still active
    if not payload:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        _session_for_user(session_id, payload, db)
    except HTTPException:
        await websocket.close(code=4404)
        return
    finally:
        db.close()
    channel = f"live:{session_id}"
    await hub.subscribe(channel, websocket)
    try:
        while True:
            await websocket.receive_text()   # keepalive pings from the client
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(channel, websocket)
