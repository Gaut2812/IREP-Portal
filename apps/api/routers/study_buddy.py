"""Screen 25 · AI Study Buddy (student). Spec: docs/screens/25-study-buddy.md"""
import datetime
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_student_for_user
from models.schema import StudyBuddyMessage, TestAttempt, UsageLedger
from services.study_buddy import HISTORY_TURNS, MIN_GAP_SECONDS, calls_since, daily_cap, day_start, get_adapter, redact

router = APIRouter(prefix="/student/buddy", tags=["Study Buddy"])
STUDENT = require_role(["student"])
TAMIL = re.compile(r"[஀-௿]")


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    topic: Optional[str] = Field(default=None, max_length=64, pattern=r"^[\w .:#&+-]*$")


def _test_in_progress(db: Session, student_id: str) -> bool:
    now = datetime.datetime.utcnow()
    return db.execute(select(TestAttempt.id).where(TestAttempt.student_id == student_id, TestAttempt.status == "in_progress",
                                                   TestAttempt.ends_at > now)).first() is not None


def _usage(db: Session, student) -> dict:
    cap = daily_cap(db, student.college_id)
    used = calls_since(db, student.id, day_start())
    return {"used_today": used, "daily_cap": cap, "left_today": max(0, cap - used)}


@router.get("")
def history(current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    msgs = db.execute(select(StudyBuddyMessage).where(StudyBuddyMessage.student_id == student.id,
                                                      StudyBuddyMessage.college_id == student.college_id)
                      .order_by(StudyBuddyMessage.created_at.desc()).limit(50)).scalars().all()
    return {"messages": [{"id": m.id, "role": m.role, "content": m.content, "topic": m.topic,
                          "at": m.created_at.isoformat() if m.created_at else None} for m in reversed(msgs)],
            "usage": _usage(db, student), "locked": _test_in_progress(db, student.id)}


@router.post("/ask")
def ask(req: AskIn, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    sid, college_id = student.id, student.college_id
    if _test_in_progress(db, sid):
        raise HTTPException(status_code=409, detail={"reason": "test_in_progress", "message": "Study Buddy is paused while your practice test is running."})
    usage = _usage(db, student)
    if usage["left_today"] <= 0:
        raise HTTPException(status_code=429, detail={"reason": "quota", "message": f"You have used all {usage['daily_cap']} questions for today. It resets at midnight."})
    recent = db.execute(select(StudyBuddyMessage).where(StudyBuddyMessage.student_id == sid)
                        .order_by(StudyBuddyMessage.created_at.desc()).limit(HISTORY_TURNS * 2)).scalars().all()
    last_user = next((m for m in recent if m.role == "user"), None)
    if last_user and (datetime.datetime.utcnow() - last_user.created_at).total_seconds() < MIN_GAP_SECONDS:
        raise HTTPException(status_code=429, detail={"reason": "too_fast", "message": "One question at a time, please."})
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
    while history and history[0]["role"] != "user":          # the API needs the first turn to be the user's
        history.pop(0)
    question = redact(req.question.strip())
    lang = "ta" if TAMIL.search(question) else "en"
    adapter = get_adapter()
    db.rollback()                                             # end the read transaction: no external call inside one (rule 3)

    try:
        answer = adapter.reply(history, question, req.topic, lang) or "…"
    except Exception:
        raise HTTPException(status_code=503, detail={"reason": "unavailable", "message": "Study Buddy is busy right now. Try again in a minute."})

    now = datetime.datetime.utcnow()
    db.add(StudyBuddyMessage(id=f"sb_{uuid.uuid4().hex[:18]}", college_id=college_id, student_id=sid, role="user",
                             content=question, topic=req.topic, lang=lang, provider=adapter.name, created_at=now))
    db.add(StudyBuddyMessage(id=f"sb_{uuid.uuid4().hex[:18]}", college_id=college_id, student_id=sid, role="assistant",
                             content=redact(answer), topic=req.topic, lang=lang, provider=adapter.name,
                             created_at=now + datetime.timedelta(milliseconds=1)))
    db.add(UsageLedger(id=f"ul_{uuid.uuid4().hex[:18]}", college_id=college_id, student_id=sid, kind="ai_calls", amount=1,
                       period=now.strftime("%Y-%m"), ref_type="study_buddy", ref_id=req.topic))      # L21
    db.commit()
    student = get_student_for_user(current_user, db)
    return {"answer": redact(answer), "lang": lang, "usage": _usage(db, student)}


@router.delete("")
def clear(current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    """The student can delete their own chat (usage counts stay: they are metering, not content)."""
    student = get_student_for_user(current_user, db)
    n = db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.student_id == student.id,
                                                   StudyBuddyMessage.college_id == student.college_id)).rowcount
    db.commit()
    return {"deleted": n}
