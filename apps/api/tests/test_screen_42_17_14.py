"""Screens 42 and 17 (events), 14 (at-risk) and readiness v1: links L05, L29, L31, L34.
Spec: docs/screens/42-17-14-events-and-at-risk.md"""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import (AtRiskFlag, DirectMessage, Event, FlagAction, GroupMessage, Notification, OutboxEvent, ReadinessSnapshot,
                           Rsvp, RulesConfig, SessionAttendance, Student, TrainerDirectThread)

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


KAVITHA, RAMESH, LAKSHMI = _h("usr_kavitha_01", "college_admin"), _h("usr_ramesh_01", "parent"), _h("usr_lakshmi_01", "parent")
PRIYA, ARUN, MEENA = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer")
OTHER_COLLEGE = _h("usr_kavitha_01", "college_admin", "col_other_test")


def _at(hours):
    return (datetime.datetime.now() + datetime.timedelta(hours=hours)).replace(microsecond=0).isoformat()


@pytest.fixture
def events():
    made = []
    started = datetime.datetime.utcnow() - datetime.timedelta(seconds=2)
    yield made
    db = SessionLocal()
    try:
        db.execute(delete(Rsvp).where(Rsvp.event_id.in_(made or ["_"])))
        db.execute(delete(Event).where(Event.id.in_(made or ["_"])))
        db.execute(delete(GroupMessage).where(GroupMessage.id.like("gm_evt_%"), GroupMessage.created_at >= started))
        db.execute(delete(Notification).where(Notification.kind == "event", Notification.created_at >= started))
        db.commit()
    finally:
        db.close()


def _create(made, **kw):
    body = {"title_en": "Parents' open day", "kind": "event", "starts_at": _at(24 * 5), "audience": "parents", "rsvp_enabled": True, **kw}
    r = client.post("/api/v1/college/events", json=body, headers=KAVITHA)
    assert r.status_code == 201, r.text
    made.append(r.json()["id"])
    return r.json()["id"]


@pytest.mark.link("L05")
def test_invitations_go_down_and_rsvp_counts_come_up(events):
    eid = _create(events)
    assert client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "yes"}, headers=RAMESH).status_code == 404   # draft
    assert all(e["id"] != eid for e in client.get("/api/v1/parent/events", headers=RAMESH).json()["upcoming"])
    r = client.post(f"/api/v1/college/events/{eid}/publish", headers=KAVITHA)
    assert r.status_code == 422 and "Tamil" in r.json()["detail"]
    upd = {"title_en": "Parents' open day", "title_ta": "பெற்றோர் திறந்த நாள்", "kind": "event", "starts_at": _at(24 * 5),
           "audience": "parents", "rsvp_enabled": True, "location": "Seminar hall"}
    assert client.put(f"/api/v1/college/events/{eid}", json=upd, headers=KAVITHA).status_code == 200
    pub = client.post(f"/api/v1/college/events/{eid}/publish", headers=KAVITHA).json()
    assert pub["status"] == "published" and pub["notified"]["parents"] >= 2 and pub["notified"]["students"] == 0
    assert client.put(f"/api/v1/college/events/{eid}", json=upd, headers=KAVITHA).status_code == 409             # no edits once out

    mine = client.get("/api/v1/parent/events?lang=ta", headers=RAMESH).json()
    row = next(e for e in mine["upcoming"] if e["id"] == eid)
    assert row["title"] == "பெற்றோர் திறந்த நாள்" and row["can_rsvp"] and row["rsvp_status"] is None
    assert client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "yes", "guests": 2}, headers=RAMESH).status_code == 200
    assert client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "maybe", "guests": 1}, headers=LAKSHMI).status_code == 200
    counts = client.get(f"/api/v1/college/events/{eid}", headers=KAVITHA).json()["rsvp"]
    assert counts == {"yes": 1, "maybe": 1, "no": 0, "guests": 2}
    listed = next(e for e in client.get("/api/v1/college/events", headers=KAVITHA).json()["events"] if e["id"] == eid)
    assert listed["rsvp"]["yes"] == 1 and "parent" not in str(listed["rsvp"])                                 # counts only, no names

    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_ramesh_01", Notification.link == "/parent/events",
                                                     Notification.title_en == "Invitation: Parents' open day")).first()
    finally:
        db.close()
    out = client.post(f"/api/v1/college/events/{eid}/cancel", headers=KAVITHA).json()
    assert out["status"] == "cancelled" and out["parents_told"] == 2
    assert client.post(f"/api/v1/parent/events/{eid}/rsvp", json={"status": "no"}, headers=RAMESH).status_code == 404
    assert all(e["id"] != eid for e in client.get("/api/v1/parent/events", headers=RAMESH).json()["upcoming"])


