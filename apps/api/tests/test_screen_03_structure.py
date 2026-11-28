"""Screen 03 · Branches and batches. Spec: docs/screens/03-branches-and-batches.md

Every test runs in a college created on screen 45 by IREP staff and set up
here by its first admin (link L25); the fixture removes the college after.
"""
import sys
import uuid
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
from models.schema import (Invitation, AuditLog, Batch, BatchTrainer, Branch, College, ConsentRecord, MouTerm, OutboxEvent, ParentStudent,
                           Student, Trainer, User)

from tests.invite_helpers import set_password
client = TestClient(app)
STAFF = {"Authorization": "Bearer " + create_access_token({"sub": "usr_irep_staff_01", "role": "irep_admin", "college_id": PLATFORM_TENANT})}
KAVITHA = {"Authorization": "Bearer " + create_access_token({"sub": "usr_kavitha_01", "role": "college_admin", "college_id": "col_demo_001"})}


@pytest.fixture
def college():
    """L25: staff create the college and its first admin on 45; the admin signs in."""
    code = "S" + uuid.uuid4().hex[:7].upper()
    cid = client.post("/api/v1/admin/colleges", json={"name": "Structure Test College", "code": code, "city": "Trichy",
                                                      "state": "Tamil Nadu"}, headers=STAFF).json()["id"]
    email = f"admin.{code.lower()}@college.example"
    temp = set_password(client.post(f"/api/v1/admin/colleges/{cid}/admins", json={"name": "Dr. Admin", "email": email}, headers=STAFF).json())
    tok = client.post("/api/v1/auth/login", json={"role": "college", "identifier": email, "password": temp}).json()["access_token"]
    db = SessionLocal()
    try:
        tuid = f"usr_trn_{code.lower()}"
        db.add(User(id=tuid, college_id=cid, email=f"trainer.{code.lower()}@college.example", hashed_password="x", role="trainer",
                    name="Trainer One", avatar_initials="T1"))
        db.flush()
        db.add(Trainer(id=f"trn_{code.lower()}", college_id=cid, user_id=tuid))
        tuid2 = f"usr_trn2_{code.lower()}"
        db.add(User(id=tuid2, college_id=cid, email=f"trainer2.{code.lower()}@college.example", hashed_password="x", role="trainer",
                    name="Trainer Two", avatar_initials="T2"))
        db.flush()
        db.add(Trainer(id=f"trn2_{code.lower()}", college_id=cid, user_id=tuid2))
        db.commit()
    finally:
        db.close()
    yield {"id": cid, "code": code, "h": {"Authorization": f"Bearer {tok}"}, "trainer": f"trn_{code.lower()}", "trainer2": f"trn2_{code.lower()}"}
    db = SessionLocal()
    try:
        sids = list(db.execute(select(Student.id).where(Student.college_id == cid)).scalars())
        db.execute(delete(ConsentRecord).where(ConsentRecord.subject_student_id.in_(sids or ["_"])))
        db.execute(delete(ParentStudent).where(ParentStudent.college_id == cid))
        db.execute(delete(Student).where(Student.college_id == cid))
        db.execute(delete(BatchTrainer).where(BatchTrainer.college_id == cid))
        db.execute(delete(Batch).where(Batch.college_id == cid))
        db.execute(delete(Branch).where(Branch.college_id == cid))
        db.execute(delete(Trainer).where(Trainer.college_id == cid))
        db.execute(delete(Invitation).where(Invitation.college_id == cid))
        db.execute(delete(User).where(User.college_id == cid))
        db.execute(delete(OutboxEvent).where(OutboxEvent.college_id == cid))
        db.execute(delete(MouTerm).where(MouTerm.college_id == cid))
        db.execute(delete(College).where(College.id == cid))
        db.commit()
    finally:
        db.close()


def _setup(c):
    br = client.post("/api/v1/college/branches", json={"name": "Computer Science", "code": "CSE"}, headers=c["h"]).json()["id"]
    bt = client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "CSE-A", "semester": 5, "academic_year": "2026-27"},
                     headers=c["h"]).json()["id"]
    return br, bt


CSV_HEADER = "register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone,parent_email,parent_consent,parent_consent_ref\n"


