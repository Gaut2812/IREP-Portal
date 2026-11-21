"""Screen 22 · Assessments (trainer): problems and tests down to 24 and 23, results back (L13);
the IREP question and problem banks from 46 (L37). Spec: docs/screens/22-assessments.md"""
import datetime
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import PLATFORM_TENANT, TokenPayload, require_role
from core.tenant import get_trainer_batch_ids, get_trainer_for_user, get_user_name
from models.schema import (Batch, CodingProblem, CodingSubmission, PracticeQuestion, PracticeTest, Student, TestAttempt, TestCase,
                           User)
from services.audit import record_audit
from services.notifications import notify_user

router = APIRouter(tags=["Assessments"])
TRAINER = require_role(["trainer"])
STAFF = require_role(["irep_admin"])
KINDS = {"problem": CodingProblem, "test": PracticeTest}
DIFFICULTIES = ("Easy", "Medium", "Hard")
OPTIONS = ("A", "B", "C", "D")


class CaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    input_data: str = Field(max_length=20000)
    expected_output: str = Field(max_length=20000)
    is_hidden: bool = False


class ProblemIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    statement: str = Field(min_length=10, max_length=20000)
    constraints: str = Field(default="", max_length=4000)
    difficulty: str = "Medium"
    topic: str = Field(default="General", max_length=64)
    example_input: Optional[str] = None
    example_output: Optional[str] = None
    trainer_notes: Optional[str] = Field(default=None, max_length=4000)
    starter_code: str = Field(default="def solve():\n    pass\n", max_length=20000)
    cases: List[CaseIn] = Field(min_length=1, max_length=50)


class QuestionIn(BaseModel):
    question_text: str = Field(min_length=5, max_length=4000)
    option_a: str = Field(min_length=1, max_length=255)
    option_b: str = Field(min_length=1, max_length=255)
    option_c: str = Field(min_length=1, max_length=255)
    option_d: str = Field(min_length=1, max_length=255)
    correct_option: str
    section_name: str = Field(default="Quantitative", max_length=64)
    topic: str = Field(default="General", max_length=64)
    explanation: Optional[str] = Field(default=None, max_length=4000)


class TestIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    category: str = Field(default="Aptitude", max_length=128)
    duration_min: int = Field(default=30, ge=5, le=180)
    questions: List[QuestionIn] = Field(min_length=1, max_length=100)


class PublishIn(BaseModel):
    batch_ids: List[str] = Field(min_length=1)
    due_at: Optional[datetime.datetime] = None


class NotesIn(BaseModel):
    trainer_notes: Optional[str] = Field(default=None, max_length=4000)


# ------------------------------------------------------------------ builders (shared by 22 and the 46 bank)

def _new_problem(db: Session, college_id: str, req: ProblemIn, author: str, status_: str) -> CodingProblem:
    if req.difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=422, detail="difficulty must be Easy, Medium or Hard")
    if not any(not c.is_hidden for c in req.cases):
        raise HTTPException(status_code=422, detail="Add at least one visible sample case")
    pid = f"prob_{uuid.uuid4().hex[:16]}"
    p = CodingProblem(id=pid, college_id=college_id, slug=pid, title=req.title.strip(), difficulty=req.difficulty, topic=req.topic,
                      company_tags="", week_info="", statement=req.statement, example_input=req.example_input,
                      example_output=req.example_output, constraints=req.constraints, starter_code=req.starter_code,
                      starter_codes={"python": req.starter_code}, trainer_notes=req.trainer_notes, trainer_author=author,
                      status=status_, batch_ids=None if status_ == "published" else [],
                      published_at=datetime.datetime.utcnow() if status_ == "published" else None)
    db.add(p)
    db.flush()
    for i, c in enumerate(req.cases, start=1):
        db.add(TestCase(id=f"tc_{uuid.uuid4().hex[:16]}", college_id=college_id, problem_id=pid, test_order=i, is_hidden=c.is_hidden,
                        name=c.name, input_data=c.input_data, expected_output=c.expected_output))
    return p