def test_event_validation_and_guards(events):
    assert client.post("/api/v1/college/events", json={"title_en": "Bad", "starts_at": _at(5), "kind": "party"}, headers=KAVITHA).status_code == 422
    assert client.post("/api/v1/college/events", json={"title_en": "Bad end", "starts_at": _at(5), "ends_at": _at(4)}, headers=KAVITHA).status_code == 422
    past = _create(events, title_ta="கடந்தது", starts_at=_at(-3))
    assert client.post(f"/api/v1/college/events/{past}/publish", headers=KAVITHA).status_code == 422
    for h in (PRIYA, ARUN, RAMESH):
        assert client.get("/api/v1/college/events", headers=h).status_code == 403
    assert client.get("/api/v1/parent/events", headers=KAVITHA).status_code == 403
    assert client.get(f"/api/v1/college/events/{past}", headers=OTHER_COLLEGE).status_code == 404            # another college
    assert client.post("/api/v1/parent/events/evt_demo_day/rsvp", json={"status": "sure"}, headers=RAMESH).status_code == 422


@pytest.mark.link("L29")
def test_a_published_drive_reaches_the_dashboard_and_the_placement_group(events):
    eid = _create(events, title_en="Mock drive: Zoho round 1", title_ta="மாதிரி முகாம்: Zoho சுற்று 1", kind="drive",
                  audience="students", starts_at=_at(2), rsvp_enabled=False)
    out = client.post(f"/api/v1/college/events/{eid}/publish", headers=KAVITHA).json()
    assert out["placement_posts"] >= 1 and out["notified"]["students"] > 0
    upcoming = client.get("/api/v1/student/dashboard?lang=ta", headers=PRIYA).json()["upcoming_events"]
    assert any(e["id"] == eid and e["title"].startswith("மாதிரி முகாம்") for e in upcoming)
    db = SessionLocal()
    try:
        post = db.execute(select(GroupMessage).where(GroupMessage.group_id == "grp_placement",
                                                     GroupMessage.message_text.contains("Mock drive: Zoho round 1"))).scalars().first()
        assert post is not None and post.sender_role == "Placement cell"
    finally:
        db.close()


# ----------------------------------------------------------------- Screen 14 / L31