def _import(c, body, dry_run):
    return client.post(f"/api/v1/college/students/import?dry_run={'true' if dry_run else 'false'}",
                       files={"file": ("students.csv", (CSV_HEADER + body).encode("utf-8"), "text/csv")}, headers=c["h"])


@pytest.mark.link("L25")
def test_first_admin_sets_up_a_new_college(college):
    empty = client.get("/api/v1/college/structure", headers=college["h"]).json()
    assert empty == {"students_total": 0, "unassigned_students": 0, "branches": []}
    br, bt = _setup(college)
    tag = college["code"].lower()
    rows = (f"R{tag}01,Anu K,anu.{tag}@stu.example,9876501001,CSE,CSE-A,5,Kumar K,9876502001,,yes,FORM-{tag}-01\n"
            f"R{tag}02,Bala S,bala.{tag}@stu.example,,cse,cse-a,5,,,,,\n")
    dry = _import(college, rows, True).json()
    assert dry["can_import"] is True and dry["summary"] == {"rows": 2, "errors": 0, "new": 2, "updated": 0, "parents_linked": 1,
                                                            "parents_without_email": 1}
    assert client.get("/api/v1/college/structure", headers=college["h"]).json()["students_total"] == 0      # dry run wrote nothing
    done = _import(college, rows, False).json()
    assert done["imported"] is True
    st = client.get("/api/v1/college/structure", headers=college["h"]).json()
    assert st["students_total"] == 2 and st["branches"][0]["batches"][0]["students"] == 2
    # staff see the onboarded college with its students (45 <- 03)
    assert client.get(f"/api/v1/admin/colleges/{college['id']}", headers=STAFF).json()["college"]["students"] == 2
    # the imported parent signs in with OTP; the consent form recorded at import already covers screen 15 (48)
    otp = client.post("/api/v1/auth/parent/otp/request", json={"phone": "9876502001"}).json()["demo_otp"]
    ptok = client.post("/api/v1/auth/parent/otp/verify", json={"phone": "9876502001", "otp": otp}).json()["access_token"]
    assert client.get("/api/v1/parent/overview", headers={"Authorization": f"Bearer {ptok}"}).json().get("consent_required") is not True
    db = SessionLocal()
    try:
        audit = db.execute(select(AuditLog).where(AuditLog.college_id == college["id"], AuditLog.action == "students.imported")).scalar_one()
        assert audit.detail["new"] == 2 and "Anu" not in str(audit.detail)          # counts only, no personal data
    finally:
        db.close()


def test_reimport_updates_and_reports_row_errors(college):
    _setup(college)
    tag = college["code"].lower()
    _import(college, f"R{tag}01,Anu K,anu.{tag}@stu.example,,CSE,CSE-A,5,,,,,\n", False)
    again = _import(college, f"R{tag}01,Anu Kumari,anu.{tag}@stu.example,9876501002,CSE,CSE-A,5,,,,,\n", False).json()
    assert again["summary"]["new"] == 0 and again["summary"]["updated"] == 1
    db = SessionLocal()
    try:
        s = db.execute(select(Student).where(Student.college_id == college["id"])).scalars().all()
        assert len(s) == 1 and db.get(User, s[0].user_id).name == "Anu Kumari"
    finally:
        db.close()
    bad = (f"R{tag}02,Bala,bala.{tag}@stu.example,,ECE,ECE-A,5,,,,,\n"          # unknown branch
           f"R{tag}03,Chitra,not-an-email,,CSE,CSE-A,5,,,,,\n"
           f"R{tag}04,Devi,devi.{tag}@stu.example,,CSE,CSE-A,6,,,,,\n"           # semester mismatch
           f"R{tag}05,Ezhil,priya.r@demo.edu,,CSE,CSE-A,5,,,,,\n"                # another account's email
           f"R{tag}06,Fathima,f.{tag}@stu.example,12345,CSE,CSE-A,5,,,,,\n"
           f"R{tag}06,Fathima,f2.{tag}@stu.example,,CSE,CSE-A,5,,,,,\n")
    r = _import(college, bad, False).json()
    assert r["dry_run"] is True and r["can_import"] is False                   # errors block the real import
    assert [e["row"] for e in r["errors"]] == [2, 3, 4, 5, 6, 7]
    assert "ECE" in r["errors"][0]["error"] and "another account" in r["errors"][3]["error"]
    missing = client.post("/api/v1/college/students/import?dry_run=true",
                          files={"file": ("x.csv", b"register_no,name\nA1,B\n", "text/csv")}, headers=college["h"])
    assert missing.status_code == 422 and "Missing columns" in missing.json()["detail"]


