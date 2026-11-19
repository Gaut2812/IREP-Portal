"""Screen 07 live classroom: video-platform adapter, presence and auto attendance.

`LIVE_CLASS_ADAPTER=fake` (default) keeps the whole classroom inside the
portal: the stage (shared notebook + flow panel), polls, Q&A and presence
all come from our tables. `LIVE_CLASS_ADAPTER=bbb` returns signed
BigBlueButton join URLs (BBB_URL / BBB_SECRET); BBB then calls
POST /webhooks/bbb with user-joined / user-left / meeting-ended /
rap-publish-ended events which land in the same tables.
"""
import datetime
import hashlib
import hmac
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import (
    LiveMeeting, JoinEvent, SessionItem, SessionAttendance, Student, User,
)

PRESENT_RATIO = 0.75


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

class LiveClassAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def create_meeting(self, session: SessionItem) -> str:
        """Create (or ensure) the remote meeting and return its id."""

    @abstractmethod
    def join_url(self, meeting_id: str, user_id: str, full_name: str, role: str) -> Optional[str]:
        """Signed URL that drops the user into the room, or None for the in-portal stage."""

    def end_meeting(self, meeting_id: str) -> None:
        return None


class FakeLiveClassAdapter(LiveClassAdapter):
    name = "fake"

    def create_meeting(self, session: SessionItem) -> str:
        return f"irep-{session.id}"

    def join_url(self, meeting_id, user_id, full_name, role):
        return None


class BBBAdapter(LiveClassAdapter):
    """BigBlueButton API: checksum = sha1(call + query + secret)."""
    name = "bbb"

    def __init__(self, base_url: str, secret: str):
        self.base_url = base_url.rstrip("/")
        self.secret = secret

    def _url(self, call: str, params: Dict[str, str]) -> str:
        query = urllib.parse.urlencode(params)
        checksum = hashlib.sha1(f"{call}{query}{self.secret}".encode()).hexdigest()
        return f"{self.base_url}/api/{call}?{query}&checksum={checksum}"

    def create_meeting(self, session: SessionItem) -> str:
        # The create call itself is issued by the worker; here we only return the deterministic id.
        return f"irep-{session.id}"

    def create_url(self, session: SessionItem) -> str:
        return self._url("create", {"meetingID": f"irep-{session.id}", "name": session.title, "record": "true",
                                    "meta_endCallbackUrl": f"{settings.PUBLIC_BASE_URL}/api/v1/webhooks/bbb"})

    def join_url(self, meeting_id, user_id, full_name, role):
        return self._url("join", {"meetingID": meeting_id, "fullName": full_name, "userID": user_id,
                                  "role": "MODERATOR" if role in ("trainer", "college_admin") else "VIEWER", "redirect": "true"})


class TeamsAdapter(LiveClassAdapter):
    """Microsoft Teams via Graph calendar events (services/teams.py).
    The event is created by the outbox worker; the join URL lives on LiveMeeting."""
    name = "teams"

    def create_meeting(self, session: SessionItem) -> str:
        return f"irep-{session.id}"          # also the Graph transactionId

    def join_url(self, meeting_id, user_id, full_name, role):
        return None                           # router returns LiveMeeting.join_url


def get_live_adapter() -> LiveClassAdapter:
    name = (getattr(settings, "LIVE_CLASS_ADAPTER", None) or "fake").lower()
    if name == "teams":
        return TeamsAdapter()
    if name == "bbb" and settings.BBB_SECRET:
        return BBBAdapter(settings.BBB_URL, settings.BBB_SECRET)
    return FakeLiveClassAdapter()


