"""Screen 04 · Trainer batches. Spec: docs/screens/04-trainer-batches.md"""
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
from models.schema import (Invitation, AuditLog, Batch, BatchTrainer, Branch, College, MouTerm, Notification, OutboxEvent, ParentStudent,
                           RosterChangeRequest, Student, Trainer, TrainerNote, User)

from tests.invite_helpers import set_password
client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
ARUN, MEENA = _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer")
KAVITHA, PRIYA, RAMESH = _h("usr_kavitha_01", "college_admin"), _h("usr_priya_01", "student"), _h("usr_ramesh_01", "parent")


# ---- demo college: what Arun sees --------------------------------------------

def test_trainer_sees_only_mapped_batches_and_their_students():
    batches = client.get("/api/v1/trainer/batches", headers=ARUN).json()["batches"]
    assert {b["short_name"] for b in batches} == {"CSE-A", "CSE-B", "IT-A", "AI&DS", "Cyber"}
    aids = next(b for b in batches if b["short_name"] == "AI&DS")
    assert aids["students"] == 50 and aids["avg_readiness"] == 79
    roster = client.get(f"/api/v1/trainer/batches/{aids['id']}/roster", headers=ARUN).json()
    assert len(roster["students"]) == 50 and any(s["id"] == "std_priya_01" for s in roster["students"])
    db = SessionLocal()
    try:
        not_mine = db.execute(select(Batch.id).where(Batch.college_id == "col_demo_001",
                                                     Batch.id.not_in([b["id"] for b in batches]))).scalars().first()
        outsider = db.execute(select(Student.id).where(Student.batch_id == not_mine)).scalars().first()
    finally:
        db.close()
    assert client.get(f"/api/v1/trainer/batches/{not_mine}/roster", headers=ARUN).status_code == 404
    assert client.get(f"/api/v1/trainer/students/{outsider}", headers=ARUN).status_code == 404
    assert client.get("/api/v1/trainer/batches", headers=PRIYA).status_code == 403


def test_private_notes_are_for_the_batch_trainers_only():
    r = client.post("/api/v1/trainer/students/std_priya_01/notes", json={"text": "Needs help with time complexity; pair with Vikram."}, headers=ARUN)
    assert r.status_code == 201
    note_id = r.json()["id"]
    try:
        prof = client.get("/api/v1/trainer/students/std_priya_01", headers=ARUN).json()
        mine = next(n for n in prof["notes"] if n["id"] == note_id)
        assert mine["mine"] is True and mine["author"] == "Arun Kumar"
        assert prof["parents"] and set(prof["parents"][0]) == {"name", "relationship"}       # names only
        # never visible to the student, parent or college
        for h in (PRIYA, RAMESH):
            assert client.get("/api/v1/trainer/students/std_priya_01", headers=h).status_code == 403
        assert "pair with Vikram" not in client.get("/api/v1/college/overview", headers=KAVITHA).text
        assert "pair with Vikram" not in client.get("/api/v1/parent/overview", headers=RAMESH).text
        db = SessionLocal()
        try:
            audit = db.execute(select(AuditLog).where(AuditLog.action == "trainer.note_added", AuditLog.entity_id == "std_priya_01")
                               .order_by(AuditLog.created_at.desc())).scalars().first()
            assert "Vikram" not in str(audit.detail)                                          # note text never copied
        finally:
            db.close()
    finally:
        assert client.delete(f"/api/v1/trainer/notes/{note_id}", headers=ARUN).status_code == 200


def test_only_the_author_deletes_a_note():
    note_id = client.post("/api/v1/trainer/students/std_priya_01/notes", json={"text": "temp"}, headers=ARUN).json()["id"]
    db = SessionLocal()
    try:
        other = db.execute(select(Trainer).where(Trainer.college_id == "col_demo_001", Trainer.id != "trn_arun_01")).scalars().first()
        other_h = _h(other.user_id, "trainer")
    finally:
        db.close()
    assert client.delete(f"/api/v1/trainer/notes/{note_id}", headers=other_h).status_code == 403
    assert client.delete(f"/api/v1/trainer/notes/{note_id}", headers=ARUN).status_code == 200


# ---- L24 round trip in a fresh college ----------------------------------------

