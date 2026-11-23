"""Live classes on Microsoft Teams (Master Plan: "Live classes, messaging and broadcast").

The portal owns schedule, attendance and the recordings list; Teams only
carries the meeting.

1. Scheduling (outbox ``teams.create_event``): a calendar event with a Teams
   meeting on the organizer's calendar via Graph app-only permissions. Use
   calendar events, not standalone online meetings, or attendance reports and
   recordings cannot be fetched. ``transactionId`` makes the create idempotent
   on Graph's side as well as ours.
2. Students press "Join in Teams" (screen 08/07): the stored joinUrl. A click
   is not attendance.
3. After the meeting (outbox ``teams.pull_attendance``): attendance reports
   -> join/leave intervals per person -> join_events(source="teams") -> the
   existing 75% rule in services/live_class.finalize_session. Licensed users
   match by email; anonymous ones by the display-name rule
   "IREP-<register no> Name"; anything else waits for the trainer.

Every Graph call runs in the outbox worker, never in a request.
Times: the portal stores naive local datetimes; Graph gets and returns UTC.
"""
import datetime
import re
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import JoinEvent, LiveMeeting, SessionItem, Student, Trainer, User, BatchTrainer
from services.outbox import emit, handler as outbox_handler

DISPLAY_NAME_RULE = re.compile(r"^\s*IREP-(?P<code>[A-Za-z0-9]+)\b", re.I)


class GraphError(RuntimeError):
    pass


def _upn(organizer: str) -> str:
    """Path segment for /users/{id|userPrincipalName}."""
    return quote(organizer, safe="@")


# ---------------------------------------------------------------------------
# Graph client (app-only). Tests pass an httpx.MockTransport.
# ---------------------------------------------------------------------------

class GraphClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, *,
                 base_url: str = "https://graph.microsoft.com/v1.0", login_url: str = "https://login.microsoftonline.com",
                 transport: Optional[httpx.BaseTransport] = None):
        if not (tenant_id and client_id and client_secret):
            raise GraphError("Graph credentials are not configured (GRAPH_TENANT_ID / GRAPH_CLIENT_ID / GRAPH_CLIENT_SECRET)")
        self.tenant_id, self.client_id, self.client_secret = tenant_id, client_id, client_secret
        self.base_url, self.login_url = base_url.rstrip("/"), login_url.rstrip("/")
        self.http = httpx.Client(transport=transport, timeout=20)
        self._token: Optional[str] = None
        self._token_exp = 0.0
        self._lock = threading.Lock()

    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._token_exp - 60:
                return self._token
            r = self.http.post(f"{self.login_url}/{self.tenant_id}/oauth2/v2.0/token", data={
                "grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default"})
            if r.status_code != 200:
                raise GraphError(f"token request failed: {r.status_code}")
            body = r.json()
            self._token, self._token_exp = body["access_token"], time.monotonic() + int(body.get("expires_in", 3600))
            return self._token

    def _call(self, method: str, path: str, **kw) -> dict:
        r = self.http.request(method, f"{self.base_url}{path}", headers={"Authorization": f"Bearer {self._access_token()}"}, **kw)
        if r.status_code >= 400:
            # raised -> the outbox retries with backoff; 403 usually means the
            # tenant admin has not granted permissions or the access policy
            raise GraphError(f"Graph {method} {path.split('?')[0]} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def create_event(self, organizer: str, *, subject: str, body_html: str, start_utc: datetime.datetime,
                     end_utc: datetime.datetime, transaction_id: str) -> dict:
        return self._call("POST", f"/users/{_upn(organizer)}/events", json={
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "start": {"dateTime": start_utc.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"},
            "end": {"dateTime": end_utc.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"},
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
            "allowNewTimeProposals": False,
            "transactionId": transaction_id,
        })

    def update_event_time(self, organizer: str, event_id: str, *, start_utc: datetime.datetime, end_utc: datetime.datetime,
                          subject: Optional[str] = None) -> dict:
        body = {"start": {"dateTime": start_utc.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"},
                "end": {"dateTime": end_utc.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"}}
        if subject:
            body["subject"] = subject
        return self._call("PATCH", f"/users/{_upn(organizer)}/events/{quote(event_id)}", json=body)

    def cancel_event(self, organizer: str, event_id: str, comment: str) -> None:
        self._call("POST", f"/users/{_upn(organizer)}/events/{quote(event_id)}/cancel", json={"comment": comment})

    def find_online_meeting_id(self, organizer: str, join_url: str) -> Optional[str]:
        flt = quote(f"JoinWebUrl eq '{join_url}'", safe="")
        rows = self._call("GET", f"/users/{_upn(organizer)}/onlineMeetings?$filter={flt}").get("value", [])
        return rows[0]["id"] if rows else None

    def attendance_records(self, organizer: str, meeting_id: str) -> List[dict]:
        base = f"/users/{_upn(organizer)}/onlineMeetings/{quote(meeting_id)}/attendanceReports"
        records: List[dict] = []
        for rep in self._call("GET", base).get("value", []):
            path = f"{base}/{quote(rep['id'])}/attendanceRecords"
            while path:
                page = self._call("GET", path)
                records.extend(page.get("value", []))
                nxt = page.get("@odata.nextLink")
                path = nxt[len(self.base_url):] if nxt else None
        return records


_client_factory: Optional[Callable[[], GraphClient]] = None


def get_graph() -> GraphClient:
    if _client_factory is not None:
        return _client_factory()
    return GraphClient(settings.GRAPH_TENANT_ID, settings.GRAPH_CLIENT_ID, settings.GRAPH_CLIENT_SECRET,
                       base_url=settings.GRAPH_BASE_URL, login_url=settings.GRAPH_LOGIN_URL)


def set_graph_factory(factory: Optional[Callable[[], GraphClient]]) -> None:
    """Tests (and a staging smoke test) swap in a client with a mock transport."""
    global _client_factory
    _client_factory = factory


# ---------------------------------------------------------------------------
# Time helpers: naive local (portal) <-> UTC (Graph)
# ---------------------------------------------------------------------------

def local_to_utc(naive_local: datetime.datetime) -> datetime.datetime:
    return naive_local.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def graph_time_to_local(value: str) -> datetime.datetime:
    v = value.rstrip("Z")
    if "." in v:
        head, frac = v.split(".", 1)
        v = f"{head}.{frac[:6]}"          # Graph sends 7 fractional digits
    aware = datetime.datetime.fromisoformat(v).replace(tzinfo=datetime.timezone.utc)
    return aware.astimezone().replace(tzinfo=None, microsecond=0)   # attendance needs seconds, not ticks


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

def organizer_for(db: Session, session: SessionItem) -> str:
    """The trainer's licensed Teams account, else the college default organizer."""
    trainer_ids = []
    if session.batch_id:
        trainer_ids = db.execute(select(BatchTrainer.trainer_id).where(BatchTrainer.batch_id == session.batch_id)).scalars().all()
    for tid in trainer_ids:
        t = db.get(Trainer, tid)
        if t and t.teams_upn:
            return t.teams_upn
    if settings.TEAMS_DEFAULT_ORGANIZER:
        return settings.TEAMS_DEFAULT_ORGANIZER
    raise GraphError(f"No Teams organizer for session {session.id}: set trainers.teams_upn or TEAMS_DEFAULT_ORGANIZER")


def _already_pending(db: Session, event_type: str, session_id: str) -> bool:
    from models.schema import OutboxEvent
    db.flush()                     # sessions run with autoflush off: see events queued in this transaction
    return db.execute(select(OutboxEvent.id).where(
        OutboxEvent.event_type == event_type, OutboxEvent.entity_id == session_id,
        OutboxEvent.status == "pending")).first() is not None


def queue_create(db: Session, session: SessionItem, meeting: LiveMeeting) -> None:
    if _already_pending(db, "teams.create_event", session.id):
        return
    emit(db, "teams.create_event", {"session_id": session.id}, college_id=session.college_id,
         entity_type="session", entity_id=session.id)


def queue_attendance_pull(db: Session, session: SessionItem, delay_seconds: Optional[int] = None) -> None:
    if _already_pending(db, "teams.pull_attendance", session.id):
        return                                   # a pull is already waiting or retrying
    emit(db, "teams.pull_attendance", {"session_id": session.id}, college_id=session.college_id,
         entity_type="session", entity_id=session.id,
         delay_seconds=settings.TEAMS_REPORT_DELAY_SECONDS if delay_seconds is None else delay_seconds)


@outbox_handler("teams.create_event")
def _create_event(db: Session, event) -> None:
    session = db.get(SessionItem, event.payload["session_id"])
    meeting = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == event.payload["session_id"])).scalar_one_or_none()
    if session is None or meeting is None or meeting.join_url:
        return                                     # gone, or already created: idempotent
    organizer = organizer_for(db, session)
    start = local_to_utc(session.scheduled_start)
    end = local_to_utc(session.scheduled_end or session.scheduled_start + datetime.timedelta(minutes=session.duration_min))
    created = get_graph().create_event(
        organizer, subject=f"IREP · {session.title}", start_utc=start, end_utc=end,
        body_html=f"<p>IREP live class: {session.title}</p><p>Join from the IREP portal or this invitation.</p>",
        transaction_id=f"irep-{session.id}")
    join_url = (created.get("onlineMeeting") or {}).get("joinUrl")
    if not join_url:
        raise GraphError("Graph created the event without a Teams join URL (is Teams enabled for the organizer?)")
    meeting.organizer_upn, meeting.graph_event_id, meeting.join_url = organizer, created.get("id"), join_url


@outbox_handler("teams.update_event")
def _update_event(db: Session, event) -> None:
    """Approved reschedule (screen 06): move the Teams calendar event. Idempotent (PATCH to the same time)."""
    session = db.get(SessionItem, event.payload["session_id"])
    meeting = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == event.payload["session_id"])).scalar_one_or_none()
    if session is None or meeting is None or not meeting.graph_event_id:
        return
    get_graph().update_event_time(meeting.organizer_upn, meeting.graph_event_id, start_utc=local_to_utc(session.scheduled_start),
                                  end_utc=local_to_utc(session.scheduled_end), subject=f"IREP · {session.title}")


@outbox_handler("teams.cancel_event")
def _cancel_event(db: Session, event) -> None:
    """Approved cancellation (screen 06): cancel the Teams meeting so invitees are told."""
    meeting = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == event.payload["session_id"])).scalar_one_or_none()
    if meeting is None or not meeting.graph_event_id or meeting.ended_at:
        return
    get_graph().cancel_event(meeting.organizer_upn, meeting.graph_event_id, event.payload.get("comment") or "Cancelled by the college")
    meeting.ended_at = datetime.datetime.now()                           # never pulled for attendance


