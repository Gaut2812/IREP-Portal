"""Screen 25 · AI Study Buddy: hint-first tutor, redaction, daily cap, test lock, L21 counts.
The Claude adapter is tested with a stub client (no network). Spec: docs/screens/25-study-buddy.md"""
import datetime
import sys
import time
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
from models.schema import StudyBuddyMessage, TestAttempt, UsageLedger
import routers.study_buddy as sb_router
from services import study_buddy as sb

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer")


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(sb_router, "MIN_GAP_SECONDS", 0)
    db = SessionLocal()
    try:   # attempts other tests left running would lock Study Buddy
        for att in db.execute(select(TestAttempt).where(TestAttempt.student_id == "std_priya_01", TestAttempt.status == "in_progress")).scalars():
            att.status = "expired"
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.student_id == "std_priya_01"))
        db.execute(delete(UsageLedger).where(UsageLedger.student_id == "std_priya_01", UsageLedger.kind == "ai_calls"))
        db.execute(delete(TestAttempt).where(TestAttempt.id == "att_buddy_lock"))
        db.commit()
    finally:
        db.close()


class Capture(sb.BuddyAdapter):
    name = "capture"

    def __init__(self):
        self.calls = []

    def reply(self, history, question, topic, lang):
        self.calls.append((history, question, topic, lang))
        return "Try a hash set. Mail me at x@y.com"          # the answer is redacted too


def test_ask_answers_counts_and_keeps_history():
    r = client.post("/api/v1/student/buddy/ask", json={"question": "How do I find duplicates in a list?", "topic": "Hashing"}, headers=PRIYA)
    assert r.status_code == 200 and r.json()["answer"].startswith("Good question about Hashing")
    assert r.json()["usage"]["used_today"] == 1 and r.json()["usage"]["daily_cap"] == 30          # from the MoU
    ta = client.post("/api/v1/student/buddy/ask", json={"question": "லூப் என்றால் என்ன?"}, headers=PRIYA).json()
    assert ta["lang"] == "ta" and "உதாரண" in ta["answer"]
    hist = client.get("/api/v1/student/buddy", headers=PRIYA).json()
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant", "user", "assistant"] and hist["locked"] is False
    assert client.delete("/api/v1/student/buddy", headers=PRIYA).json()["deleted"] == 4
    assert client.get("/api/v1/student/buddy", headers=PRIYA).json()["usage"]["used_today"] == 2    # metering stays


def test_personal_details_never_reach_the_model(monkeypatch):
    cap = Capture()
    monkeypatch.setattr(sb_router, "get_adapter", lambda: cap)
    client.post("/api/v1/student/buddy/ask", json={"question": "First question about SQL joins"}, headers=PRIYA)
    r = client.post("/api/v1/student/buddy/ask", json={"question": "Call me on 98765 43210 or priya@demo.edu about joins"}, headers=PRIYA)
    history, question, _, _ = cap.calls[-1]
    assert "98765" not in question and "priya@demo.edu" not in question and "[phone removed]" in question and "[email removed]" in question
    assert history[0]["role"] == "user" and "Priya" not in str(cap.calls)
    assert "x@y.com" not in r.json()["answer"]
    db = SessionLocal()
    try:
        stored = " ".join(m.content for m in db.execute(select(StudyBuddyMessage).where(StudyBuddyMessage.student_id == "std_priya_01")).scalars())
    finally:
        db.close()
    assert "98765" not in stored and "@demo.edu" not in stored and "x@y.com" not in stored


def test_daily_cap_too_fast_and_test_lock(monkeypatch):
    monkeypatch.setattr(sb_router, "daily_cap", lambda db, college_id: 1)
    assert client.post("/api/v1/student/buddy/ask", json={"question": "What is recursion?"}, headers=PRIYA).status_code == 200
    r = client.post("/api/v1/student/buddy/ask", json={"question": "And memoisation?"}, headers=PRIYA)
    assert r.status_code == 429 and r.json()["detail"]["reason"] == "quota"
    monkeypatch.setattr(sb_router, "daily_cap", lambda db, college_id: 30)
    monkeypatch.setattr(sb_router, "MIN_GAP_SECONDS", 60)
    assert client.post("/api/v1/student/buddy/ask", json={"question": "And memoisation?"}, headers=PRIYA).json()["detail"]["reason"] == "too_fast"
    monkeypatch.setattr(sb_router, "MIN_GAP_SECONDS", 0)
    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        db.add(TestAttempt(id="att_buddy_lock", college_id="col_demo_001", test_id="test_service_aptitude", student_id="std_priya_01",
                           status="in_progress", started_at=now, ends_at=now + datetime.timedelta(minutes=20)))
        db.commit()
    finally:
        db.close()
    locked = client.post("/api/v1/student/buddy/ask", json={"question": "Answer to Q3?"}, headers=PRIYA)
    assert locked.status_code == 409 and locked.json()["detail"]["reason"] == "test_in_progress"
    assert client.get("/api/v1/student/buddy", headers=PRIYA).json()["locked"] is True


def test_roles():
    assert client.post("/api/v1/student/buddy/ask", json={"question": "hello there"}, headers=ARUN).status_code == 403
    assert client.post("/api/v1/student/buddy/ask", json={"question": "x"}, headers=PRIYA).status_code == 422


@pytest.mark.link("L21")
def test_trainers_see_counts_not_content():
    for q in ("What is a stack?", "What is a queue?"):
        client.post("/api/v1/student/buddy/ask", json={"question": q}, headers=PRIYA)
    dash = client.get("/api/v1/trainer/dashboard", headers=ARUN).json()["ai_usage"]
    priya = next(t for t in dash["top"] if t["student_id"] == "std_priya_01")
    assert priya["calls"] == 2 and dash["calls_7d"] >= 2
    assert "stack" not in str(dash).lower()
    flags = client.get("/api/v1/trainer/at-risk", headers=ARUN).json()["flags"]
    assert all("ai_calls_7d" in f for f in flags)


def test_claude_adapter_request_shape():
    sent = {}

    def create(**kw):
        sent.update(kw)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="thinking", thinking=""),
                                                                SimpleNamespace(type="text", text="Think about two pointers.")])
    stub = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    adapter = sb.ClaudeBuddyAdapter(client=stub, model="claude-opus-5-5")
    out = adapter.reply([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}], "Two sum?", "Arrays", "en")
    assert out == "Think about two pointers."
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in sent["betas"]
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"} and "complete solution" in sent["system"][0]["text"]
    assert sent["messages"][-1] == {"role": "user", "content": "(Topic: Arrays)\nTwo sum?"} and "thinking" not in sent

    def refuse(**kw):
        return SimpleNamespace(stop_reason="refusal", content=[])
    stub.beta.messages.create = refuse
    assert "can't help" in adapter.reply([], "x", None, "en")