def _new_test(db: Session, college_id: str, req: TestIn, status_: str) -> PracticeTest:
    for q in req.questions:
        if q.correct_option not in OPTIONS:
            raise HTTPException(status_code=422, detail="correct_option must be A, B, C or D")
    tid = f"test_{uuid.uuid4().hex[:16]}"
    sections = {}
    for q in req.questions:
        sections[q.section_name] = sections.get(q.section_name, 0) + 1
    t = PracticeTest(id=tid, college_id=college_id, title=req.title.strip(), category=req.category, duration_min=req.duration_min,
                     total_questions=len(req.questions), sections_json=sections, status=status_,
                     batch_ids=None if status_ == "published" else [],
                     published_at=datetime.datetime.utcnow() if status_ == "published" else None)
    db.add(t)
    db.flush()
    for i, q in enumerate(req.questions, start=1):
        db.add(PracticeQuestion(id=f"pq_{uuid.uuid4().hex[:16]}", college_id=college_id, test_id=tid, question_number=i, **q.model_dump()))
    return t


def _copy(db: Session, kind: str, src, college_id: str):
    """Import a bank item into a college as a draft (L37)."""
    if kind == "problem":
        p = CodingProblem(id=f"prob_{uuid.uuid4().hex[:16]}", college_id=college_id, status="draft", batch_ids=[], source_id=src.id,
                          **{k: getattr(src, k) for k in ("title", "difficulty", "topic", "company_tags", "week_info", "statement", "example_input",
                                                          "example_output", "constraints", "time_limit_ms", "memory_limit_mb", "starter_codes",
                                                          "starter_code", "trainer_notes", "trainer_author")})
        p.slug = p.id
        db.add(p)
        db.flush()
        for c in db.execute(select(TestCase).where(TestCase.problem_id == src.id).order_by(TestCase.test_order)).scalars():
            db.add(TestCase(id=f"tc_{uuid.uuid4().hex[:16]}", college_id=college_id, problem_id=p.id, test_order=c.test_order,
                            is_hidden=c.is_hidden, name=c.name, input_data=c.input_data, expected_output=c.expected_output, explanation=c.explanation))
        return p
    t = PracticeTest(id=f"test_{uuid.uuid4().hex[:16]}", college_id=college_id, status="draft", batch_ids=[], source_id=src.id,
                     **{k: getattr(src, k) for k in ("title", "category", "duration_min", "total_questions", "sections_json")})
    db.add(t)
    db.flush()
    for q in db.execute(select(PracticeQuestion).where(PracticeQuestion.test_id == src.id).order_by(PracticeQuestion.question_number)).scalars():
        db.add(PracticeQuestion(id=f"pq_{uuid.uuid4().hex[:16]}", college_id=college_id, test_id=t.id,
                                **{k: getattr(q, k) for k in ("question_number", "section_name", "topic", "question_text", "option_a", "option_b",
                                                              "option_c", "option_d", "correct_option", "explanation")}))
    return t


def _row(kind: str, item, batch_names: dict) -> dict:
    out = {"kind": kind, "id": item.id, "title": item.title, "status": item.status,
           "batch_ids": item.batch_ids, "batches": "all" if item.batch_ids is None else [batch_names.get(b, b) for b in item.batch_ids],
           "due_at": item.due_at.isoformat() if item.due_at else None, "source_id": item.source_id}
    if kind == "problem":
        out.update({"difficulty": item.difficulty, "topic": item.topic, "trainer_notes": item.trainer_notes})
    else:
        out.update({"category": item.category, "questions": item.total_questions, "duration_min": item.duration_min})
    return out


# ------------------------------------------------------------------ Screen 22 (trainer)

def _mine(db: Session, user: TokenPayload) -> List[str]:
    return get_trainer_batch_ids(get_trainer_for_user(user, db), db)


