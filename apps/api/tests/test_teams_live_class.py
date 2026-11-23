"""Live classes on Microsoft Teams (LIVE_CLASS_ADAPTER=teams), Graph mocked.

Covers the Master Plan flow: calendar event with a Teams meeting created by
the outbox (never in a request), "Join in Teams", attendance report ->
75% rule, display-name matching, trainer confirmation, retries.
"""
import datetime
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import (AuditLog, JoinEvent, LiveMeeting, OutboxEvent, SessionAttendance, SessionItem, Student,
                           Trainer)
from services import outbox, teams

client = TestClient(app)
SID = "sess_teams_it"
ORGANIZER = "arun.k@irep.example"
BATCH = "bat_aids_s5_aids"


def _h(sub, role, name="x"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": "col_demo_001", "name": name})}


PRIYA, ARUN = _h("usr_priya_01", "student", "Priya R"), _h("usr_arun_01", "trainer", "Arun Kumar")


class FakeGraph:
    """Just enough of login.microsoftonline.com and Graph v1.0."""

    def __init__(self):
        self.calls = []
        self.events = {}          # transactionId -> event
        self.records = []         # attendance records to serve
        self.publish_report = True

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = urlparse(str(request.url))
        self.calls.append((request.method, url.path))
        if url.netloc == "login.test":
            assert parse_qs(request.content.decode())["grant_type"] == ["client_credentials"]
            return httpx.Response(200, json={"access_token": "graph-token", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer graph-token"
        path = url.path.removeprefix("/v1.0")
        if request.method == "POST" and path == f"/users/{ORGANIZER}/events":
            body = json.loads(request.content)
            ev = self.events.setdefault(body["transactionId"], {
                "id": f"evt-{len(self.events) + 1}", "body_sent": body,
                "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/abc"}})
            return httpx.Response(201, json=ev)
        if path == f"/users/{ORGANIZER}/onlineMeetings":
            assert "JoinWebUrl eq 'https://teams.microsoft.com/l/meetup-join/abc'" in parse_qs(url.query)["$filter"][0]
            return httpx.Response(200, json={"value": [{"id": "om-1"}]})
        if path == f"/users/{ORGANIZER}/onlineMeetings/om-1/attendanceReports":
            return httpx.Response(200, json={"value": [{"id": "rep-1"}] if self.publish_report else []})
        if path == f"/users/{ORGANIZER}/onlineMeetings/om-1/attendanceReports/rep-1/attendanceRecords":
            page2 = "page=2" in url.query
            half = len(self.records) // 2
            rows = self.records[half:] if page2 else self.records[:half]
            body = {"value": rows}
            if not page2:
                body["@odata.nextLink"] = f"https://graph.test/v1.0{path}?page=2"
            return httpx.Response(200, json=body)
        return httpx.Response(404, json={"error": path})


@pytest.fixture
def graph(monkeypatch):
    fake = FakeGraph()
    monkeypatch.setattr(settings, "LIVE_CLASS_ADAPTER", "teams")
    teams.set_graph_factory(lambda: teams.GraphClient("tenant-1", "client-1", "secret-1", base_url="https://graph.test/v1.0",
                                                      login_url="https://login.test", transport=httpx.MockTransport(fake)))
    db = SessionLocal()
    try:
        _cleanup(db)
        start = datetime.datetime.now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=5)
        db.add(SessionItem(id=SID, college_id="col_demo_001", title="Teams IT: RAG review", track="AI & DS", trainer_name="Arun Kumar",
                           scheduled_start=start, scheduled_end=start + datetime.timedelta(minutes=60), duration_min=60,
                           status="Scheduled", batch_id=BATCH))
        db.get(Trainer, "trn_arun_01").teams_upn = ORGANIZER
        db.commit()
    finally:
        db.close()
    yield fake
    teams.set_graph_factory(None)
    db = SessionLocal()
    try:
        _cleanup(db)
        db.get(Trainer, "trn_arun_01").teams_upn = None
        db.commit()
    finally:
        db.close()


def _cleanup(db):
    # Teams is not used by the demo data, so every teams meeting/event is ours
    # (queue_due_work also creates meetings for the seeded upcoming sessions)
    db.execute(delete(OutboxEvent).where(OutboxEvent.event_type.like("teams.%")))
    db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id == SID))
    db.execute(delete(JoinEvent).where(JoinEvent.session_id == SID))
    db.execute(delete(SessionAttendance).where(SessionAttendance.session_id == SID))
    db.execute(delete(LiveMeeting).where(LiveMeeting.provider == "teams"))
    db.execute(delete(SessionItem).where(SessionItem.id == SID))
    db.commit()


def _drain():
    return outbox.dispatch_pending(SessionLocal, limit=100_000)


def _meeting():
    db = SessionLocal()
    try:
        return db.execute(select(LiveMeeting).where(LiveMeeting.session_id == SID)).scalar_one_or_none()
    finally:
        db.close()


def _make_due(event_type):
    db = SessionLocal()
    try:
        for ev in db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == SID, OutboxEvent.event_type == event_type)).scalars():
            ev.available_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        db.commit()
    finally:
        db.close()