@pytest.fixture
def priya_flag():
    db = SessionLocal()
    try:
        cfg = db.execute(select(RulesConfig).where(RulesConfig.college_id == "col_demo_001")).scalar_one()
        saved = (cfg.quiet_hours_start, cfg.quiet_hours_end)
        cfg.quiet_hours_start = cfg.quiet_hours_end = 0          # never quiet for the API path
        db.add(AtRiskFlag(id="flag_test_l31", college_id="col_demo_001", student_id="std_priya_01", batch_id="bat_aids_s5_aids",
                          reason_key="low_attendance", reason_text="Attendance 68%", severity="medium",
                          suggested_action="parent_call", status="open"))
        db.commit()
        started = datetime.datetime.utcnow() - datetime.timedelta(seconds=2)
    finally:
        db.close()
    yield "flag_test_l31"
    db = SessionLocal()
    try:
        db.execute(delete(FlagAction).where(FlagAction.flag_id == "flag_test_l31"))
        db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id == "flag_test_l31", OutboxEvent.event_type == "at_risk.parent_call"))
        db.execute(delete(AtRiskFlag).where(AtRiskFlag.id == "flag_test_l31"))
        db.execute(delete(DirectMessage).where(DirectMessage.sender_user_id == "usr_arun_01", DirectMessage.created_at >= started,
                                               DirectMessage.text_en.contains("short call about")))
        db.execute(delete(Notification).where(Notification.title_en == "Support plan for Priya R", Notification.created_at >= started))
        cfg = db.execute(select(RulesConfig).where(RulesConfig.college_id == "col_demo_001")).scalar_one()
        cfg.quiet_hours_start, cfg.quiet_hours_end = saved
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L31")
def test_parent_call_reaches_messages_and_overview_once(priya_flag):
    listed = client.get("/api/v1/trainer/at-risk?lang=ta", headers=ARUN).json()
    row = next(f for f in listed["flags"] if f["id"] == priya_flag)
    assert row["issue"] == "வருகை 68%" and row["band"] and row["attendance_pct"] is not None and listed["summary"]["open"] >= 1
    r = client.post(f"/api/v1/trainer/flags/{priya_flag}/actions", json={"action_type": "parent_call", "note": "Call tonight"}, headers=ARUN)
    assert r.status_code == 200 and r.json()["parent_call"] == "sent" and r.json()["notified_now"] is True
    again = client.post(f"/api/v1/trainer/flags/{priya_flag}/actions", json={"action_type": "parent_call"}, headers=ARUN).json()
    assert again["parent_call"] == "already"

    db = SessionLocal()
    try:
        assert db.execute(select(func.count(Notification.id)).where(
            Notification.user_id == "usr_ramesh_01", Notification.title_en == "Support plan for Priya R",
            Notification.channel == "in_app")).scalar_one() == 1
        thread = db.execute(select(TrainerDirectThread).where(TrainerDirectThread.trainer_user_id == "usr_arun_01",
                                                              TrainerDirectThread.contact_user_id == "usr_ramesh_01")).scalars().first()
        thread_id = thread.id
    finally:
        db.close()
    msgs = client.get(f"/api/v1/threads/{thread_id}/messages?lang=ta", headers=RAMESH).json()
    assert "short call about Priya R" in str(msgs) or "சிறிய அழைப்பு" in str(msgs)                          # 18 Message trainer
    alerts = client.get("/api/v1/parent/overview?lang=ta", headers=RAMESH).json()["support_alerts"]
    assert any(a["id"] == priya_flag and a["issue"] == "வருகை 68%" for a in alerts)                         # 15 overview
    hist = client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=ARUN).json()
    assert [a["type"] for a in hist["actions"]] == ["parent_call", "parent_call"]


def test_parent_call_in_quiet_hours_is_held_then_delivered_once(priya_flag):
    from services.at_risk import _held_parent_call, request_parent_call
    db = SessionLocal()
    try:
        cfg = db.execute(select(RulesConfig).where(RulesConfig.college_id == "col_demo_001")).scalar_one()
        cfg.quiet_hours_start, cfg.quiet_hours_end = 21, 8
        flag = db.get(AtRiskFlag, priya_flag)
        night = datetime.datetime.now().replace(hour=22, minute=30, second=0, microsecond=0)
        assert request_parent_call(db, flag, "usr_arun_01", now=night) == "held"
        assert request_parent_call(db, flag, "usr_arun_01", now=night) == "held"
        db.flush()
        evs = db.execute(select(OutboxEvent).where(OutboxEvent.entity_id == priya_flag, OutboxEvent.event_type == "at_risk.parent_call")).scalars().all()
        assert len(evs) == 1 and flag.parent_notified is False
        wait = (evs[0].available_at - evs[0].created_at).total_seconds() if evs[0].created_at else None
        assert evs[0].payload["trainer_user_id"] == "usr_arun_01" and (wait is None or wait > 3600)
        _held_parent_call(db, evs[0])
        _held_parent_call(db, evs[0])                                                         # idempotent re-run
        db.flush()
        assert flag.parent_notified is True
        assert db.execute(select(func.count(Notification.id)).where(Notification.user_id == "usr_ramesh_01",
                                                                    Notification.title_en == "Support plan for Priya R",
                                                                    Notification.channel == "in_app")).scalar_one() == 1
    finally:
        db.rollback()
        db.close()


