"""Screen 22 · Assessments: problems and tests down to 24 and 23 and results back (L13);
the IREP bank from 46 (L37). Spec: docs/screens/22-assessments.md"""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import Notification, Student

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


ARUN, MEENA, PRIYA = _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer"), _h("usr_priya_01", "student")
STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
PRIYA_BATCH = "bat_aids_s5_aids"
PROBLEM = {"title": "Count vowels", "statement": "Read a line and print how many vowels it has.", "constraints": "length <= 1000",
           "difficulty": "Easy", "topic": "Strings", "trainer_notes": "Remind them about uppercase vowels.",
           "cases": [{"name": "Sample", "input_data": "hello", "expected_output": "2"},
                     {"name": "Upper", "input_data": "AEIOU", "expected_output": "5", "is_hidden": True}]}
TEST = {"title": "Quick aptitude", "duration_min": 10, "questions": [
    {"question_text": "2 + 2 * 2 = ?", "option_a": "6", "option_b": "8", "option_c": "4", "option_d": "10", "correct_option": "A"},
    {"question_text": "Next in 2, 4, 8, ?", "option_a": "10", "option_b": "12", "option_c": "16", "option_d": "14", "correct_option": "C"}]}


def _other_batch_student():
    db = SessionLocal()
    try:
        st = db.execute(select(Student).where(Student.college_id == "col_demo_001", Student.batch_id == "bat_cse_s2")).scalars().first()
        return _h(st.user_id, "student")
    finally:
        db.close()


@pytest.fixture(autouse=True)
def restore():
    yield
    from seed.seed_screen22 import seed_screen22
    db = SessionLocal()
    try:
        seed_screen22(db)
        db.commit()
    finally:
        db.close()


@pytest.mark.link("L13")
def test_problem_goes_down_to_the_batch_and_results_come_back():
    pid = client.post("/api/v1/trainer/assessments/problems", json=PROBLEM, headers=ARUN).json()["id"]
    assert all(p["id"] != pid for p in client.get("/api/v1/student/coding", headers=PRIYA).json()["problems"])   # draft
    assert client.get(f"/api/v1/student/coding/{pid}", headers=PRIYA).status_code == 404
    due = (datetime.datetime.now() + datetime.timedelta(days=3)).replace(microsecond=0).isoformat()
    pub = client.post(f"/api/v1/trainer/assessments/problem/{pid}/publish", json={"batch_ids": [PRIYA_BATCH], "due_at": due}, headers=ARUN)
    assert pub.status_code == 200 and pub.json()["status"] == "published" and pub.json()["notified"] > 0
    assert any(p["id"] == pid for p in client.get("/api/v1/student/coding", headers=PRIYA).json()["problems"])
    detail = client.get(f"/api/v1/student/coding/{pid}", headers=PRIYA).json()
    assert detail["trainer_notes"] == "Remind them about uppercase vowels."                          # notes travel down
    other = _other_batch_student()
    assert client.get(f"/api/v1/student/coding/{pid}", headers=other).status_code == 404               # not their batch
    assert client.post(f"/api/v1/student/coding/{pid}/submit", json={"code": "x", "language": "python"}, headers=other).status_code == 404

    client.put(f"/api/v1/trainer/assessments/problem/{pid}/notes", json={"trainer_notes": "Use str.lower()."}, headers=ARUN)
    assert client.get(f"/api/v1/student/coding/{pid}", headers=PRIYA).json()["trainer_notes"] == "Use str.lower()."
    sub = client.post(f"/api/v1/student/coding/{pid}/submit",
                      json={"code": "def solve():\n    s = input()\n    print(sum(c in 'aeiouAEIOU' for c in s))\n", "language": "python"}, headers=PRIYA)
    assert sub.status_code == 200
    res = client.get(f"/api/v1/trainer/assessments/problem/{pid}/results", headers=ARUN).json()
    priya = next(r for r in res["students"] if r["student_id"] == "std_priya_01")
    assert priya["attempts"] == 1 and priya["result"] and res["summary"]["attempted"] == 1
    assert all(r["batch"] for r in res["students"])
    db = SessionLocal()
    try:
        assert db.execute(select(Notification).where(Notification.user_id == "usr_priya_01", Notification.link == f"/student/coding/{pid}")).first()
    finally:
        db.close()

    assert client.post(f"/api/v1/trainer/assessments/problem/{pid}/unpublish", headers=ARUN).json()["status"] == "draft"
    assert client.get(f"/api/v1/student/coding/{pid}", headers=PRIYA).status_code == 404