@outbox_handler("teams.pull_attendance")
def _pull_attendance(db: Session, event) -> None:
    from services.audit import record_audit

    session = db.get(SessionItem, event.payload["session_id"])
    meeting = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == event.payload["session_id"])).scalar_one_or_none()
    if session is None or meeting is None or not meeting.join_url:
        return
    graph = get_graph()
    if not meeting.graph_online_meeting_id:
        meeting.graph_online_meeting_id = graph.find_online_meeting_id(meeting.organizer_upn, meeting.join_url)
        if not meeting.graph_online_meeting_id:
            raise GraphError("online meeting not found yet")          # retried with backoff
    records = graph.attendance_records(meeting.organizer_upn, meeting.graph_online_meeting_id)
    if not records:
        raise GraphError("attendance report not published yet")       # Teams publishes it after the meeting
    summary = import_attendance(db, session, meeting, records)
    record_audit(db, None, "attendance.teams_imported", "session", session.id, summary, college_id=session.college_id)


# ---------------------------------------------------------------------------
# Attendance import (pure DB logic; also used by the CSV fallback)
# ---------------------------------------------------------------------------

def _match_user(db: Session, college_id: str, record: dict) -> Optional[str]:
    identity = record.get("identity") or {}
    email = (record.get("emailAddress") or "").strip().lower()
    if email:
        uid = db.execute(select(User.id).where(User.college_id == college_id, User.email == email)).scalar_one_or_none()
        if uid:
            return uid
    m = DISPLAY_NAME_RULE.match(identity.get("displayName") or "")
    if m:
        return db.execute(select(Student.user_id).where(Student.college_id == college_id,
                                                        Student.register_no == m.group("code"))).scalar_one_or_none()
    return None


def import_attendance(db: Session, session: SessionItem, meeting: LiveMeeting, records: Iterable[dict],
                      now: Optional[datetime.datetime] = None) -> Dict[str, int]:
    """Replace this session's Teams presence with the report and re-run the 75% rule."""
    from services.live_class import finalize_session

    db.execute(delete(JoinEvent).where(JoinEvent.session_id == session.id, JoinEvent.source == "teams"))
    unmatched, matched = [], 0
    per_user: Dict[str, List[list]] = {}
    for rec in records:
        intervals = rec.get("attendanceIntervals") or []
        uid = _match_user(db, session.college_id, rec)
        if uid is None:
            unmatched.append({"name": (rec.get("identity") or {}).get("displayName") or "Unknown",
                              "email": rec.get("emailAddress"),
                              "minutes": round(sum(i.get("durationInSeconds") or 0 for i in intervals) / 60),
                              "intervals": [[i.get("joinDateTime"), i.get("leaveDateTime")] for i in intervals]})
            continue
        matched += 1
        per_user.setdefault(uid, []).extend([i.get("joinDateTime"), i.get("leaveDateTime")] for i in intervals)
    for uid, ivs in per_user.items():          # one person may appear in several records / devices
        _write_intervals(db, session, uid, ivs)
    meeting.unmatched_attendees = unmatched
    meeting.attendance_pulled_at = now or datetime.datetime.now()
    if not meeting.ended_at:
        meeting.ended_at = session.scheduled_end
    db.flush()
    summary = finalize_session(db, session, meeting, now or datetime.datetime.now())
    return {**summary, "matched": matched, "unmatched": len(unmatched)}