def webhook_signature(body: bytes) -> str:
    return hmac.new(settings.BBB_SECRET.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Presence maths
# ---------------------------------------------------------------------------

def presence_intervals(events: List[Tuple[str, datetime.datetime]], until: datetime.datetime) -> List[Tuple[datetime.datetime, datetime.datetime]]:
    """Turn a time-ordered joined/left stream into closed intervals. A join
    without a matching leave stays open until `until`; duplicate joins are
    ignored; a leave without a join is ignored."""
    intervals = []
    open_at = None
    for kind, at in sorted(events, key=lambda e: e[1]):
        if kind == "joined":
            if open_at is None:
                open_at = at
        elif kind == "left":
            if open_at is not None:
                if at > open_at:
                    intervals.append((open_at, at))
                open_at = None
    if open_at is not None and until > open_at:
        intervals.append((open_at, until))
    return intervals


def covered_minutes(intervals, window_start: datetime.datetime, window_end: datetime.datetime) -> float:
    """Minutes covered by the union of intervals, clipped to the window
    (overlapping intervals from duplicate tabs are not double counted)."""
    clipped = sorted((max(a, window_start), min(b, window_end)) for a, b in intervals if b > window_start and a < window_end)
    total = 0.0
    cur_a = cur_b = None
    for a, b in clipped:
        if cur_b is None or a > cur_b:
            if cur_b is not None:
                total += (cur_b - cur_a).total_seconds()
            cur_a, cur_b = a, b
        else:
            cur_b = max(cur_b, b)
    if cur_b is not None:
        total += (cur_b - cur_a).total_seconds()
    return total / 60.0


def session_window(session: SessionItem, meeting: Optional[LiveMeeting]) -> Tuple[datetime.datetime, datetime.datetime]:
    start = session.scheduled_start
    if meeting and meeting.started_at and meeting.started_at < start:
        start = meeting.started_at
    end = start + datetime.timedelta(minutes=session.duration_min)
    if meeting and meeting.ended_at and meeting.ended_at > end:
        end = meeting.ended_at
    return start, end


def user_presence(db: Session, session: SessionItem, user_id: str, now: datetime.datetime,
                  meeting: Optional[LiveMeeting] = None) -> dict:
    q = select(JoinEvent.event, JoinEvent.at).where(JoinEvent.session_id == session.id, JoinEvent.user_id == user_id)
    if meeting is not None and meeting.provider == "teams":
        q = q.where(JoinEvent.source == "teams")     # a "Join in Teams" click is not attendance
    events = db.execute(q).all()
    start, end = session_window(session, meeting)
    until = min(now, meeting.ended_at) if meeting and meeting.ended_at else now
    intervals = presence_intervals([(e, a) for e, a in events], until)
    minutes = covered_minutes(intervals, start, end)
    threshold = session.duration_min * PRESENT_RATIO
    joined_first = min((a for e, a in events if e == "joined"), default=None)
    return {
        "minutes_present": int(minutes),
        "total_minutes": session.duration_min,
        "threshold_minutes": int(round(threshold)),
        "threshold_pct": int(PRESENT_RATIO * 100),
        "marked_present": minutes >= threshold,
        "joined_at": joined_first.isoformat() if joined_first else None,
        "is_in_room": bool(events) and sorted(events, key=lambda e: e[1])[-1][0] == "joined" and not (meeting and meeting.ended_at),
    }


def finalize_session(db: Session, session: SessionItem, meeting: Optional[LiveMeeting], now: datetime.datetime) -> Dict[str, int]:
    """Meeting ended: compute presence for every student in the batch and upsert
    attendance (Present at >= 75% of scheduled time). Manual overrides win."""
    students = db.execute(select(Student).filter_by(batch_id=session.batch_id, college_id=session.college_id)).scalars().all()
    present = absent = 0
    for st in students:
        p = user_presence(db, session, st.user_id, now, meeting)
        status = "Present" if p["marked_present"] else "Absent"
        row = db.execute(select(SessionAttendance).filter_by(session_id=session.id, student_id=st.id)).scalar_one_or_none()
        if row and row.source == "manual":
            continue
        if row:
            row.status, row.minutes_present, row.source, row.marked_at = status, p["minutes_present"], "auto", now
        else:
            db.add(SessionAttendance(id=("att_" + session.id + "_" + st.id)[:64], college_id=session.college_id, session_id=session.id,
                                     student_id=st.id, minutes_present=p["minutes_present"], status=status, source="auto", marked_at=now))
        if status == "Present":
            present += 1
        else:
            absent += 1
    if meeting:
        meeting.finalized = True
    return {"present": present, "absent": absent}


def record_join_event(db: Session, session: SessionItem, user_id: str, event: str, at: datetime.datetime, source: str = "portal") -> JoinEvent:
    je = JoinEvent(id=f"je_{uuid.uuid4().hex[:18]}", college_id=session.college_id, session_id=session.id,
                   user_id=user_id, event=event, at=at, source=source)
    db.add(je)
    return je


def ensure_meeting(db: Session, session: SessionItem) -> LiveMeeting:
    m = db.execute(select(LiveMeeting).filter_by(session_id=session.id)).scalar_one_or_none()
    if not m:
        adapter = get_live_adapter()
        m = LiveMeeting(id=f"lm_{session.id}"[:64], college_id=session.college_id, session_id=session.id,
                        provider=adapter.name, external_meeting_id=adapter.create_meeting(session), flow_steps=[],
                        unmatched_attendees=[])
        db.add(m)
        db.flush()
        if adapter.name == "teams":
            from services.teams import queue_create
            queue_create(db, session, m)       # Graph call happens in the outbox worker
    return m
