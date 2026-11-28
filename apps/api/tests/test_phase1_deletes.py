"""Phase 1: delete across screens (docs/plans/2026-11-27-feedback-plan.md, decision D2).

Never used by anyone: removed for good. Used by students or other records: hidden, kept for results and reports.
Every delete is audited; stored files are removed after commit through the outbox (storage.delete)."""
import datetime
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import (AuditLog, Certificate, CodingProblem, CodingSubmission, College, Course, Event, Interview, MouTerm,
                           OutboxEvent, PracticeTest, ReportRun, TestAttempt, TestCase)

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


ARUN, MEENA = _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer")
PRIYA, KAVITHA = _h("usr_priya_01", "student"), _h("usr_kavitha_01", "college_admin")
ARUN_ELSEWHERE = _h("usr_arun_01", "trainer", "col_other_999")
STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
SUPER = _h("usr_irep_super_01", "super_admin", PLATFORM_TENANT)


def _audited(action, entity_id):
    with SessionLocal() as db:
        return db.execute(select(AuditLog.id).where(AuditLog.action == action, AuditLog.entity_id == entity_id)).first() is not None


def _file_delete_queued(key):
    with SessionLocal() as db:
        return any((e.payload or {}).get("key") == key
                   for e in db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "storage.delete")).scalars())