def merge_intervals(intervals: List[tuple]) -> List[tuple]:
    """Union of (start, end) intervals: two devices or rejoin overlaps count once."""
    merged: List[list] = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [tuple(x) for x in merged]


def _write_intervals(db: Session, session: SessionItem, user_id: str, graph_intervals: List[list]) -> None:
    """Replace the user's Teams presence with the union of their existing and new intervals."""
    from services.live_class import presence_intervals, record_join_event

    existing = db.execute(select(JoinEvent.event, JoinEvent.at).where(
        JoinEvent.session_id == session.id, JoinEvent.user_id == user_id, JoinEvent.source == "teams")).all()
    end_default = session.scheduled_end or session.scheduled_start + datetime.timedelta(minutes=session.duration_min)
    spans = list(presence_intervals(sorted(((e, a) for e, a in existing), key=lambda x: x[1]), end_default)) if existing else []
    for join_s, leave_s in graph_intervals:
        if join_s:
            start = graph_time_to_local(join_s)
            spans.append((start, graph_time_to_local(leave_s) if leave_s else end_default))
    db.execute(delete(JoinEvent).where(JoinEvent.session_id == session.id, JoinEvent.user_id == user_id,
                                       JoinEvent.source == "teams"))
    for a, b in merge_intervals(spans):
        record_join_event(db, session, user_id, "joined", a, source="teams")
        record_join_event(db, session, user_id, "left", b, source="teams")


def confirm_unmatched(db: Session, session: SessionItem, meeting: LiveMeeting, index: int, student: Student,
                      now: Optional[datetime.datetime] = None) -> Dict[str, int]:
    """Trainer links an unmatched Teams attendee to a student; presence is recomputed."""
    from services.live_class import finalize_session

    pending = list(meeting.unmatched_attendees or [])
    if not (0 <= index < len(pending)):
        raise IndexError(index)
    entry = pending.pop(index)
    _write_intervals(db, session, student.user_id, entry.get("intervals") or [])
    meeting.unmatched_attendees = pending
    db.flush()
    return finalize_session(db, session, meeting, now or datetime.datetime.now())


# ---------------------------------------------------------------------------
# Periodic job (Celery beat / staff endpoint): what needs Graph work now
# ---------------------------------------------------------------------------

def queue_due_work(db: Session, now: Optional[datetime.datetime] = None, horizon_days: int = 14,
                   college_id: Optional[str] = None) -> Dict[str, int]:
    from services.live_class import ensure_meeting

    now = now or datetime.datetime.now()
    created = pulled = 0
    upcoming = db.execute(select(SessionItem).where(
        SessionItem.scheduled_start >= now, SessionItem.scheduled_start <= now + datetime.timedelta(days=horizon_days),
        SessionItem.batch_id.isnot(None), SessionItem.status != "Cancelled",
        *([SessionItem.college_id == college_id] if college_id else []))).scalars().all()
    for s in upcoming:
        m = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == s.id)).scalar_one_or_none()
        if m is None:
            ensure_meeting(db, s)          # emits teams.create_event
            created += 1
    ended = db.execute(select(LiveMeeting, SessionItem).join(SessionItem, SessionItem.id == LiveMeeting.session_id).where(
        LiveMeeting.provider == "teams", LiveMeeting.join_url.isnot(None), LiveMeeting.attendance_pulled_at.is_(None),
        SessionItem.scheduled_end <= now - datetime.timedelta(seconds=settings.TEAMS_REPORT_DELAY_SECONDS),
        SessionItem.status != "Cancelled",
        *([SessionItem.college_id == college_id] if college_id else []))).all()
    for m, s in ended:
        queue_attendance_pull(db, s, delay_seconds=0)
        pulled += 1
    return {"create_queued": created, "pull_queued": pulled}