def _item(db: Session, kind: str, item_id: str, user: TokenPayload):
    model = KINDS.get(kind)
    if model is None:
        raise HTTPException(status_code=404, detail="Not found")
    item = db.execute(select(model).where(model.id == item_id, model.college_id == user.college_id)).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    return item


@router.get("/trainer/assessments")
def list_assessments(current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    mine = _mine(db, current_user)
    names = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id)).all())
    probs = db.execute(select(CodingProblem).where(CodingProblem.college_id == current_user.college_id).order_by(CodingProblem.title)).scalars().all()
    tests = db.execute(select(PracticeTest).where(PracticeTest.college_id == current_user.college_id).order_by(PracticeTest.title)).scalars().all()
    return {"batches": [{"id": b, "name": names.get(b, b)} for b in mine],
            "problems": [_row("problem", p, names) for p in probs], "tests": [_row("test", t, names) for t in tests]}


@router.post("/trainer/assessments/problems", status_code=status.HTTP_201_CREATED)
def create_problem(req: ProblemIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    p = _new_problem(db, current_user.college_id, req, get_user_name(db, current_user.sub, "Trainer"), "draft")
    record_audit(db, current_user, "assessment.created", "coding_problem", p.id, {"cases": len(req.cases)})
    db.commit()
    return _row("problem", p, {})


@router.post("/trainer/assessments/tests", status_code=status.HTTP_201_CREATED)
def create_test(req: TestIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    t = _new_test(db, current_user.college_id, req, "draft")
    record_audit(db, current_user, "assessment.created", "practice_test", t.id, {"questions": len(req.questions)})
    db.commit()
    return _row("test", t, {})


@router.put("/trainer/assessments/problem/{item_id}/notes")
def set_notes(item_id: str, req: NotesIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """Trainer notes travel down to 24 with the problem (L13)."""
    p = _item(db, "problem", item_id, current_user)
    p.trainer_notes = (req.trainer_notes or "").strip() or None
    p.trainer_author = get_user_name(db, current_user.sub, p.trainer_author)
    db.commit()
    return _row("problem", p, {})


@router.post("/trainer/assessments/{kind}/{item_id}/publish")
def publish(kind: str, item_id: str, req: PublishIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    item = _item(db, kind, item_id, current_user)
    mine = set(_mine(db, current_user))
    chosen = set(req.batch_ids)
    if not chosen <= mine:
        raise HTTPException(status_code=403, detail="You can publish only to your own batches")
    if req.due_at and req.due_at <= datetime.datetime.now():
        raise HTTPException(status_code=422, detail="The due date must be in the future")
    if item.status == "published" and item.batch_ids is None:
        new_targets = set()                                    # already open to every batch
    else:
        current = set(item.batch_ids or []) if item.status == "published" else set()
        new_targets = chosen - current
        item.batch_ids = sorted(current | chosen)
    item.status = "published"
    item.published_at = item.published_at or datetime.datetime.utcnow()
    if req.due_at:
        item.due_at = req.due_at
    students = db.execute(select(Student.user_id).where(Student.college_id == current_user.college_id,
                                                         Student.batch_id.in_(sorted(new_targets) or ["_"]))).scalars().all()
    link = f"/student/coding/{item.id}" if kind == "problem" else f"/student/tests/{item.id}"
    due = f" · due {item.due_at.strftime('%d %b %H:%M')}" if item.due_at else ""
    for uid in students:
        if uid:
            notify_user(db, uid, f"New {'coding problem' if kind == 'problem' else 'practice test'}: {item.title}", f"From your trainer{due}",
                        title_ta=f"புதிய {'கோடிங் கணக்கு' if kind == 'problem' else 'பயிற்சித் தேர்வு'}: {item.title}",
                        kind="assessment", link=link, college_id=current_user.college_id)
    record_audit(db, current_user, "assessment.published", kind, item.id, {"batches": sorted(chosen), "notified": len(students)})
    db.commit()
    names = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id)).all())
    return {**_row(kind, item, names), "notified": len(students)}


@router.post("/trainer/assessments/{kind}/{item_id}/unpublish")
def unpublish(kind: str, item_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """Withdraw from my batches only; other trainers' batches keep it."""
    item = _item(db, kind, item_id, current_user)
    mine = set(_mine(db, current_user))
    current = set(item.batch_ids or []) if item.batch_ids is not None else set(
        db.execute(select(Batch.id).where(Batch.college_id == current_user.college_id)).scalars())
    left = sorted(current - mine)
    item.batch_ids = left
    if not left:
        item.status = "draft"
    record_audit(db, current_user, "assessment.unpublished", kind, item.id, {"batches_left": len(left)})
    db.commit()
    names = dict(db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id)).all())
    return _row(kind, item, names)