@pytest.fixture
def college():
    code = "B" + uuid.uuid4().hex[:7].upper()
    cid = client.post("/api/v1/admin/colleges", json={"name": "Batches Test College", "code": code, "city": "Hosur", "state": "TN"},
                      headers=STAFF).json()["id"]
    email = f"admin.{code.lower()}@college.example"
    temp = set_password(client.post(f"/api/v1/admin/colleges/{cid}/admins", json={"name": "Dr. Admin", "email": email}, headers=STAFF).json())
    admin_h = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"role": "college", "identifier": email, "password": temp}).json()["access_token"]}
    tuid, tid = f"usr_trn_{code.lower()}", f"trn_{code.lower()}"
    db = SessionLocal()
    try:
        db.add(User(id=tuid, college_id=cid, email=f"t.{code.lower()}@college.example", hashed_password="x", role="trainer", name="Trainer T", avatar_initials="TT"))
        db.flush()
        db.add(Trainer(id=tid, college_id=cid, user_id=tuid))
        db.commit()
    finally:
        db.close()
    yield {"id": cid, "code": code, "admin": admin_h, "trainer": tid, "trainer_h": _h(tuid, "trainer", cid)}
    db = SessionLocal()
    try:
        db.execute(delete(RosterChangeRequest).where(RosterChangeRequest.college_id == cid))
        db.execute(delete(TrainerNote).where(TrainerNote.college_id == cid))
        db.execute(delete(ParentStudent).where(ParentStudent.college_id == cid))
        db.execute(delete(Student).where(Student.college_id == cid))
        db.execute(delete(BatchTrainer).where(BatchTrainer.college_id == cid))
        db.execute(delete(Batch).where(Batch.college_id == cid))
        db.execute(delete(Branch).where(Branch.college_id == cid))
        db.execute(delete(Trainer).where(Trainer.college_id == cid))
        db.execute(delete(Notification).where(Notification.college_id == cid))
        db.execute(delete(Invitation).where(Invitation.college_id == cid))
        db.execute(delete(User).where(User.college_id == cid))
        db.execute(delete(OutboxEvent).where(OutboxEvent.college_id == cid))
        db.execute(delete(MouTerm).where(MouTerm.college_id == cid))
        db.execute(delete(College).where(College.id == cid))
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L24")
def test_structure_down_and_roster_changes_up(college):
    h, tag = college["admin"], college["code"].lower()
    br = client.post("/api/v1/college/branches", json={"name": "ECE", "code": "ECE"}, headers=h).json()["id"]
    a = client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "ECE-A", "semester": 4, "academic_year": "2026-27"}, headers=h).json()["id"]
    b = client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "ECE-B", "semester": 4, "academic_year": "2026-27"}, headers=h).json()["id"]
    other_sem = client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "ECE-C", "semester": 6, "academic_year": "2026-27"}, headers=h).json()["id"]
    csv = ("register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone\n"
           f"R{tag}1,Mani S,mani.{tag}@stu.example,,ECE,ECE-A,4,,\n")
    client.post("/api/v1/college/students/import?dry_run=false", files={"file": ("s.csv", csv.encode(), "text/csv")}, headers=h)

    # down: nothing until the college maps the trainer on 03
    assert client.get("/api/v1/trainer/batches", headers=college["trainer_h"]).json()["batches"] == []
    client.post(f"/api/v1/college/batches/{a}/trainers", json={"trainer_id": college["trainer"]}, headers=h)
    mine = client.get("/api/v1/trainer/batches", headers=college["trainer_h"]).json()["batches"]
    assert [x["short_name"] for x in mine] == ["ECE-A"] and mine[0]["students"] == 1
    sid = client.get(f"/api/v1/trainer/batches/{a}/roster", headers=college["trainer_h"]).json()["students"][0]["id"]

    # up: a move request, validated, approved on 03
    bad = client.post("/api/v1/trainer/roster-requests", json={"student_id": sid, "kind": "move", "to_batch_id": other_sem,
                                                              "reason": "Wants the evening batch slot"}, headers=college["trainer_h"])
    assert bad.status_code == 422
    rid = client.post("/api/v1/trainer/roster-requests", json={"student_id": sid, "kind": "move", "to_batch_id": b,
                                                              "reason": "Timetable clash with lab hours"}, headers=college["trainer_h"]).json()["id"]
    assert client.post("/api/v1/trainer/roster-requests", json={"student_id": sid, "kind": "remove",
                                                               "reason": "Second request should be refused"}, headers=college["trainer_h"]).status_code == 409
    queue = client.get("/api/v1/college/roster-requests", headers=h).json()["items"]
    assert queue[0]["id"] == rid and (queue[0]["from_batch"], queue[0]["to_batch"]) == ("ECE-A", "ECE-B")
    assert client.post(f"/api/v1/college/roster-requests/{rid}/approve", headers=KAVITHA).status_code == 404        # other college
    done = client.post(f"/api/v1/college/roster-requests/{rid}/approve", headers=h).json()
    assert done["status"] == "approved" and done["student_batch_id"] == b
    # the trainer no longer sees the student (not mapped to ECE-B) and was notified
    assert client.get(f"/api/v1/trainer/batches/{a}/roster", headers=college["trainer_h"]).json()["students"] == []
    db = SessionLocal()
    try:
        tuser = db.get(Trainer, college["trainer"]).user_id
        assert db.execute(select(Notification).where(Notification.user_id == tuser, Notification.title_en == "Roster change approved")).first()
    finally:
        db.close()


def test_rejection_needs_a_reason(college):
    h, tag = college["admin"], college["code"].lower()
    br = client.post("/api/v1/college/branches", json={"name": "ECE", "code": "ECE"}, headers=h).json()["id"]
    a = client.post("/api/v1/college/batches", json={"branch_id": br, "short_name": "ECE-A", "semester": 4, "academic_year": "2026-27"}, headers=h).json()["id"]
    csv = ("register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone\n"
           f"R{tag}1,Mani S,mani.{tag}@stu.example,,ECE,ECE-A,4,,\n")
    client.post("/api/v1/college/students/import?dry_run=false", files={"file": ("s.csv", csv.encode(), "text/csv")}, headers=h)
    client.post(f"/api/v1/college/batches/{a}/trainers", json={"trainer_id": college["trainer"]}, headers=h)
    sid = client.get(f"/api/v1/trainer/batches/{a}/roster", headers=college["trainer_h"]).json()["students"][0]["id"]
    rid = client.post("/api/v1/trainer/roster-requests", json={"student_id": sid, "kind": "remove", "reason": "Discontinued the programme"},
                      headers=college["trainer_h"]).json()["id"]
    assert client.post(f"/api/v1/college/roster-requests/{rid}/reject", json={"reason": ""}, headers=h).status_code == 422
    assert client.post(f"/api/v1/college/roster-requests/{rid}/reject", json={"reason": "Talk to the student first"}, headers=h).json()["status"] == "rejected"
    assert client.post(f"/api/v1/college/roster-requests/{rid}/approve", headers=h).status_code == 409