def test_branches_batches_and_trainers(college):
    br, bt = _setup(college)
    assert client.post("/api/v1/college/branches", json={"name": "Again", "code": "cse"}, headers=college["h"]).status_code == 409
    assert client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "CSE-A", "semester": 5, "academic_year": "2026-27"},
                       headers=college["h"]).status_code == 409
    assert client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "CSE-B", "semester": 9, "academic_year": "2026-27"},
                       headers=college["h"]).status_code == 422
    # another college's branch/batch/trainer is not found (tenant), never forbidden
    assert client.post("/api/v1/college/batches", json={"branch_id": "br_cse_x", "short_name": "ZZ-A", "semester": 5, "academic_year": "2026-27"},
                       headers=college["h"]).status_code == 404
    assert client.post(f"/api/v1/college/batches/{bt}/trainers", json={"trainer_id": "trn_arun_01"}, headers=college["h"]).status_code == 404
    assert client.post(f"/api/v1/college/batches/{bt}/trainers", json={"trainer_id": college["trainer"]}, headers=KAVITHA).status_code == 404

    assert client.post(f"/api/v1/college/batches/{bt}/trainers", json={"trainer_id": college["trainer"]}, headers=college["h"]).status_code == 201
    two = client.post(f"/api/v1/college/batches/{bt}/trainers", json={"trainer_id": college["trainer2"]}, headers=college["h"])
    assert two.status_code == 409                                                # one primary per batch
    assert client.post(f"/api/v1/college/batches/{bt}/trainers", json={"trainer_id": college["trainer2"], "role": "substitute"},
                       headers=college["h"]).status_code == 201
    batch = client.get("/api/v1/college/structure", headers=college["h"]).json()["branches"][0]["batches"][0]
    assert sorted((t["name"], t["role"]) for t in batch["trainers"]) == [("Trainer One", "primary"), ("Trainer Two", "substitute")]
    assert client.delete(f"/api/v1/college/batches/{bt}/trainers/{college['trainer2']}", headers=college["h"]).status_code == 200


def test_promote_moves_batch_and_students(college):
    br, bt = _setup(college)
    tag = college["code"].lower()
    _import(college, f"R{tag}01,Anu K,anu.{tag}@stu.example,,CSE,CSE-A,5,,,,,\n", False)
    r = client.post(f"/api/v1/college/batches/{bt}/promote", headers=college["h"]).json()
    assert r == {"batch_id": bt, "semester": 6, "students": 1}
    db = SessionLocal()
    try:
        s = db.execute(select(Student).where(Student.college_id == college["id"])).scalar_one()
        assert s.semester == 6 and s.batch_name == "CSE-A · Sem 6"
        db.get(Batch, bt).semester = 7
        db.commit()
    finally:
        db.close()
    assert client.post(f"/api/v1/college/batches/{bt}/promote", headers=college["h"]).status_code == 409


@pytest.mark.parametrize("headers", [
    {"Authorization": "Bearer " + create_access_token({"sub": "usr_arun_01", "role": "trainer", "college_id": "col_demo_001"})},
    STAFF,
    {"Authorization": "Bearer " + create_access_token({"sub": "usr_priya_01", "role": "student", "college_id": "col_demo_001"})},
])
def test_only_college_admins(headers):
    assert client.get("/api/v1/college/structure", headers=headers).status_code == 403
    assert client.post("/api/v1/college/branches", json={"name": "X branch", "code": "XB"}, headers=headers).status_code == 403


def test_demo_college_structure_matches_the_cohort():
    st = client.get("/api/v1/college/structure", headers=KAVITHA).json()
    assert st["students_total"] == 612 and len(st["branches"]) == 4
