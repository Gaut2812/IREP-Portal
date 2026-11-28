"""Study Buddy (screen 25), Phase 2: saved conversations, course context, practice mode, feedback, and "explain my
last failed submission". The Claude adapter is tested with a stub client (no network)."""
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import BuddyConversation, CodingSubmission, StudyBuddyMessage, TestAttempt, UsageLedger
import routers.study_buddy as sb_router
from services import study_buddy as sb

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, RAMESH = _h("usr_priya_01", "student"), _h("usr_ramesh_01", "parent")
OTHER = _h("usr_cse_2_001_6c05", "student")


class Capture(sb.BuddyAdapter):
    name = "capture"

    def __init__(self):
        self.calls = []

    def reply(self, history, question, topic, lang, context=None):
        self.calls.append({"history": history, "question": question, "topic": topic, "context": context})
        return "Think about the base case first."


@pytest.fixture
def cap(monkeypatch):
    monkeypatch.setattr(sb_router, "MIN_GAP_SECONDS", 0)
    adapter = Capture()
    monkeypatch.setattr(sb_router, "get_adapter", lambda: adapter)
    with SessionLocal() as db:   # a running practice test would lock Study Buddy
        for att in db.execute(select(TestAttempt).where(TestAttempt.student_id == "std_priya_01", TestAttempt.status == "in_progress")).scalars():
            att.status = "expired"
        db.commit()
    yield adapter
    with SessionLocal() as db:
        db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.student_id == "std_priya_01"))
        db.execute(delete(BuddyConversation).where(BuddyConversation.student_id == "std_priya_01"))
        db.execute(delete(UsageLedger).where(UsageLedger.student_id == "std_priya_01", UsageLedger.kind == "ai_calls"))
        db.commit()


def test_conversations_keep_their_own_history_and_are_named_after_the_first_question(cap):
    a = client.post("/api/v1/student/buddy/conversations", headers=PRIYA, json={}).json()
    b = client.post("/api/v1/student/buddy/conversations", headers=PRIYA, json={}).json()
    assert a["title"] == "New chat"
    client.post("/api/v1/student/buddy/ask", headers=PRIYA, json={"question": "What is recursion?", "conversation_id": a["id"]})
    client.post("/api/v1/student/buddy/ask", headers=PRIYA, json={"question": "What is a JOIN in SQL?", "conversation_id": b["id"]})
    client.post("/api/v1/student/buddy/ask", headers=PRIYA, json={"question": "And tail recursion?", "conversation_id": a["id"]})
    assert [m["content"] for m in cap.calls[-1]["history"] if m["role"] == "user"] == ["What is recursion?"]    # only chat A
    msgs = client.get(f"/api/v1/student/buddy?conversation_id={a['id']}", headers=PRIYA).json()
    assert [m["content"] for m in msgs["messages"] if m["role"] == "user"] == ["What is recursion?", "And tail recursion?"]
    titles = {c["id"]: c["title"] for c in msgs["conversations"]}
    assert titles[a["id"]] == "What is recursion?" and titles[b["id"]] == "What is a JOIN in SQL?"

    assert client.patch(f"/api/v1/student/buddy/conversations/{a['id']}", headers=PRIYA, json={"title": "Recursion"}).json()["title"] == "Recursion"
    assert client.delete(f"/api/v1/student/buddy/conversations/{b['id']}", headers=PRIYA).json()["deleted"] == 2
    assert client.get(f"/api/v1/student/buddy?conversation_id={b['id']}", headers=PRIYA).status_code == 404


def test_course_context_and_practice_mode_reach_the_tutor(cap):
    courses = client.get("/api/v1/student/buddy", headers=PRIYA).json()["courses"]
    if not courses:
        pytest.skip("demo state: no published course for Priya")
    course = courses[0]
    c = client.post("/api/v1/student/buddy/conversations", headers=PRIYA, json={"course_id": course["id"], "mode": "practice"}).json()
    assert c["title"] == f"Practice: {course['title']}" and c["mode"] == "practice"
    client.post("/api/v1/student/buddy/ask", headers=PRIYA, json={"question": "Quiz me", "conversation_id": c["id"]})
    ctx = cap.calls[-1]["context"]
    assert course["title"] in ctx and sb.PRACTICE_MARK in ctx
    plain = client.post("/api/v1/student/buddy/conversations", headers=PRIYA, json={}).json()
    client.post("/api/v1/student/buddy/ask", headers=PRIYA, json={"question": "Hello there", "conversation_id": plain["id"]})
    assert cap.calls[-1]["context"] is None                                          # a plain chat adds nothing