def _iv(start, a, b):
    """Graph-style interval a..b minutes after the (local) session start, in UTC."""
    fmt = lambda d: teams.local_to_utc(d).strftime("%Y-%m-%dT%H:%M:%S.1234567Z")
    return {"joinDateTime": fmt(start + datetime.timedelta(minutes=a)), "leaveDateTime": fmt(start + datetime.timedelta(minutes=b)),
            "durationInSeconds": (b - a) * 60}


def _shift_to_past(minutes_ago=90):
    """The class has happened: move the session (already set up in Teams) into the past."""
    db = SessionLocal()
    try:
        s = db.get(SessionItem, SID)
        s.scheduled_start = datetime.datetime.now().replace(second=0, microsecond=0) - datetime.timedelta(minutes=minutes_ago)
        s.scheduled_end = s.scheduled_start + datetime.timedelta(minutes=60)
        db.commit()
    finally:
        db.close()


def _start():
    db = SessionLocal()
    try:
        return db.get(SessionItem, SID).scheduled_start
    finally:
        db.close()


def test_meeting_is_created_by_the_outbox_not_the_request(graph):
    r = client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA)
    assert r.status_code == 409 and "being set up" in r.json()["detail"]
    assert graph.calls == []                                   # no Graph call inside a request

    _drain()
    posts = [c for c in graph.calls if c[0] == "POST" and c[1].endswith("/events")]
    assert len(posts) == 1
    sent = next(iter(graph.events.values()))["body_sent"]
    assert sent["isOnlineMeeting"] is True and sent["onlineMeetingProvider"] == "teamsForBusiness"
    assert sent["transactionId"] == f"irep-{SID}" and sent["start"]["timeZone"] == "UTC"
    assert sent["start"]["dateTime"] == teams.local_to_utc(_start()).strftime("%Y-%m-%dT%H:%M:%S")

    m = _meeting()
    assert (m.provider, m.organizer_upn, m.graph_event_id) == ("teams", ORGANIZER, "evt-1")
    j = client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA).json()
    assert j["provider"] == "teams" and j["join_url"] == "https://teams.microsoft.com/l/meetup-join/abc"

    # idempotent: re-running the create does not create a second event
    db = SessionLocal()
    try:
        teams.queue_create(db, db.get(SessionItem, SID), db.get(LiveMeeting, m.id))
        db.commit()
    finally:
        db.close()
    _drain()
    assert len([c for c in graph.calls if c[0] == "POST" and c[1].endswith("/events")]) == 1