@pytest.mark.link("L13")
def test_test_goes_down_and_the_score_comes_back():
    tid = client.post("/api/v1/trainer/assessments/tests", json=TEST, headers=ARUN).json()["id"]
    assert all(t["id"] != tid for t in client.get("/api/v1/student/tests", headers=PRIYA).json()["tests"])
    assert client.get(f"/api/v1/student/tests/{tid}", headers=PRIYA).status_code == 404
    client.post(f"/api/v1/trainer/assessments/test/{tid}/publish", json={"batch_ids": [PRIYA_BATCH]}, headers=ARUN)
    assert any(t["id"] == tid for t in client.get("/api/v1/student/tests", headers=PRIYA).json()["tests"])
    att = client.post(f"/api/v1/student/tests/{tid}/attempts", headers=PRIYA).json()
    out = client.post(f"/api/v1/student/tests/attempts/{att['attempt_id']}/submit", json={"answers": {"1": "A", "2": "B"}}, headers=PRIYA)
    assert out.status_code == 200
    res = client.get(f"/api/v1/trainer/assessments/test/{tid}/results", headers=ARUN).json()
    priya = next(r for r in res["students"] if r["student_id"] == "std_priya_01")
    assert priya["score"] == "1/2" and priya["done"]
    assert next(t for t in client.get("/api/v1/student/tests", headers=PRIYA).json()["tests"] if t["id"] == tid)["best_score"] == "1/2"


def test_publishing_guards():
    pid = client.post("/api/v1/trainer/assessments/problems", json=PROBLEM, headers=ARUN).json()["id"]
    assert client.post(f"/api/v1/trainer/assessments/problem/{pid}/publish", json={"batch_ids": [PRIYA_BATCH]}, headers=MEENA).status_code == 403
    past = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    assert client.post(f"/api/v1/trainer/assessments/problem/{pid}/publish", json={"batch_ids": [PRIYA_BATCH], "due_at": past}, headers=ARUN).status_code == 422
    assert client.get(f"/api/v1/trainer/assessments/problem/{pid}/results", headers=_h("usr_arun_01", "trainer", "col_other_test")).status_code in (403, 404)
    assert client.get("/api/v1/trainer/assessments", headers=PRIYA).status_code == 403
    assert client.post("/api/v1/trainer/assessments/problems", json={**PROBLEM, "cases": [{**PROBLEM["cases"][1]}]}, headers=ARUN).status_code == 422
    bad = {**TEST, "questions": [{**TEST["questions"][0], "correct_option": "E"}]}
    assert client.post("/api/v1/trainer/assessments/tests", json=bad, headers=ARUN).status_code == 422
    # a college-wide seeded problem: unpublishing removes only Arun's batches
    r = client.post("/api/v1/trainer/assessments/problem/prob_two_sum/unpublish", headers=ARUN).json()
    assert r["status"] == "published" and PRIYA_BATCH not in r["batch_ids"] and len(r["batch_ids"]) > 0
    assert client.get("/api/v1/student/coding/prob_two_sum", headers=PRIYA).status_code == 404
    assert client.get("/api/v1/student/coding/prob_two_sum", headers=_other_batch_student()).status_code == 200


def test_practice_test_never_falls_back_to_another_test():
    assert client.get("/api/v1/student/tests/test_does_not_exist", headers=PRIYA).status_code == 404
    assert client.post("/api/v1/student/tests/test_does_not_exist/attempts", headers=PRIYA).status_code == 404
    assert client.get("/api/v1/student/tests/bank_test_aptitude_core", headers=PRIYA).status_code == 404    # platform bank, not her college


@pytest.mark.link("L37")
def test_bank_items_import_into_the_college_as_drafts():
    bank = client.get("/api/v1/trainer/bank", headers=ARUN).json()
    assert any(p["id"] == "bank_prob_pair_sum" for p in bank["problems"]) and any(t["id"] == "bank_test_aptitude_core" for t in bank["tests"])
    imp = client.post("/api/v1/trainer/bank/problem/bank_prob_pair_sum/import", headers=ARUN)
    assert imp.status_code == 201 and imp.json()["status"] == "draft" and imp.json()["source_id"] == "bank_prob_pair_sum"
    assert client.post("/api/v1/trainer/bank/problem/bank_prob_pair_sum/import", headers=ARUN).status_code == 409
    t = client.post("/api/v1/trainer/bank/test/bank_test_aptitude_core/import", headers=ARUN).json()
    client.post(f"/api/v1/trainer/assessments/test/{t['id']}/publish", json={"batch_ids": [PRIYA_BATCH]}, headers=ARUN)
    assert len(client.get(f"/api/v1/student/tests/{t['id']}", headers=PRIYA).json()["questions"]) == 5
    assert next(p for p in client.get("/api/v1/admin/content/bank", headers=STAFF).json()["problems"] if p["id"] == "bank_prob_pair_sum")["imports"] == 1

    added = client.post("/api/v1/admin/content/bank/problems", json=PROBLEM, headers=STAFF)
    assert added.status_code == 201 and added.json()["status"] == "published"
    assert any(p["id"] == added.json()["id"] for p in client.get("/api/v1/trainer/bank", headers=ARUN).json()["problems"])
    assert all(p["id"] != added.json()["id"] for p in client.get("/api/v1/student/coding", headers=PRIYA).json()["problems"])   # bank is not live
    assert client.get("/api/v1/admin/content/bank", headers=ARUN).status_code == 403
    assert client.post("/api/v1/trainer/bank/problem/prob_two_sum/import", headers=ARUN).status_code == 404       # not a bank item