def _new_problem(headers=ARUN):
    r = client.post("/api/v1/trainer/assessments/problems", headers=headers, json={
        "title": f"Delete me {uuid.uuid4().hex[:6]}", "statement": "Print the sum of two numbers.",
        "cases": [{"name": "Sample", "input_data": "1 2", "expected_output": "3"}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _new_test():
    r = client.post("/api/v1/trainer/assessments/tests", headers=ARUN, json={
        "title": f"Delete me {uuid.uuid4().hex[:6]}", "duration_min": 10,
        "questions": [{"question_text": "What is 2 + 2?", "option_a": "3", "option_b": "4", "option_c": "5", "option_d": "6", "correct_option": "B"}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ------------------------------------------------------------------ trainer: problems and tests (screen 22)

def test_unused_problem_is_removed_for_good():
    pid = _new_problem()
    r = client.delete(f"/api/v1/trainer/assessments/problem/{pid}", headers=ARUN)
    assert r.status_code == 200 and r.json()["mode"] == "removed"
    with SessionLocal() as db:
        assert db.get(CodingProblem, pid) is None
        assert not db.execute(select(TestCase.id).where(TestCase.problem_id == pid)).first()
    assert _audited("assessment.deleted", pid)


def test_used_problem_is_hidden_and_its_submissions_kept():
    pid = _new_problem()
    sub_id = f"sub_t_{uuid.uuid4().hex[:10]}"
    with SessionLocal() as db:
        db.add(CodingSubmission(id=sub_id, college_id="col_demo_001", problem_id=pid, student_id="std_priya_01", code="print(3)", status="Accepted"))
        db.commit()
    try:
        r = client.delete(f"/api/v1/trainer/assessments/problem/{pid}", headers=ARUN)
        assert r.status_code == 200 and r.json()["mode"] == "hidden"
        listed = client.get("/api/v1/trainer/assessments", headers=ARUN).json()["problems"]
        assert pid not in [p["id"] for p in listed]                                         # gone from the trainer's list
        assert client.get(f"/api/v1/trainer/assessments/problem/{pid}/results", headers=ARUN).status_code == 404
        assert client.get(f"/api/v1/student/coding/{pid}", headers=PRIYA).status_code == 404
        with SessionLocal() as db:
            assert db.get(CodingSubmission, sub_id) is not None                             # results kept
            assert db.get(CodingProblem, pid).status == "deleted"
    finally:
        with SessionLocal() as db:
            db.execute(delete(CodingSubmission).where(CodingSubmission.id == sub_id))
            db.execute(delete(TestCase).where(TestCase.problem_id == pid))
            db.execute(delete(CodingProblem).where(CodingProblem.id == pid))
            db.commit()


def test_problem_published_to_another_trainers_batch_is_refused():
    pid = _new_problem()
    with SessionLocal() as db:
        db.get(CodingProblem, pid).status, db.get(CodingProblem, pid).batch_ids = "published", None   # every batch
        db.commit()
    try:
        r = client.delete(f"/api/v1/trainer/assessments/problem/{pid}", headers=ARUN)
        assert r.status_code == 409 and "other trainers" in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.execute(delete(TestCase).where(TestCase.problem_id == pid))
            db.execute(delete(CodingProblem).where(CodingProblem.id == pid))
            db.commit()


def test_test_with_an_attempt_in_progress_is_refused():
    tid = _new_test()
    att = f"att_t_{uuid.uuid4().hex[:10]}"
    with SessionLocal() as db:
        now = datetime.datetime.now()
        db.add(TestAttempt(id=att, college_id="col_demo_001", test_id=tid, student_id="std_priya_01", status="in_progress",
                           started_at=now, ends_at=now + datetime.timedelta(minutes=10), total_questions=1))
        db.commit()
    try:
        assert client.delete(f"/api/v1/trainer/assessments/test/{tid}", headers=ARUN).status_code == 409
        with SessionLocal() as db:
            db.get(TestAttempt, att).status = "submitted"
            db.commit()
        r = client.delete(f"/api/v1/trainer/assessments/test/{tid}", headers=ARUN)
        assert r.status_code == 200 and r.json()["mode"] == "hidden"
        assert tid not in [t["id"] for t in client.get("/api/v1/student/tests", headers=PRIYA).json().get("tests", [])]
    finally:
        with SessionLocal() as db:
            db.execute(delete(TestAttempt).where(TestAttempt.id == att))
            from models.schema import PracticeQuestion
            db.execute(delete(PracticeQuestion).where(PracticeQuestion.test_id == tid))
            db.execute(delete(PracticeTest).where(PracticeTest.id == tid))
            db.commit()


def test_assessment_delete_guards():
    pid = _new_problem()
    assert client.delete(f"/api/v1/trainer/assessments/problem/{pid}", headers=PRIYA).status_code == 403
    assert client.delete(f"/api/v1/trainer/assessments/problem/{pid}", headers=ARUN_ELSEWHERE).status_code == 404
    assert client.delete(f"/api/v1/trainer/assessments/widget/{pid}", headers=ARUN).status_code == 404
    assert client.delete(f"/api/v1/trainer/assessments/problem/{pid}", headers=ARUN).status_code == 200
    assert client.delete(f"/api/v1/trainer/assessments/problem/{pid}", headers=ARUN).status_code == 404     # already gone


# ------------------------------------------------------------------ trainer: interview recording (screen 37)

def test_interview_recording_delete_queues_the_file_removal():
    iid, key = f"iv_t_{uuid.uuid4().hex[:10]}", f"recordings/interviews/test_{uuid.uuid4().hex[:8]}.mp4"
    with SessionLocal() as db:
        db.add(Interview(id=iid, college_id="col_demo_001", student_id="std_priya_01", trainer_id="trn_arun_01", round_number=99,
                         round_type="technical", scheduled_at=datetime.datetime.now(), duration_min=30, status="completed",
                         submitted_at=datetime.datetime.now(), recording_key=key))
        db.commit()
    try:
        assert client.delete(f"/api/v1/trainer/interviews/{iid}/recording", headers=PRIYA).status_code == 403
        assert client.delete(f"/api/v1/trainer/interviews/{iid}/recording", headers=MEENA).status_code == 404   # not her interview
        r = client.delete(f"/api/v1/trainer/interviews/{iid}/recording", headers=ARUN)
        assert r.status_code == 200 and r.json()["has_recording"] is False
        assert _file_delete_queued(key) and _audited("interview.recording_deleted", iid)
        assert client.get(f"/api/v1/student/interviews/{iid}/recording", headers=PRIYA).status_code == 404
        assert client.delete(f"/api/v1/trainer/interviews/{iid}/recording", headers=ARUN).status_code == 404
    finally:
        with SessionLocal() as db:
            db.execute(delete(Interview).where(Interview.id == iid))
            db.commit()


# ------------------------------------------------------------------ student: external certificate (screen 26)

def test_student_deletes_own_pending_external_certificate_only():
    pending, earned = f"cert_t_{uuid.uuid4().hex[:8]}", f"cert_t_{uuid.uuid4().hex[:8]}"
    key = f"certificates/test_{pending}.pdf"
    with SessionLocal() as db:
        db.add(Certificate(id=pending, college_id="col_demo_001", student_id="std_priya_01", title="AWS CCP", issuer="AWS",
                           cert_type="external", status="pending_proof", proof_key=key))
        db.add(Certificate(id=earned, college_id="col_demo_001", student_id="std_priya_01", title="IREP DSA", cert_type="course", status="earned"))
        db.commit()
    try:
        mine = {c["id"]: c for c in client.get("/api/v1/student/certificates", headers=PRIYA).json()["certificates"]}
        assert mine[pending]["can_delete"] is True and mine[earned]["can_delete"] is False
        assert client.delete(f"/api/v1/student/certificates/{earned}", headers=PRIYA).status_code == 409
        assert client.delete(f"/api/v1/student/certificates/{pending}", headers=ARUN).status_code == 403
        assert client.delete(f"/api/v1/student/certificates/{pending}", headers=_h("usr_priya_01", "student", "col_other_999")).status_code == 404
        assert client.delete(f"/api/v1/student/certificates/{pending}", headers=PRIYA).status_code == 200
        with SessionLocal() as db:
            assert db.get(Certificate, pending) is None
        assert _file_delete_queued(key) and _audited("certificate.deleted", pending)
    finally:
        with SessionLocal() as db:
            db.execute(delete(Certificate).where(Certificate.id.in_([pending, earned])))
            db.commit()


# ------------------------------------------------------------------ college: events (42) and MoU reports (20)

def test_college_deletes_a_draft_event_but_not_a_published_one():
    body = {"title_en": "Delete-me meetup", "starts_at": (datetime.datetime.now() + datetime.timedelta(days=9)).isoformat()}
    draft = client.post("/api/v1/college/events", json=body, headers=KAVITHA).json()["id"]
    published = client.post("/api/v1/college/events", json=body, headers=KAVITHA).json()["id"]
    try:
        with SessionLocal() as db:
            db.get(Event, published).status = "published"
            db.commit()
        assert client.delete(f"/api/v1/college/events/{published}", headers=KAVITHA).status_code == 409   # cancel instead
        assert client.delete(f"/api/v1/college/events/{draft}", headers=ARUN).status_code == 403
        assert client.delete(f"/api/v1/college/events/{draft}", headers=_h("usr_kavitha_01", "college_admin", "col_other_999")).status_code == 404
        assert client.delete(f"/api/v1/college/events/{draft}", headers=KAVITHA).status_code == 200
        with SessionLocal() as db:
            assert db.get(Event, draft) is None
        assert _audited("event.deleted", draft)
    finally:
        with SessionLocal() as db:
            from models.schema import Notification, Rsvp
            db.execute(delete(Rsvp).where(Rsvp.event_id.in_([draft, published])))
            db.execute(delete(Event).where(Event.id.in_([draft, published])))
            db.commit()


def test_college_deletes_a_generated_report():
    rid = client.post("/api/v1/college/reports/generate", json={"report_type": "progress"}, headers=KAVITHA).json()["report"]["id"]
    with SessionLocal() as db:
        key = db.get(ReportRun, rid).file_path
    assert client.delete(f"/api/v1/college/reports/{rid}", headers=ARUN).status_code == 403
    assert client.delete(f"/api/v1/college/reports/{rid}", headers=_h("usr_kavitha_01", "college_admin", "col_other_999")).status_code == 404
    assert client.delete(f"/api/v1/college/reports/{rid}", headers=KAVITHA).status_code == 200
    assert rid not in [r["id"] for r in client.get("/api/v1/college/reports", headers=KAVITHA).json()["reports"]]
    assert _file_delete_queued(key) and _audited("report.deleted", rid)


# ------------------------------------------------------------------ IREP: courses (46), MoU and colleges (45)

def test_staff_delete_a_course_only_after_unpublishing():
    c = client.post("/api/v1/admin/content/courses", headers=STAFF,
                    json={"title_en": "Delete-me course", "semester": 5, "skill_key": "dsa"}).json()
    try:
        with SessionLocal() as db:
            db.get(Course, c["id"]).status = "published"
            db.commit()
        assert client.delete(f"/api/v1/admin/content/courses/{c['id']}", headers=STAFF).status_code == 409
        with SessionLocal() as db:
            db.get(Course, c["id"]).status = "draft"
            db.commit()
        assert client.delete(f"/api/v1/admin/content/courses/{c['id']}", headers=KAVITHA).status_code == 403
        r = client.delete(f"/api/v1/admin/content/courses/{c['id']}", headers=STAFF)
        assert r.status_code == 200 and r.json()["mode"] == "removed"
        assert c["id"] not in [x["id"] for x in client.get("/api/v1/admin/content/courses", headers=STAFF).json()["courses"]]
    finally:
        with SessionLocal() as db:
            db.execute(delete(Course).where(Course.id == c["id"]))
            db.commit()


def test_super_admin_deletes_an_empty_college_and_an_inactive_mou():
    code = f"DL{uuid.uuid4().hex[:6].upper()}"
    cid = client.post("/api/v1/admin/colleges", headers=STAFF, json={"name": "Delete-me College", "code": code, "city": "Madurai", "state": "TN"}).json()["id"]
    try:
        mou = {"starts_on": "2026-01-01", "ends_on": "2026-12-31", "students_cap": 100}
        active = client.post(f"/api/v1/admin/colleges/{cid}/mou", headers=SUPER, json=mou).json()["id"]
        draft = client.post(f"/api/v1/admin/colleges/{cid}/mou", headers=SUPER, json={**mou, "activate": False}).json()["id"]
        assert client.delete(f"/api/v1/admin/colleges/{cid}/mou/{active}", headers=SUPER).status_code == 409       # the active one stays
        assert client.delete(f"/api/v1/admin/colleges/{cid}/mou/{draft}", headers=STAFF).status_code == 403        # super admin only
        assert client.delete(f"/api/v1/admin/colleges/{cid}/mou/{draft}", headers=SUPER).status_code == 200
        assert client.delete(f"/api/v1/admin/colleges/col_demo_001", headers=SUPER).status_code == 409            # has people
        assert client.delete(f"/api/v1/admin/colleges/{cid}", headers=STAFF).status_code == 403
        assert client.delete(f"/api/v1/admin/colleges/{cid}", headers=SUPER).status_code == 200
        with SessionLocal() as db:
            assert db.get(College, cid) is None
            assert not db.execute(select(MouTerm.id).where(MouTerm.college_id == cid)).first()
        assert _audited("college.deleted", cid)
    finally:
        with SessionLocal() as db:
            db.execute(delete(MouTerm).where(MouTerm.college_id == cid))
            db.execute(delete(College).where(College.id == cid))
            db.commit()


def test_storage_delete_handler_removes_the_file_and_is_idempotent():
    from services.file_cleanup import delete_file_later
    from services.outbox import dispatch_pending
    from services.storage import get_storage
    key = f"tmp/test_delete_{uuid.uuid4().hex[:8]}.txt"
    get_storage().put(key, b"bye", "text/plain")
    with SessionLocal() as db:
        delete_file_later(db, key, college_id="col_demo_001", entity_type="test", entity_id=key)
        delete_file_later(db, key, college_id="col_demo_001", entity_type="test", entity_id=key)   # a repeat must not fail
        db.commit()
    dispatch_pending(SessionLocal, limit=1000)
    assert not get_storage().exists(key)
    with SessionLocal() as db:
        states = {e.status for e in db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "storage.delete")).scalars()
                  if (e.payload or {}).get("key") == key}
    assert states == {"done"}
