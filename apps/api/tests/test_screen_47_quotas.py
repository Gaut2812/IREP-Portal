"""Screen 47 quotas (S12): MoU quotas reach 29, 25 and 08 (L36); usage figures reach 20 (L23);
Cyber Range access expires. Spec: docs/screens/47-usage-quotas.md"""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import LabApproval, LabSession, MouTerm, Recording, ReportRun
from services.quotas import can_store_recording

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
SUPER = _h("usr_irep_super_01", "super_admin", PLATFORM_TENANT)          # MoU terms and feature switches
PRIYA, KAVITHA, ARUN = _h("usr_priya_01", "student"), _h("usr_kavitha_01", "college_admin"), _h("usr_arun_01", "trainer")


@pytest.fixture
def tight_mou():
    """A new MoU with tiny quotas, activated through 45; the demo MoU is re-activated afterwards."""
    r = client.post("/api/v1/admin/colleges/col_demo_001/mou", json={
        "starts_on": "2026-06-01", "ends_on": "2027-05-31", "students_cap": 650, "lab_hours_per_student": 1,
        "ai_calls_per_day": 1, "storage_gb": 0, "activate": True}, headers=SUPER)
    assert r.status_code == 201, r.text
    yield r.json()["id"]
    client.post("/api/v1/admin/colleges/col_demo_001/mou/mou_demo_2026/activate", headers=SUPER)
    db = SessionLocal()
    try:
        db.execute(delete(MouTerm).where(MouTerm.id == r.json()["id"]))
        db.execute(delete(Recording).where(Recording.id == "rec_test_quota"))
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L36")
def test_mou_quotas_reach_labs_study_buddy_and_recordings(tight_mou):
    labs = client.get("/api/v1/student/labs", headers=PRIYA).json()
    assert labs["usage"]["lab_minutes_quota"] == 60                                     # 1 hour, from the MoU
    linux = next(l for l in labs["labs"] if l["id"] == "lab_linux")
    assert linux["locked"]["reason"] == "quota" and "60 lab minutes" in linux["locked"]["message"]
    assert client.get("/api/v1/student/buddy", headers=PRIYA).json()["usage"]["daily_cap"] == 1
    db = SessionLocal()
    try:
        assert can_store_recording(db, "col_demo_001", 1) is False                       # storage_gb 0
    finally:
        db.close()
    usage = client.get("/api/v1/admin/usage/col_demo_001", headers=STAFF).json()
    assert usage["mou"]["lab_hours_per_student"] == 1 and usage["usage"]["lab_minutes"]["quota"] == usage["students"] * 60
    assert usage["usage"]["recording_mb"]["quota"] == 0 and usage["usage"]["recording_mb"]["level"] in ("ok", "over")


def test_a_recording_over_the_storage_quota_is_not_kept(tight_mou):
    db = SessionLocal()
    try:
        db.add(Recording(id="rec_test_quota", college_id="col_demo_001", title="Over quota", storage_key="recordings/x.mp4",
                         status="over_quota", size_mb=500, batch_id="bat_aids_s5_aids"))
        db.commit()
    finally:
        db.close()
    r = client.get("/api/v1/student/recordings/rec_test_quota/url", headers=PRIYA)
    assert r.status_code == 409 and "storage is full" in r.json()["detail"]


def test_staff_see_every_college_and_colleges_see_their_own():
    d = client.get("/api/v1/admin/usage", headers=STAFF).json()
    demo = next(c for c in d["colleges"] if c["college_id"] == "col_demo_001")
    assert demo["students"] > 600 and demo["usage"]["lab_minutes"]["quota"] == demo["students"] * 60 * 60     # 60 h in the demo MoU
    assert set(demo["usage"]) == {"lab_minutes", "ai_calls", "recording_mb", "cloud_credits"}
    assert all(c["college_id"] != PLATFORM_TENANT for c in d["colleges"]) and "summary" in d
    mine = client.get("/api/v1/college/usage", headers=KAVITHA).json()
    assert mine["usage"]["lab_minutes"]["quota"] == demo["usage"]["lab_minutes"]["quota"]
    for h in (KAVITHA, ARUN, PRIYA):
        assert client.get("/api/v1/admin/usage", headers=h).status_code == 403
    assert client.get("/api/v1/admin/usage/irep_platform", headers=STAFF).status_code == 404
    assert client.get("/api/v1/admin/usage/col_nope", headers=STAFF).status_code == 404
    assert client.get("/api/v1/admin/usage?period=2026-13", headers=STAFF).status_code == 422


@pytest.mark.link("L23")
def test_mou_report_carries_usage_figures():
    rid = client.post("/api/v1/college/reports/generate", json={"report_type": "progress"}, headers=KAVITHA).json()["report"]["id"]
    try:
        pdf = client.get(f"/api/v1/college/reports/{rid}/download", headers=KAVITHA).content
        assert b"Usage this month" in pdf and b"Lab minutes:" in pdf and b"AI Study Buddy calls:" in pdf
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ReportRun).where(ReportRun.id == rid))
            db.commit()
        finally:
            db.close()


def test_cyber_range_access_expires_and_can_be_requested_again():
    db = SessionLocal()
    try:
        db.execute(delete(LabApproval).where(LabApproval.student_id == "std_priya_01", LabApproval.lab_id == "lab_cyber_range"))
        old = datetime.datetime.now() - datetime.timedelta(days=31)
        db.add(LabApproval(id="lap_test_expired", college_id="col_demo_001", lab_id="lab_cyber_range", student_id="std_priya_01",
                           status="approved", aup_accepted_at=old, decided_at=old, decided_by="trn_arun_01"))
        db.commit()
    finally:
        db.close()
    try:
        cyber = next(l for l in client.get("/api/v1/student/labs", headers=PRIYA).json()["labs"] if l["id"] == "lab_cyber_range")
        assert cyber["locked"]["reason"] == "approval_expired"
        again = client.post("/api/v1/student/labs/lab_cyber_range/request-access", json={"accept_aup": True}, headers=PRIYA).json()
        assert again["status"] == "pending" and again["approval_id"] != "lap_test_expired"
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(LabApproval).where(LabApproval.student_id == "std_priya_01", LabApproval.lab_id == "lab_cyber_range"))
            db.commit()
        finally:
            db.close()
