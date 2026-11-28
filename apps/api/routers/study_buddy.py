"""Screen 25 · AI Study Buddy (student). Spec: docs/screens/25-study-buddy.md

Phase 2: saved conversations (title, optional course context, tutor or practice mode), thumbs feedback on answers,
and "explain my last failed submission" from the coding lab."""
import datetime
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import PLATFORM_TENANT, TokenPayload, require_role
from core.tenant import get_student_for_user
from models.schema import BuddyConversation, CodingProblem, CodingSubmission, Course, Lesson, StudyBuddyMessage, TestAttempt, UsageLedger
from services.study_buddy import (HISTORY_TURNS, MIN_GAP_SECONDS, calls_since, daily_cap, day_start, get_adapter, redact,
                                  turn_context)

router = APIRouter(prefix="/student/buddy", tags=["Study Buddy"])
STUDENT = require_role(["student"])
TAMIL = re.compile(r"[஀-௿]")


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    topic: Optional[str] = Field(default=None, max_length=64, pattern=r"^[\w .:#&+-]*$")
    conversation_id: Optional[str] = Field(default=None, max_length=64)


class ConversationIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    course_id: Optional[str] = Field(default=None, max_length=64)
    mode: str = Field(default="tutor", pattern="^(tutor|practice)$")


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class FeedbackIn(BaseModel):
    value: Optional[str] = Field(default=None, pattern="^(up|down)$")


class ExplainIn(BaseModel):
    problem_id: str = Field(min_length=1, max_length=64)


def _test_in_progress(db: Session, student_id: str) -> bool:
    now = datetime.datetime.utcnow()
    return db.execute(select(TestAttempt.id).where(TestAttempt.student_id == student_id, TestAttempt.status == "in_progress",
                                                   TestAttempt.ends_at > now)).first() is not None


def _usage(db: Session, student) -> dict:
    cap = daily_cap(db, student.college_id)
    used = calls_since(db, student.id, day_start())
    return {"used_today": used, "daily_cap": cap, "left_today": max(0, cap - used)}


def _visible_courses(db: Session, student) -> list:
    from services.courses import visible_courses
    return visible_courses(db, student)


def _conv_out(c: BuddyConversation, course_titles: dict) -> dict:
    return {"id": c.id, "title": c.title, "mode": c.mode, "course_id": c.course_id, "course": course_titles.get(c.course_id),
            "updated_at": c.updated_at.isoformat() if c.updated_at else None}