def test_at_risk_guards(priya_flag):
    assert client.get("/api/v1/trainer/at-risk", headers=PRIYA).status_code == 403
    assert client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=MEENA).status_code == 404               # not her batch
    assert client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=_h("usr_arun_01", "trainer", "col_other_test")).status_code in (403, 404)


# ----------------------------------------------------------------- readiness v1 / L34

@pytest.mark.link("L34")
def test_nightly_recomputes_attendance_scores_and_flags():
    from services.readiness import recompute_attendance, run_nightly
    db = SessionLocal()
    try:
        priya = db.get(Student, "std_priya_01")
        rows = dict(db.execute(select(SessionAttendance.status, func.count(SessionAttendance.id))
                               .where(SessionAttendance.student_id == priya.id).group_by(SessionAttendance.status)).all())
        marked = rows.get("Present", 0) + rows.get("Absent", 0) + rows.get("Partial", 0)
        expected = round(100 * rows.get("Present", 0) / marked) if marked else priya.attendance_pct
        assert recompute_attendance(db, priya) in (expected, None)
        assert priya.attendance_pct == expected                                 # Excused (approved leave) is left out

        today = datetime.date.today()
        before = db.execute(select(func.count(ReadinessSnapshot.id)).where(ReadinessSnapshot.student_id == priya.id,
                                                                           ReadinessSnapshot.snapshot_date == today)).scalar_one()
        out = run_nightly(db, "col_demo_001")
        out2 = run_nightly(db, "col_demo_001")
        db.flush()
        assert out["students"] > 50 and out["attendance_recomputed"] >= 1 and out2["flags_created"] == 0      # no duplicate flags
        assert db.execute(select(func.count(ReadinessSnapshot.id)).where(ReadinessSnapshot.student_id == priya.id,
                                                                         ReadinessSnapshot.snapshot_date == today)).scalar_one() == 1
        month_ago = db.execute(select(ReadinessSnapshot.score).where(
            ReadinessSnapshot.student_id == priya.id, ReadinessSnapshot.snapshot_date <= today - datetime.timedelta(days=30))
            .order_by(ReadinessSnapshot.snapshot_date.desc())).scalars().first()
        if month_ago is not None:
            assert priya.readiness_delta == priya.readiness_score - month_ago                          # "this month"
        assert before in (0, 1)
    finally:
        db.rollback()
        db.close()


def test_nightly_flags_notify_the_batch_trainer():
    from services.readiness import run_nightly
    db = SessionLocal()
    try:
        st = db.execute(select(Student).where(Student.college_id == "col_demo_001", Student.batch_id == "bat_cse_s5_cseb")).scalars().first()
        db.execute(delete(FlagAction).where(FlagAction.flag_id.in_(select(AtRiskFlag.id).where(AtRiskFlag.student_id == st.id))))
        db.execute(delete(AtRiskFlag).where(AtRiskFlag.student_id == st.id))
        db.execute(delete(SessionAttendance).where(SessionAttendance.student_id == st.id))
        st.attendance_pct = 40                                                   # no register rows: the stored value stays
        out = run_nightly(db, "col_demo_001")
        db.flush()
        flag = db.execute(select(AtRiskFlag).where(AtRiskFlag.student_id == st.id, AtRiskFlag.reason_key == "low_attendance")).scalar_one()
        assert out["flags_created"] >= 1 and out["trainer_alerts"] >= 1 and flag.severity == "high"
        assert db.execute(select(Notification).where(Notification.user_id == "usr_arun_01", Notification.link == "/trainer/at-risk",
                                                     Notification.body_en == "Attendance 40%")).first()
        assert db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "audit.at_risk.flagged", OutboxEvent.entity_id == flag.id)).first()
    finally:
        db.rollback()
        db.close()