def test_attendance_comes_from_the_teams_report(graph):
    client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA)
    _drain()
    _shift_to_past()
    start = _start()
    db = SessionLocal()
    try:
        mates = db.execute(select(Student).where(Student.batch_id == BATCH, Student.id != "std_priya_01").order_by(Student.id)).scalars().all()
        sneha, vikram = mates[0], mates[1]
        # a manual override must survive the import
        db.add(SessionAttendance(id=f"att_{SID}_{vikram.id}"[:64], college_id="col_demo_001", session_id=SID, student_id=vikram.id,
                                 minutes_present=0, status="Present", source="manual", overridden_by="usr_arun_01"))
        db.commit()
        sneha_id, sneha_reg, vikram_id = sneha.id, sneha.register_no, vikram.id
    finally:
        db.close()

    graph.records = [
        # licensed user by email: 30 + 20 = 50 of 60 minutes -> Present (>= 45)
        {"emailAddress": "priya.r@demo.edu", "identity": {"displayName": "Priya R"},
         "attendanceIntervals": [_iv(start, 0, 30), _iv(start, 35, 55)]},
        # anonymous, display-name rule: 20 minutes -> Absent
        {"emailAddress": None, "identity": {"displayName": f"IREP-{sneha_reg} Sneha N"}, "attendanceIntervals": [_iv(start, 0, 20)]},
        # Vikram attended only 10 minutes but has a manual Present override
        {"emailAddress": "vikram.r@demo.edu", "identity": {"displayName": "Vikram R"}, "attendanceIntervals": [_iv(start, 0, 10)]},
        # cannot be matched -> waits for the trainer
        {"emailAddress": None, "identity": {"displayName": "Guest phone 98xx"}, "attendanceIntervals": [_iv(start, 0, 58)]},
    ]

    end = client.post(f"/api/v1/sessions/{SID}/end", headers=ARUN)
    # the trainer never "started" in the portal for a Teams class; end must still queue the pull
    assert end.status_code in (200, 409)
    if end.status_code == 409:
        client.post(f"/api/v1/sessions/{SID}/join", headers=ARUN)
        end = client.post(f"/api/v1/sessions/{SID}/end", headers=ARUN)
    assert end.json()["attendance"] == {"pending": True}

    _drain()                                               # pull is delayed: Teams publishes reports later
    assert not any(c[1].endswith("attendanceReports") for c in graph.calls)
    _make_due("teams.pull_attendance")
    _drain()

    db = SessionLocal()
    try:
        rows = {r.student_id: r for r in db.execute(select(SessionAttendance).where(SessionAttendance.session_id == SID)).scalars()}
        assert rows["std_priya_01"].status == "Present" and rows["std_priya_01"].minutes_present == 50
        assert rows[sneha_id].status == "Absent" and rows[sneha_id].minutes_present == 20
        assert rows[vikram_id].status == "Present" and rows[vikram_id].source == "manual"
        m = db.execute(select(LiveMeeting).where(LiveMeeting.session_id == SID)).scalar_one()
        assert m.graph_online_meeting_id == "om-1" and m.attendance_pulled_at is not None
        assert [u["name"] for u in m.unmatched_attendees] == ["Guest phone 98xx"]
        # the "Join in Teams" clicks are not attendance; only report intervals count
        sources = set(db.execute(select(JoinEvent.source).where(JoinEvent.session_id == SID)).scalars())
        assert sources == {"click", "teams"}
        # the audit log is append-only: earlier runs' rows stay, read the newest
        audit = db.execute(select(AuditLog).where(AuditLog.action == "attendance.teams_imported", AuditLog.entity_id == SID)
                           .order_by(AuditLog.created_at.desc())).scalars().first()
        assert audit.detail["matched"] == 3 and audit.detail["unmatched"] == 1
    finally:
        db.close()

    # trainer links the unmatched guest to Sneha -> her minutes now exceed 45
    un = client.get(f"/api/v1/trainer/sessions/{SID}/teams-unmatched", headers=ARUN).json()["unmatched"]
    assert un == [{"index": 0, "name": "Guest phone 98xx", "email": None, "minutes": 58}]
    assert client.get(f"/api/v1/trainer/sessions/{SID}/teams-unmatched", headers=PRIYA).status_code == 403
    bad = client.post(f"/api/v1/trainer/sessions/{SID}/teams-unmatched/confirm", json={"index": 0, "student_id": "std_cse_5_001_x"}, headers=ARUN)
    assert bad.status_code == 404
    ok = client.post(f"/api/v1/trainer/sessions/{SID}/teams-unmatched/confirm", json={"index": 0, "student_id": sneha_id}, headers=ARUN)
    assert ok.status_code == 200
    db = SessionLocal()
    try:
        assert db.execute(select(SessionAttendance.status).where(SessionAttendance.session_id == SID,
                                                                 SessionAttendance.student_id == sneha_id)).scalar_one() == "Present"
        assert db.execute(select(LiveMeeting).where(LiveMeeting.session_id == SID)).scalar_one().unmatched_attendees == []
    finally:
        db.close()


def test_unpublished_report_is_retried_not_lost(graph):
    client.post(f"/api/v1/sessions/{SID}/join", headers=PRIYA)
    _drain()
    graph.publish_report = False
    db = SessionLocal()
    try:
        teams.queue_attendance_pull(db, db.get(SessionItem, SID), delay_seconds=0)
        teams.queue_attendance_pull(db, db.get(SessionItem, SID), delay_seconds=0)   # deduplicated
        db.commit()
    finally:
        db.close()
    _drain()
    db = SessionLocal()
    try:
        pulls = db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == SID, OutboxEvent.event_type == "teams.pull_attendance")).scalars().all()
        assert len(pulls) == 1
        assert pulls[0].status == "pending" and pulls[0].attempts == 1 and "not published" in pulls[0].last_error
    finally:
        db.close()


def test_due_work_creates_upcoming_meetings_once(graph):
    db = SessionLocal()
    try:
        first = teams.queue_due_work(db, college_id="col_demo_001")
        db.commit()
        second = teams.queue_due_work(db, college_id="col_demo_001")
        db.commit()
        creates = db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == SID, OutboxEvent.event_type == "teams.create_event")).scalars().all()
    finally:
        db.close()
    assert first["create_queued"] >= 1 and second["create_queued"] == 0
    assert len(creates) == 1
    assert client.post("/api/v1/admin/jobs/teams", headers=_h("usr_kavitha_01", "college_admin")).json()["success"] is True
    assert client.post("/api/v1/admin/jobs/teams", headers=PRIYA).status_code == 403


def test_display_name_rule_and_utc_conversion():
    assert teams.DISPLAY_NAME_RULE.match("IREP-910022104042 Priya R").group("code") == "910022104042"
    assert teams.DISPLAY_NAME_RULE.match("irep-AB12 Someone").group("code") == "AB12"
    assert teams.DISPLAY_NAME_RULE.match("Priya R") is None
    local = datetime.datetime(2026, 11, 19, 11, 0)
    utc = teams.local_to_utc(local)
    assert teams.graph_time_to_local(utc.strftime("%Y-%m-%dT%H:%M:%S.1234567Z")) == local


def test_overlapping_intervals_from_two_devices_count_once():
    t = lambda m: datetime.datetime(2026, 11, 19, 11, 0) + datetime.timedelta(minutes=m)
    assert teams.merge_intervals([(t(0), t(20)), (t(0), t(58)), (t(55), t(60)), (t(70), t(75))]) == [(t(0), t(60)), (t(70), t(75))]