@router.get("/trainer/assessments/{kind}/{item_id}/results")
def results(kind: str, item_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """L13 results back: the trainer's students that the item reaches."""
    item = _item(db, kind, item_id, current_user)
    mine = _mine(db, current_user)
    reach = mine if item.batch_ids is None else [b for b in mine if b in item.batch_ids]
    rows = db.execute(select(Student, User.name).join(User, User.id == Student.user_id)
                      .where(Student.college_id == current_user.college_id, Student.batch_id.in_(reach or ["_"]))
                      .order_by(User.name)).all()
    ids = [s.id for s, _ in rows]
    out = []
    if kind == "problem":
        subs = db.execute(select(CodingSubmission).where(CodingSubmission.problem_id == item.id, CodingSubmission.student_id.in_(ids or ["_"]))
                          .order_by(CodingSubmission.created_at)).scalars().all()
        by = {}
        for s in subs:
            by.setdefault(s.student_id, []).append(s)
        for st, name in rows:
            mine_subs = by.get(st.id, [])
            best = max(mine_subs, key=lambda s: (s.status == "Accepted", s.tests_passed), default=None)
            out.append({"student_id": st.id, "name": name, "batch": st.batch_name, "attempts": len(mine_subs),
                        "result": best.status if best else None, "score": f"{best.tests_passed}/{best.tests_total}" if best else None,
                        "done": bool(best and best.status == "Accepted")})
    else:
        atts = db.execute(select(TestAttempt).where(TestAttempt.test_id == item.id, TestAttempt.student_id.in_(ids or ["_"]),
                                                    TestAttempt.status == "submitted")).scalars().all()
        by = {}
        for a in atts:
            by.setdefault(a.student_id, []).append(a)
        for st, name in rows:
            mine_atts = by.get(st.id, [])
            best = max(mine_atts, key=lambda a: a.score or 0, default=None)
            out.append({"student_id": st.id, "name": name, "batch": st.batch_name, "attempts": len(mine_atts),
                        "result": f"{round(best.accuracy_pct or 0)}%" if best else None,
                        "score": f"{best.score}/{best.total_questions}" if best else None, "done": bool(best)})
    done = sum(1 for r in out if r["done"])
    return {"item": _row(kind, item, {}), "students": out,
            "summary": {"students": len(out), "attempted": sum(1 for r in out if r["attempts"]), "done": done}}


# ------------------------------------------------------------------ L37: the IREP bank (platform tenant)

def _bank_rows() -> tuple:
    return (select(CodingProblem).where(CodingProblem.college_id == PLATFORM_TENANT, CodingProblem.status == "published").order_by(CodingProblem.title),
            select(PracticeTest).where(PracticeTest.college_id == PLATFORM_TENANT, PracticeTest.status == "published").order_by(PracticeTest.title))


@router.get("/trainer/bank")
def bank_for_trainer(current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    qp, qt = _bank_rows()
    imported = {s for s in db.execute(select(CodingProblem.source_id).where(CodingProblem.college_id == current_user.college_id)).scalars() if s}
    imported |= {s for s in db.execute(select(PracticeTest.source_id).where(PracticeTest.college_id == current_user.college_id)).scalars() if s}
    return {"problems": [{**_row("problem", p, {}), "imported": p.id in imported} for p in db.execute(qp).scalars()],
            "tests": [{**_row("test", t, {}), "imported": t.id in imported} for t in db.execute(qt).scalars()]}


@router.post("/trainer/bank/{kind}/{bank_id}/import", status_code=status.HTTP_201_CREATED)
def import_from_bank(kind: str, bank_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    model = KINDS.get(kind)
    src = db.execute(select(model).where(model.id == bank_id, model.college_id == PLATFORM_TENANT, model.status == "published")).scalar_one_or_none() if model else None
    if src is None:
        raise HTTPException(status_code=404, detail="Bank item not found")
    existing = db.execute(select(model).where(model.college_id == current_user.college_id, model.source_id == src.id)).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Already imported as {existing.id}")
    item = _copy(db, kind, src, current_user.college_id)
    record_audit(db, current_user, "assessment.imported", kind, item.id, {"from": src.id})
    db.commit()
    return _row(kind, item, {})


@router.get("/admin/content/bank")
def bank_for_staff(current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    qp, qt = _bank_rows()
    used = dict(db.execute(select(CodingProblem.source_id, func.count(CodingProblem.id)).where(CodingProblem.source_id.is_not(None))
                           .group_by(CodingProblem.source_id)).all())
    used.update(dict(db.execute(select(PracticeTest.source_id, func.count(PracticeTest.id)).where(PracticeTest.source_id.is_not(None))
                                .group_by(PracticeTest.source_id)).all()))
    return {"problems": [{**_row("problem", p, {}), "imports": used.get(p.id, 0)} for p in db.execute(qp).scalars()],
            "tests": [{**_row("test", t, {}), "imports": used.get(t.id, 0)} for t in db.execute(qt).scalars()]}


@router.post("/admin/content/bank/problems", status_code=status.HTTP_201_CREATED)
def bank_add_problem(req: ProblemIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    p = _new_problem(db, PLATFORM_TENANT, req, "IREP", "published")
    record_audit(db, current_user, "bank.problem_added", "coding_problem", p.id, {"cases": len(req.cases)})
    db.commit()
    return _row("problem", p, {})


@router.post("/admin/content/bank/tests", status_code=status.HTTP_201_CREATED)
def bank_add_test(req: TestIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    t = _new_test(db, PLATFORM_TENANT, req, "published")
    record_audit(db, current_user, "bank.test_added", "practice_test", t.id, {"questions": len(req.questions)})
    db.commit()
    return _row("test", t, {})


# ------------------------------------------------------------------ Screen 23 list (student)

@router.get("/student/tests")
def student_tests(current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    """Practice tests published to the student's batch (L13), with the best submitted attempt."""
    from services.assessments import caller_student, visible_to
    me = caller_student(db, current_user)
    tests = [t for t in db.execute(select(PracticeTest).where(PracticeTest.college_id == current_user.college_id)
                                   .order_by(PracticeTest.title)).scalars() if visible_to(t, me)]
    best = {}
    if me is not None:
        for a in db.execute(select(TestAttempt).where(TestAttempt.student_id == me.id, TestAttempt.status == "submitted",
                                                      TestAttempt.test_id.in_([t.id for t in tests] or ["_"]))).scalars():
            if a.test_id not in best or (a.score or 0) > (best[a.test_id].score or 0):
                best[a.test_id] = a
    return {"tests": [{"id": t.id, "title": t.title, "category": t.category, "questions": t.total_questions,
                       "duration_min": t.duration_min, "due_at": t.due_at.isoformat() if t.due_at else None,
                       "best_score": f"{best[t.id].score}/{best[t.id].total_questions}" if t.id in best else None}
                      for t in tests]}
