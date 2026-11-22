"""Screen 08 Live Sessions & Recordings: join window, derived statuses, reminders, signed recording URLs."""
import datetime
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

from fastapi.testclient import TestClient
from sqlalchemy import select, func, delete

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import Student, SessionItem, SessionReminder, Notification, User
from services.live_sessions import build_student_live, join_enabled, session_status, sign_url, verify_signed

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Priya R"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


PRIYA = _token("usr_priya_01", "student")


def _session(db, sid):
    return db.execute(select(SessionItem).filter_by(id=sid)).scalar_one()


def test_join_window_is_ten_minutes():
    db = SessionLocal()
    try:
        s = _session(db, "sess_thu_rag")
        assert join_enabled(s, s.scheduled_start - datetime.timedelta(minutes=11)) is False
        assert join_enabled(s, s.scheduled_start - datetime.timedelta(minutes=10)) is True
        assert join_enabled(s, s.scheduled_start + datetime.timedelta(minutes=30)) is True
        assert join_enabled(s, s.scheduled_end) is False
    finally:
        db.close()


def test_hero_and_week_states_at_a_fixed_clock():
    """Freeze the clock 4 minutes before Thursday's session (the PDF 14 moment)."""
    db = SessionLocal()
    try:
        priya = db.execute(select(Student).filter_by(id="std_priya_01")).scalar_one()
        thu = _session(db, "sess_thu_rag")
        now = thu.scheduled_start - datetime.timedelta(minutes=4)
        d = build_student_live(db, priya, "en", now=now)
        hero = d["hero_session"]
        assert hero["id"] == "sess_thu_rag" and hero["starts_in_min"] == 4 and hero["join_enabled"] is True
        assert hero["lab"] == "AI Notebook pre-loaded"
        rows = {r["id"]: r for r in d["week_sessions"]}
        assert rows["sess_thu_rag"]["action"] == "join"
        assert rows["sess_sat_track_project"]["type"] == "In-lab / Hybrid"
        assert rows["sess_fri_quiz"]["action"] == "remind_me"
        # past sessions only become Attended/Missed once they have ended
        for sid in ("sess_mon_unionfind", "sess_tue_model_eval", "sess_wed_aptitude"):
            s = _session(db, sid)
            assert rows[sid]["status"] in (("Attended", "Missed", "Completed") if s.scheduled_end <= now else ("Upcoming", "Scheduled", "Live"))
    finally:
        db.close()


def test_status_derivation():
    class A:  # minimal attendance stub
        def __init__(self, status): self.status = status
    db = SessionLocal()
    try:
        s = _session(db, "sess_fri_quiz")
        after = s.scheduled_end + datetime.timedelta(minutes=1)
        assert session_status(s, A("Present"), after) == "Attended"
        assert session_status(s, A("Absent"), after) == "Missed"
        assert session_status(s, None, s.scheduled_start + datetime.timedelta(minutes=5)) == "Live"
        assert session_status(s, None, s.scheduled_start - datetime.timedelta(hours=2)) == "Upcoming"
        assert session_status(s, None, s.scheduled_start - datetime.timedelta(days=3)) == "Scheduled"
    finally:
        db.close()


def test_endpoint_payload_and_attendance_summary():
    res = client.get("/api/v1/student/live", headers=PRIYA)
    assert res.status_code == 200
    d = res.json()
    assert len(d["week_sessions"]) == 6
    summ = d["attendance_summary"]
    assert summ["sessions_total"] >= 54 and 88 <= summ["overall_pct"] <= 96
    assert summ["saturday_pct"] is not None and summ["weekday_pct"] is not None
    assert summ["recordings_watched_for_missed"] <= summ["missed_with_recording"]
    titles = [r["title"] for r in d["recording_library"]]
    assert "Cloud deploy walkthrough" in titles and "Docker Compose lab" in titles


def test_reminder_is_idempotent_and_notifies():
    db = SessionLocal()
    try:
        db.execute(delete(SessionReminder).where(SessionReminder.user_id == "usr_priya_01", SessionReminder.session_id == "sess_sat_track_project"))
        db.commit()
        before = db.execute(select(func.count(Notification.id)).filter_by(user_id="usr_priya_01", kind="reminder")).scalar_one()
    finally:
        db.close()
    r1 = client.post("/api/v1/student/sessions/sess_sat_track_project/remind", headers=PRIYA)
    assert r1.status_code == 200 and r1.json()["reminder_set"] is True
    r2 = client.post("/api/v1/student/sessions/sess_sat_track_project/remind", headers=PRIYA)
    assert r2.json().get("already") is True
    db = SessionLocal()
    try:
        after = db.execute(select(func.count(Notification.id)).filter_by(user_id="usr_priya_01", kind="reminder")).scalar_one()
        assert after == before + 1
    finally:
        db.close()
    d = client.get("/api/v1/student/live", headers=PRIYA).json()
    assert next(r for r in d["week_sessions"] if r["id"] == "sess_sat_track_project")["reminder_set"] is True


def test_signed_recording_url():
    res = client.get("/api/v1/student/recordings/rec_cloud_deploy/url", headers=PRIYA)
    assert res.status_code == 200
    url = res.json()["url"]
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    key = parsed.path[len("/media/"):]
    assert verify_signed(key, int(q["exp"][0]), q["sig"][0])
    assert not verify_signed(key, int(q["exp"][0]), "0" * 32)
    assert client.get(url).status_code == 200
    assert client.get(url.replace(q["sig"][0], "f" * 32)).status_code == 403
    expired = sign_url(key, datetime.datetime.now() - datetime.timedelta(minutes=1))
    assert client.get(expired).status_code == 403


def test_other_batch_and_tenant_cannot_access():
    db = SessionLocal()
    try:
        karthik = db.execute(select(User).filter_by(name="Karthik S")).scalars().first()
    finally:
        db.close()
    other = _token(karthik.id, "student", name="Karthik S")
    assert client.get("/api/v1/student/recordings/rec_mon_unionfind/url", headers=other).status_code == 404
    assert client.post("/api/v1/student/sessions/sess_thu_rag/remind", headers=other).status_code == 404
    assert client.get("/api/v1/student/live", headers=_token("usr_priya_01", "student", college_id="col_other_999")).status_code == 404
    assert client.get("/api/v1/student/live", headers=_token("usr_ramesh_01", "parent")).status_code == 403
