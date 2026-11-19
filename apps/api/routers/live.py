"""Screen 07: Live Classroom."""
import datetime
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from core.security import require_role, TokenPayload, decode_access_token, normalize_role
from core.tenant import get_student_for_user, get_trainer_for_user, get_trainer_batch_ids
from models.schema import (
    SessionItem, LiveMeeting, JoinEvent, LivePoll, LivePollVote, QaQuestion, QaUpvote, User, Batch, Recording, Student,
)
from services.live_class import (
    get_live_adapter, ensure_meeting, record_join_event, user_presence, finalize_session, webhook_signature,
)
from services.live_sessions import join_enabled
from services.realtime import hub, publish_sync
from services.audit import record_audit

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
    rows = db.execute(
        select(JoinEvent.user_id, JoinEvent.event, JoinEvent.at).where(JoinEvent.session_id == s.id).order_by(JoinEvent.at)
    ).all()
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

    adapter = get_live_adapter()
    return {
        "session_id": s.id, "title": s.title,
        "subtext": " · ".join(x for x in [s.track, f"Sem {batch.semester}" if batch else None, f"Week {s.week_no}" if s.week_no else None, s.scheduled_start.strftime("%a")] if x),
        "trainer": s.trainer_name, "role": role, "provider": adapter.name,
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
        "poll": poll_payload, "qa": qa,
        "attendance": presence, "attendance_on_track": on_track,
    }


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
    record_join_event(db, s, current_user.sub, "joined", now)
    db.commit()
    _publish(s.id, "participants")
    adapter = get_live_adapter()
    url = adapter.join_url(m.external_meeting_id, current_user.sub, current_user.name or "", role)
    return {"success": True, "session_id": s.id, "join_url": url, "provider": adapter.name, "meeting_state": _meeting_state(m)}


@router.post("/sessions/{session_id}/leave")
def leave_session(session_id: str, current_user: TokenPayload = Depends(require_role(LIVE_ROLES)), db: Session = Depends(get_db)):
    s = _session_for_user(session_id, current_user, db)
    record_join_event(db, s, current_user.sub, "left", _now())
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
    if not m.ended_at:
        m.ended_at = now
        get_live_adapter().end_meeting(m.external_meeting_id)
    summary = finalize_session(db, s, m, now)
    record_audit(db, current_user, "live.end", "session", s.id, summary)
    db.commit()
    _publish(s.id, "ended")
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
                db.add(Recording(id=rid, college_id=s.college_id, session_id=s.id, batch_id=s.batch_id, title=s.title,
                                 storage_key=payload.get("storage_key") or f"recordings/{s.id}.mp4",
                                 duration_min=int(payload.get("duration_min") or s.duration_min), chapters=[],
                                 recorded_on=at.date(), status="ready"))
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
    payload = decode_access_token(token) if token else None
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