def test_feedback_on_answers(cap):
    r = client.post("/api/v1/student/buddy/ask", headers=PRIYA, json={"question": "What is a stack?"}).json()
    assert client.post(f"/api/v1/student/buddy/messages/{r['answer_id']}/feedback", headers=PRIYA, json={"value": "up"}).json()["feedback"] == "up"
    msgs = client.get("/api/v1/student/buddy", headers=PRIYA).json()["messages"]
    assert next(m for m in msgs if m["id"] == r["answer_id"])["feedback"] == "up"
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert client.post(f"/api/v1/student/buddy/messages/{user_msg['id']}/feedback", headers=PRIYA, json={"value": "up"}).status_code == 404
    assert client.post(f"/api/v1/student/buddy/messages/{r['answer_id']}/feedback", headers=OTHER, json={"value": "down"}).status_code == 404


def test_explain_my_last_failed_submission(cap):
    sid = f"sub_t_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(CodingSubmission(id=sid, college_id="col_demo_001", problem_id="prob_two_sum", student_id="std_priya_01", language="python",
                                code="class Solution:\n    def twoSum(self, nums, target):\n        return [0, 0]\n", status="Wrong Answer",
                                tests_passed=1, tests_total=3))
        db.commit()
    try:
        r = client.post("/api/v1/student/buddy/explain-submission", headers=PRIYA, json={"problem_id": "prob_two_sum"})
        assert r.status_code == 200 and r.json()["conversation_id"]
        q = cap.calls[-1]["question"]
        assert "Two Sum" in q and "Wrong Answer" in q and "1 of 3" in q and "return [0, 0]" in q and "not the full solution" in q
        conv = next(c for c in client.get("/api/v1/student/buddy", headers=PRIYA).json()["conversations"] if c["id"] == r.json()["conversation_id"])
        assert conv["title"] == "Why did Two Sum fail?"
        assert client.post("/api/v1/student/buddy/explain-submission", headers=PRIYA, json={"problem_id": "prob_3sum"}).status_code in (200, 404)
        assert client.post("/api/v1/student/buddy/explain-submission", headers=PRIYA, json={"problem_id": "prob_nope"}).status_code == 404
    finally:
        with SessionLocal() as db:
            db.execute(delete(CodingSubmission).where(CodingSubmission.id == sid))
            db.commit()


def test_guards(cap):
    c = client.post("/api/v1/student/buddy/conversations", headers=PRIYA, json={}).json()
    assert client.post("/api/v1/student/buddy/ask", headers=OTHER, json={"question": "hi there", "conversation_id": c["id"]}).status_code == 404
    assert client.delete(f"/api/v1/student/buddy/conversations/{c['id']}", headers=OTHER).status_code == 404
    assert client.post("/api/v1/student/buddy/conversations", headers=RAMESH, json={}).status_code == 403
    assert client.post("/api/v1/student/buddy/conversations", headers=PRIYA, json={"course_id": "course_nope"}).status_code == 404
    assert client.post("/api/v1/student/buddy/conversations", headers=_h("usr_priya_01", "student", "col_other_999"), json={}).status_code == 404


def test_claude_adapter_puts_turn_context_in_a_mid_conversation_system_message():
    sent = {}

    def create(**kw):
        sent.update(kw)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Q1: what is a heap?")])
    stub = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    sb.ClaudeBuddyAdapter(client=stub, model="claude-opus-5-5").reply([], "Quiz me", None, "en", context="PRACTICE MODE: quiz")
    assert sent["messages"][-2:] == [{"role": "user", "content": "Quiz me"}, {"role": "system", "content": "PRACTICE MODE: quiz"}]
    assert "PRACTICE" not in sent["system"][0]["text"]                                  # the cached system prompt is unchanged
    sb.ClaudeBuddyAdapter(client=stub, model="claude-sonnet-5").reply([], "Quiz me", None, "en", context="PRACTICE MODE: quiz")
    assert sent["messages"] == [{"role": "user", "content": "[Tutor instructions: PRACTICE MODE: quiz]\nQuiz me"}]   # no mid-system support