def _my_conversation(db: Session, student, conversation_id: str) -> BuddyConversation:
    c = db.execute(select(BuddyConversation).where(BuddyConversation.id == conversation_id, BuddyConversation.student_id == student.id,
                                                   BuddyConversation.college_id == student.college_id)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return c


def _conversations(db: Session, student) -> list:
    rows = db.execute(select(BuddyConversation).where(BuddyConversation.student_id == student.id, BuddyConversation.college_id == student.college_id)
                      .order_by(BuddyConversation.updated_at.desc()).limit(50)).scalars().all()
    titles = {c.id: c.title_en for c in db.execute(select(Course).where(Course.id.in_([r.course_id for r in rows if r.course_id] or ["_"]))).scalars()}
    return [_conv_out(c, titles) for c in rows]


@router.get("")
def history(conversation_id: Optional[str] = None, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    """Messages of one conversation (or, without an id, the older chat from before conversations), the list of
    conversations and the courses a conversation can be about."""
    student = get_student_for_user(current_user, db)
    q = select(StudyBuddyMessage).where(StudyBuddyMessage.student_id == student.id, StudyBuddyMessage.college_id == student.college_id)
    if conversation_id:
        _my_conversation(db, student, conversation_id)
        q = q.where(StudyBuddyMessage.conversation_id == conversation_id)
    else:
        q = q.where(StudyBuddyMessage.conversation_id.is_(None))
    msgs = db.execute(q.order_by(StudyBuddyMessage.created_at.desc()).limit(50)).scalars().all()
    return {"messages": [{"id": m.id, "role": m.role, "content": m.content, "topic": m.topic, "feedback": m.feedback,
                          "at": m.created_at.isoformat() if m.created_at else None} for m in reversed(msgs)],
            "conversations": _conversations(db, student),
            "courses": [{"id": c.id, "title": c.title_en} for c in _visible_courses(db, student)],
            "usage": _usage(db, student), "locked": _test_in_progress(db, student.id)}


@router.post("/conversations", status_code=201)
def new_conversation(req: ConversationIn, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    course = None
    if req.course_id:
        course = next((c for c in _visible_courses(db, student) if c.id == req.course_id), None)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
    default = ("Practice: " if req.mode == "practice" else "") + (course.title_en if course else "New chat")
    c = _create_conversation(db, student, (req.title or "").strip() or default, course.id if course else None, req.mode)
    db.commit()
    return _conv_out(c, {course.id: course.title_en} if course else {})


def _create_conversation(db: Session, student, title: str, course_id: Optional[str], mode: str) -> BuddyConversation:
    now = datetime.datetime.utcnow()
    c = BuddyConversation(id=f"bc_{uuid.uuid4().hex[:16]}", college_id=student.college_id, student_id=student.id, title=title[:120],
                          course_id=course_id, mode=mode, created_at=now, updated_at=now)
    db.add(c)
    db.flush()
    return c


@router.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, req: RenameIn, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    c = _my_conversation(db, student, conversation_id)
    c.title = req.title.strip()
    db.commit()
    return {"id": c.id, "title": c.title}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    """The student's own chat: removed for good (usage counts stay; they are metering, not content)."""
    student = get_student_for_user(current_user, db)
    c = _my_conversation(db, student, conversation_id)
    n = db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.conversation_id == c.id)).rowcount
    db.delete(c)
    db.commit()
    return {"deleted": n}


@router.post("/messages/{message_id}/feedback")
def answer_feedback(message_id: str, req: FeedbackIn, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    m = db.execute(select(StudyBuddyMessage).where(StudyBuddyMessage.id == message_id, StudyBuddyMessage.student_id == student.id,
                                                   StudyBuddyMessage.role == "assistant")).scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    m.feedback = req.value
    db.commit()
    return {"id": m.id, "feedback": m.feedback}


@router.post("/ask")
def ask(req: AskIn, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    student = get_student_for_user(current_user, db)
    if req.conversation_id:
        conv = _my_conversation(db, student, req.conversation_id)
    else:
        conv = None
    return _ask(db, current_user, student, req.question, req.topic, conv)


@router.post("/explain-submission")
def explain_submission(req: ExplainIn, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    """From the coding lab: a new conversation that asks why my last failed submission failed. The question is built
    here from the submission (status, error, code) so the student does not have to paste anything."""
    student = get_student_for_user(current_user, db)
    prob = db.execute(select(CodingProblem).where(CodingProblem.id == req.problem_id, CodingProblem.college_id == student.college_id,
                                                  CodingProblem.status != "deleted")).scalar_one_or_none()
    if prob is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    sub = db.execute(select(CodingSubmission).where(CodingSubmission.problem_id == prob.id, CodingSubmission.student_id == student.id,
                                                    CodingSubmission.status != "Accepted")
                     .order_by(CodingSubmission.created_at.desc())).scalars().first()
    if sub is None:
        raise HTTPException(status_code=404, detail="No failed submission for this problem")
    code = (sub.code or "")[:3000]
    question = (f"My submission for \"{prob.title}\" ({sub.language}) got \"{sub.status}\": {sub.tests_passed} of {sub.tests_total} tests passed."
                + (f" Error: {sub.error_message[:300]}." if sub.error_message else "")
                + f" Here is my code:\n```{sub.language}\n{code}\n```\nWhat is wrong and what should I check? Give hints, not the full solution.")
    conv = _create_conversation(db, student, f"Why did {prob.title} fail?", None, "tutor")
    db.commit()
    return _ask(db, current_user, student, question, prob.topic[:64] if prob.topic else None, conv)


def _ask(db: Session, current_user: TokenPayload, student, raw_question: str, topic: Optional[str], conv: Optional[BuddyConversation]) -> dict:
    sid, college_id = student.id, student.college_id
    from services import consent as consent_svc
    if consent_svc.is_minor(student) and not consent_svc.allowed(db, student, "ai_hints"):
        # S16 DPDP: questions go to an AI service; a minor needs a parent's verifiable consent first
        raise HTTPException(status_code=403, detail=consent_svc.PARENTAL_REQUIRED["ai_hints"])
    if _test_in_progress(db, sid):
        raise HTTPException(status_code=409, detail={"reason": "test_in_progress", "message": "Study Buddy is paused while your practice test is running."})
    usage = _usage(db, student)
    if usage["left_today"] <= 0:
        raise HTTPException(status_code=429, detail={"reason": "quota", "message": f"You have used all {usage['daily_cap']} questions for today. It resets at midnight."})
    last_user = db.execute(select(StudyBuddyMessage).where(StudyBuddyMessage.student_id == sid, StudyBuddyMessage.role == "user")
                           .order_by(StudyBuddyMessage.created_at.desc())).scalars().first()
    if last_user and (datetime.datetime.utcnow() - last_user.created_at).total_seconds() < MIN_GAP_SECONDS:
        raise HTTPException(status_code=429, detail={"reason": "too_fast", "message": "One question at a time, please."})
    hq = select(StudyBuddyMessage).where(StudyBuddyMessage.student_id == sid)
    hq = hq.where(StudyBuddyMessage.conversation_id == conv.id) if conv else hq.where(StudyBuddyMessage.conversation_id.is_(None))
    recent = db.execute(hq.order_by(StudyBuddyMessage.created_at.desc()).limit(HISTORY_TURNS * 2)).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
    while history and history[0]["role"] != "user":          # the API needs the first turn to be the user's
        history.pop(0)

    context = None
    if conv and (conv.course_id or conv.mode == "practice"):
        course = db.execute(select(Course).where(Course.id == conv.course_id, Course.college_id == PLATFORM_TENANT)).scalar_one_or_none() if conv.course_id else None
        lessons = [l.title_en for l in db.execute(select(Lesson).where(Lesson.course_id == course.id).order_by(Lesson.position)).scalars()] if course else []
        context = turn_context(course.title_en if course else None, lessons, conv.mode)

    question = redact(raw_question.strip())
    lang = "ta" if TAMIL.search(question) else "en"
    adapter = get_adapter()
    conv_id = conv.id if conv else None
    first_in_conv = conv is not None and not recent
    db.rollback()                                             # end the read transaction: no external call inside one (rule 3)

    try:
        answer = adapter.reply(history, question, topic, lang, **({"context": context} if context else {})) or "…"
    except Exception:
        raise HTTPException(status_code=503, detail={"reason": "unavailable", "message": "Study Buddy is busy right now. Try again in a minute."})

    now = datetime.datetime.utcnow()
    db.add(StudyBuddyMessage(id=f"sb_{uuid.uuid4().hex[:18]}", college_id=college_id, student_id=sid, role="user", conversation_id=conv_id,
                             content=question, topic=topic, lang=lang, provider=adapter.name, created_at=now))
    answer_id = f"sb_{uuid.uuid4().hex[:18]}"
    db.add(StudyBuddyMessage(id=answer_id, college_id=college_id, student_id=sid, role="assistant", conversation_id=conv_id,
                             content=redact(answer), topic=topic, lang=lang, provider=adapter.name,
                             created_at=now + datetime.timedelta(milliseconds=1)))
    db.add(UsageLedger(id=f"ul_{uuid.uuid4().hex[:18]}", college_id=college_id, student_id=sid, kind="ai_calls", amount=1,
                       period=now.strftime("%Y-%m"), ref_type="study_buddy", ref_id=topic))      # L21
    if conv_id:
        values = {"updated_at": now}
        if first_in_conv and db.execute(select(BuddyConversation.title).where(BuddyConversation.id == conv_id)).scalar_one() == "New chat":
            values["title"] = (question[:57] + "…") if len(question) > 60 else question           # name a new chat after its first question
        db.execute(update(BuddyConversation).where(BuddyConversation.id == conv_id).values(**values))
    db.commit()
    student = get_student_for_user(current_user, db)
    return {"answer": redact(answer), "answer_id": answer_id, "lang": lang, "usage": _usage(db, student), "conversation_id": conv_id}


@router.delete("")
def clear(current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    """The student can delete all their chats (usage counts stay: they are metering, not content)."""
    student = get_student_for_user(current_user, db)
    n = db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.student_id == student.id,
                                                   StudyBuddyMessage.college_id == student.college_id)).rowcount
    db.execute(delete(BuddyConversation).where(BuddyConversation.student_id == student.id, BuddyConversation.college_id == student.college_id))
    db.commit()
    return {"deleted": n}
