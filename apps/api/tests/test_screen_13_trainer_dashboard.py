"""Screen 13 Trainer Dashboard: numbers equal source-table queries, flag actions, guards."""
import datetime
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import Batch, BatchTrainer, Student, PullRequest, AtRiskFlag, FlagAction, Notification, RulesConfig
from services.at_risk import run_rules, in_quiet_hours

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Arun Kumar"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name, 'avatar': 'AK'})}"}


ARUN = _token("usr_arun_01", "trainer")


def test_dashboard_numbers_match_source_tables():
    res = client.get("/api/v1/trainer/dashboard", headers=ARUN)
    assert res.status_code == 200
    d = res.json()
    db = SessionLocal()
    try:
        batch_ids = db.execute(select(BatchTrainer.batch_id).filter_by(trainer_id="trn_arun_01")).scalars().all()
        assert d["kpis"]["active_batches"]["value"] == len(batch_ids) == 5
        students = db.execute(select(func.count(Student.id)).where(Student.batch_id.in_(batch_ids))).scalar_one()
        assert d["kpis"]["active_batches"]["students"] == students == 248
        pending = db.execute(select(func.count(PullRequest.id)).filter_by(college_id="col_demo_001", status="pending")).scalar_one()
        assert d["kpis"]["pending_code_reviews"]["value"] == pending
        flagged = db.execute(
            select(func.count(func.distinct(AtRiskFlag.student_id))).where(AtRiskFlag.batch_id.in_(batch_ids), AtRiskFlag.status != "resolved")
        ).scalar_one()
        assert d["kpis"]["at_risk_students"]["value"] == flagged
        averages = dict(db.execute(
            select(Batch.short_name, func.avg(Student.readiness_score)).join(Student, Student.batch_id == Batch.id)
            .where(Batch.id.in_(batch_ids)).group_by(Batch.short_name)
        ).all())
        for row in d["batch_readiness"]:
            assert row["score"] == round(averages[row["batch"]])
        assert {r["batch"] for r in d["batch_readiness"]} == {"CSE-A", "CSE-B", "IT-A", "AI&DS", "Cyber"}
    finally:
        db.close()


def test_dashboard_schedule_and_support_table():
    d = client.get("/api/v1/trainer/dashboard", headers=ARUN).json()
    items = d["today_schedule"]["items"]
    assert len(items) >= 3
    topics = [i["topic"] for i in items]
    assert "System design basics" in topics and "OWASP lab: XSS" in topics
    assert all(i["status"] in ("Done", "Next", "Later", "Live") for i in items)
    assert sum(1 for i in items if i["status"] == "Next") <= 1
    support = d["students_needing_support"]
    assert support and all(r["score"] < d["thresholds"]["score_below"] for r in support)
    assert support == sorted(support, key=lambda r: (r["score"], r["name"]))
    assert all(r["action"] in ("parent_call", "extra_saturday", "mentor") for r in support)


def test_dashboard_tamil_labels():
    d = client.get("/api/v1/trainer/dashboard?lang=ta", headers=ARUN).json()
    assert any(r["action_label"] in ("பெற்றோர் அழைப்பு", "கூடுதல் சனி", "வழிகாட்டி") for r in d["students_needing_support"])


def test_role_guard_and_tenant():
    assert client.get("/api/v1/trainer/dashboard", headers=_token("usr_priya_01", "student")).status_code == 403
    assert client.get("/api/v1/trainer/dashboard", headers=_token("usr_arun_01", "trainer", college_id="col_other_999")).status_code == 404


def test_rule_engine_flags_karthik_for_attendance_and_score():
    db = SessionLocal()
    try:
        flags = db.execute(
            select(AtRiskFlag).join(Student, Student.id == AtRiskFlag.student_id).where(Student.readiness_score == 52, Student.attendance_pct == 71)
        ).scalars().all()
        reasons = {f.reason_key for f in flags}
        assert {"low_score", "low_attendance"} <= reasons
        # idempotent: running the rules again opens nothing new
        assert run_rules(db, "col_demo_001") == 0
        db.rollback()
    finally:
        db.close()


def test_parent_call_action_notifies_parent_once():
    db = SessionLocal()
    try:
        flag = db.execute(
            select(AtRiskFlag).join(Student, Student.id == AtRiskFlag.student_id)
            .where(Student.readiness_score == 52, AtRiskFlag.reason_key == "low_attendance")
        ).scalars().first()
        flag_id = flag.id
        flag.parent_notified = False
        flag.parent_notified_at = None
        db.commit()
        before = db.execute(select(func.count(Notification.id)).filter_by(user_id="usr_lakshmi_01", kind="alert", channel="in_app")).scalar_one()
        cfg = db.execute(select(RulesConfig).filter_by(college_id="col_demo_001")).scalar_one()
        quiet = in_quiet_hours(cfg)
    finally:
        db.close()

    r1 = client.post(f"/api/v1/trainer/flags/{flag_id}/actions", json={"action_type": "parent_call", "note": "Called mother"}, headers=ARUN)
    assert r1.status_code == 200 and r1.json()["status"] == "in_progress"
    r2 = client.post(f"/api/v1/trainer/flags/{flag_id}/actions", json={"action_type": "parent_call"}, headers=ARUN)
    assert r2.json()["notified_now"] is False
    db = SessionLocal()
    try:
        after = db.execute(select(func.count(Notification.id)).filter_by(user_id="usr_lakshmi_01", kind="alert", channel="in_app")).scalar_one()
        if quiet:
            assert after == before
        else:
            assert after == before + 1   # in-app row; SMS row is a separate channel
            assert r1.json()["notified_now"] is True
        actions = db.execute(select(func.count(FlagAction.id)).filter_by(flag_id=flag_id)).scalar_one()
        assert actions >= 2
    finally:
        db.close()


def test_resolve_requires_note_and_removes_from_open_count():
    db = SessionLocal()
    try:
        flag = db.execute(select(AtRiskFlag).where(AtRiskFlag.status != "resolved", AtRiskFlag.batch_id == "bat_cyb_s5_cyber")).scalars().first()
        flag_id = flag.id
    finally:
        db.close()
    assert client.post(f"/api/v1/trainer/flags/{flag_id}/resolve", json={"note": "  "}, headers=ARUN).status_code == 422
    before = client.get("/api/v1/trainer/dashboard", headers=ARUN).json()["kpis"]["at_risk_students"]["open_flags"]
    res = client.post(f"/api/v1/trainer/flags/{flag_id}/resolve", json={"note": "Mentor assigned, attendance back to 80%"}, headers=ARUN)
    assert res.status_code == 200 and res.json()["status"] == "resolved"
    after = client.get("/api/v1/trainer/dashboard", headers=ARUN).json()["kpis"]["at_risk_students"]["open_flags"]
    assert after == before - 1
    # a trainer without that batch cannot touch the flag
    assert client.post(f"/api/v1/trainer/flags/{flag_id}/resolve", json={"note": "x"}, headers=_token("usr_meena_01", "trainer", name="Meena S")).status_code == 404


def test_at_risk_list_endpoint():
    res = client.get("/api/v1/trainer/at-risk", headers=ARUN)
    assert res.status_code == 200
    assert res.json()["total"] >= 1
    assert all(f["status"] != "resolved" for f in res.json()["flags"])
