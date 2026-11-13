from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import datetime
import uuid

from core.database import get_db
from core.security import get_current_user, TokenPayload, require_role
from models.schema import (
    Student, CodingProblem, CodingSubmission, PracticeTest,
    PracticeQuestion, VirtualLabItem, SprintTask, MockInterview,
    SessionItem, DiscussionGroup, GroupMessage,
    TestAttempt, AttemptAnswer, ProctorEvent, TopicScore
)

router = APIRouter(prefix="/student", tags=["Student Screens"])

# --- SCREEN 12: Student Dashboard (PDF 2) ---
@router.get("/dashboard")
def get_student_dashboard(
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.execute(select(Student).filter_by(college_id=current_user.college_id)).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
        
    return {
        "student": {
            "name": current_user.name or "Priya R",
            "greeting": "Good morning, Priya 👋",
            "semester": student.semester,
            "branch": student.branch,
            "batch": student.batch_name,
            "readiness_score": student.readiness_score,
            "readiness_band": student.readiness_band,
            "readiness_delta": student.readiness_delta,
            "problems_solved": student.problems_solved,
            "problems_delta": 34,
            "attendance_pct": student.attendance_pct,
            "attendance_target": 85,
            "streak_days": student.streak_days,
            "streak_best": 27
        },
        "skill_progress": [
            {"skill": "DSA patterns", "percentage": 78, "color": "teal"},
            {"skill": "Aptitude & reasoning", "percentage": 71, "color": "blue"},
            {"skill": "Cloud & DevOps", "percentage": 64, "color": "purple"},
            {"skill": "AI & Data Science track", "percentage": 82, "color": "teal"},
            {"skill": "Future Skills: AI engineering", "percentage": 58, "color": "orange"},
            {"skill": "Communication", "percentage": 69, "color": "blue"}
        ],
        "this_week": [
            {"day": "Mon", "topic": "DSA: Pattern drill – Union-Find", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Tue", "topic": "Track: Model evaluation lab", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Wed", "topic": "Aptitude: Data interpretation", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Thu", "topic": "Future Skills: LLM APIs & RAG", "duration": "1 hr", "type": "Live", "color": "teal"},
            {"day": "Fri", "topic": "GD + weekly quiz", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Sat", "topic": "Track project kick-off + RAG mini-lab", "duration": "3 hrs", "type": "In-lab / Hybrid", "color": "purple"}
        ],
        "current_project": {
            "title": "Crop Price Predictor",
            "subtitle": "End-to-end ML · Team of 3 · Due Week 12",
            "progress_pct": 45,
            "open_tasks": 3
        },
        "upcoming_events": [
            {"title": "Mid-term DSA test", "date": "Sat"},
            {"title": "Mock interview", "date": "Wed 4:00 PM"},
            {"title": "AWS Cloud Practitioner", "date": "Nov 22"}
        ],
        "badges": [
            {"name": "Cloud Deployer", "description": "Deployed first app on cloud", "icon": "cloud", "earned_date": "Recently"},
            {"name": "DSA Master", "description": "100+ patterns solved", "icon": "code", "earned_date": "Oct 2"},
            {"name": "Consistent 15", "description": "15-day study streak", "icon": "flame", "earned_date": "Sep 28"},
            {"name": "Team Lead", "description": "Sprint 1 shipped", "icon": "users", "earned_date": "Sep 20"}
        ]
    }

# --- SCREEN 24: Coding Lab (PDF 3) ---
class CodeRunRequest(BaseModel):
    code: str
    language: str = "python"

class CodeSubmitRequest(BaseModel):
    code: str
    language: str = "python"

@router.get("/coding/{problem_id}")
def get_coding_problem(problem_id: str, db: Session = Depends(get_db)):
    prob = db.execute(select(CodingProblem).filter_by(id=problem_id)).scalar_one_or_none()
    if not prob:
        # Default to connected components problem
        prob = db.execute(select(CodingProblem)).first()[0]
        
    return {
        "id": prob.id,
        "title": prob.title,
        "difficulty": prob.difficulty,
        "topic": prob.topic,
        "company_tags": prob.company_tags,
        "week_info": prob.week_info,
        "statement": prob.statement,
        "example_input": prob.example_input,
        "example_output": prob.example_output,
        "constraints": prob.constraints,
        "starter_code": prob.starter_code,
        "trainer_notes": prob.trainer_notes,
        "trainer_author": prob.trainer_author,
        "ai_reviewer": {
            "tag": "Future Skills",
            "hints": [
                {"type": "good", "text": "Good: path compression keeps find() fast.", "color": "blue"},
                {"type": "try_next", "text": "Try next: add union by rank. Can you explain why it helps worst-case time?", "color": "amber"},
                {"type": "interview_tip", "text": "Interview tip: state the complexity aloud: near O(E · α(n)).", "color": "blue"}
            ],
            "hints_used": 1,
            "rules_note": "Hints only, no full solutions. AI help used in this problem: 1 hint"
        }
    }

@router.post("/coding/{problem_id}/run")
def run_code_sample(problem_id: str, req: CodeRunRequest):
    # Safe sandboxed simulation (adapter for Judge0)
    return {
        "status": "Passed",
        "runtime_ms": 42,
        "memory_mb": 16.1,
        "cases": [
            {"name": "Sample case 1", "status": "Passed", "time_ms": 12},
            {"name": "Sample case 2", "status": "Passed", "time_ms": 14}
        ]
    }

@router.post("/coding/{problem_id}/submit")
def submit_code(problem_id: str, req: CodeSubmitRequest, db: Session = Depends(get_db)):
    return {
        "status": "Accepted",
        "runtime_ms": 42,
        "memory_mb": 16.1,
        "tests_passed": 18,
        "tests_total": 18,
        "cases": [
            {"name": "Sample case 1", "status": "Passed"},
            {"name": "Sample case 2", "status": "Passed"},
            {"name": "Edge: no edges", "status": "Passed"},
            {"name": "Large graph (n=2000)", "status": "Passed"}
        ],
        "message": "18 / 18 hidden tests passed"
    }

# --- SCREEN 23: Practice Tests (PDF 4, Sprint 9) ---

class BatchAnswersRequest(BaseModel):
    answers: dict # { "12": "B", ... } or { "12": {"selected_option": "B", "is_marked_for_review": False} }
    marked_for_review: Optional[List[int]] = None

class ProctorEventRequest(BaseModel):
    event_type: str # tab_switch, fullscreen_exit, copy_paste_attempt
    details: Optional[str] = None

class SubmitTestRequest(BaseModel):
    answers: Optional[dict] = None
    marked_for_review: Optional[List[int]] = None

def _get_student_for_user(current_user: TokenPayload, db: Session) -> Student:
    student = db.execute(select(Student).filter_by(user_id=current_user.sub, college_id=current_user.college_id)).scalar_one_or_none()
    if not student:
        student = db.execute(select(Student).filter_by(college_id=current_user.college_id)).scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found for this tenant")
    return student

@router.get("/tests/{test_id}")
def get_practice_test(
    test_id: str,
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not isinstance(current_user, TokenPayload):
        current_user = TokenPayload(
            sub="usr_priya_01",
            role="student",
            college_id="col_demo_001",
            name="Priya R"
        )
    
    # Tenant-scoped test lookup
    test = db.execute(
        select(PracticeTest).filter_by(id=test_id, college_id=current_user.college_id)
    ).scalar_one_or_none()
    
    if not test:
        test = db.execute(select(PracticeTest).filter_by(id=test_id)).scalar_one_or_none()
    if not test:
        test = db.execute(select(PracticeTest).filter_by(college_id=current_user.college_id)).scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Practice test not found")

    questions = db.execute(
        select(PracticeQuestion)
        .filter_by(test_id=test.id)
        .order_by(PracticeQuestion.question_number)
    ).scalars().all()

    student = _get_student_for_user(current_user, db)
    active_attempt = db.execute(
        select(TestAttempt)
        .filter_by(test_id=test.id, student_id=student.id, status="in_progress")
        .order_by(TestAttempt.started_at.desc())
    ).scalars().first()

    answers_map = {}
    marked_review_list = []
    time_remaining_sec = test.duration_min * 60

    if active_attempt:
        now = datetime.datetime.utcnow()
        if now < active_attempt.ends_at:
            time_remaining_sec = max(0, int((active_attempt.ends_at - now).total_seconds()))
        else:
            time_remaining_sec = 0

        existing_answers = db.execute(
            select(AttemptAnswer).filter_by(attempt_id=active_attempt.id)
        ).scalars().all()

        for ans in existing_answers:
            if ans.selected_option:
                answers_map[ans.question_number] = ans.selected_option
            if ans.is_marked_for_review:
                marked_review_list.append(ans.question_number)

    # Section progress summary
    section_stats = {}
    for q in questions:
        sec = q.section_name or "General"
        if sec not in section_stats:
            section_stats[sec] = {"answered": 0, "total": 0}
        section_stats[sec]["total"] += 1
        if q.question_number in answers_map:
            section_stats[sec]["answered"] += 1

    sections_list = [
        {"name": sec, "answered": stats["answered"], "total": stats["total"]}
        for sec, stats in section_stats.items()
    ]

    return {
        "id": test.id,
        "title": test.title,
        "category": test.category,
        "duration_min": test.duration_min,
        "time_remaining_sec": time_remaining_sec,
        "total_questions": test.total_questions,
        "attempt_id": active_attempt.id if active_attempt else None,
        "sections": sections_list,
        "saved_answers": answers_map,
        "marked_for_review": marked_review_list,
        # Omit correct_option and explanation to prevent cheating while in-progress
        "questions": [
            {
                "id": q.id,
                "number": q.question_number,
                "section": q.section_name,
                "topic": q.topic,
                "text": q.question_text,
                "options": {
                    "A": q.option_a,
                    "B": q.option_b,
                    "C": q.option_c,
                    "D": q.option_d
                },
                "selected_option": answers_map.get(q.question_number),
                "is_marked_for_review": q.question_number in marked_review_list
            }
            for q in questions
        ]
    }

@router.post("/tests/{test_id}/attempts")
def start_or_resume_attempt(
    test_id: str,
    current_user: TokenPayload = Depends(require_role(["student", "super_admin"])),
    db: Session = Depends(get_db)
):
    student = _get_student_for_user(current_user, db)
    test = db.execute(select(PracticeTest).filter_by(id=test_id)).scalar_one_or_none()
    if not test:
        test = db.execute(select(PracticeTest)).first()[0]

    now = datetime.datetime.utcnow()

    active_attempt = db.execute(
        select(TestAttempt)
        .filter_by(test_id=test.id, student_id=student.id, status="in_progress")
        .order_by(TestAttempt.started_at.desc())
    ).scalars().first()

    if active_attempt and active_attempt.ends_at > now:
        answers = db.execute(select(AttemptAnswer).filter_by(attempt_id=active_attempt.id)).scalars().all()
        answers_dict = {a.question_number: a.selected_option for a in answers if a.selected_option}
        marked_list = [a.question_number for a in answers if a.is_marked_for_review]
        time_rem = max(0, int((active_attempt.ends_at - now).total_seconds()))

        return {
            "attempt_id": active_attempt.id,
            "status": "in_progress",
            "resumed": True,
            "started_at": active_attempt.started_at.isoformat(),
            "ends_at": active_attempt.ends_at.isoformat(),
            "time_remaining_sec": time_rem,
            "saved_answers": answers_dict,
            "marked_for_review": marked_list
        }

    attempt_id = f"att_{uuid.uuid4().hex[:12]}"
    ends_at = now + datetime.timedelta(minutes=test.duration_min)

    new_attempt = TestAttempt(
        id=attempt_id,
        college_id=current_user.college_id,
        test_id=test.id,
        student_id=student.id,
        status="in_progress",
        started_at=now,
        ends_at=ends_at,
        total_questions=test.total_questions
    )
    db.add(new_attempt)
    db.commit()

    return {
        "attempt_id": new_attempt.id,
        "status": "in_progress",
        "resumed": False,
        "started_at": new_attempt.started_at.isoformat(),
        "ends_at": new_attempt.ends_at.isoformat(),
        "time_remaining_sec": test.duration_min * 60,
        "saved_answers": {},
        "marked_for_review": []
    }

@router.put("/tests/attempts/{attempt_id}/answers")
def batch_save_answers(
    attempt_id: str,
    req: BatchAnswersRequest,
    current_user: TokenPayload = Depends(require_role(["student", "super_admin"])),
    db: Session = Depends(get_db)
):
    student = _get_student_for_user(current_user, db)
    attempt = db.execute(
        select(TestAttempt).filter_by(id=attempt_id, student_id=student.id, college_id=current_user.college_id)
    ).scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Cannot save answers: test is already submitted or expired")

    now = datetime.datetime.utcnow()
    if now > attempt.ends_at:
        attempt.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Test time has expired")

    questions = db.execute(select(PracticeQuestion).filter_by(test_id=attempt.test_id)).scalars().all()
    q_by_num = {q.question_number: q for q in questions}

    existing_answers = {
        a.question_number: a
        for a in db.execute(select(AttemptAnswer).filter_by(attempt_id=attempt.id)).scalars().all()
    }

    marked_set = set(req.marked_for_review or [])

    for q_num_raw, val in req.answers.items():
        q_num = int(q_num_raw)
        q = q_by_num.get(q_num)
        if not q:
            continue

        selected_opt = None
        is_review = q_num in marked_set

        if isinstance(val, dict):
            selected_opt = val.get("selected_option")
            if "is_marked_for_review" in val:
                is_review = val["is_marked_for_review"]
        elif isinstance(val, str):
            selected_opt = val

        if q_num in existing_answers:
            ans = existing_answers[q_num]
            ans.selected_option = selected_opt
            ans.is_marked_for_review = is_review
            ans.saved_at = now
        else:
            ans = AttemptAnswer(
                id=f"ans_{uuid.uuid4().hex[:12]}",
                college_id=current_user.college_id,
                attempt_id=attempt.id,
                question_id=q.id,
                question_number=q_num,
                selected_option=selected_opt,
                is_marked_for_review=is_review,
                saved_at=now
            )
            db.add(ans)

    db.commit()
    return {"success": True, "saved_count": len(req.answers)}

@router.post("/tests/attempts/{attempt_id}/proctor-events")
def log_proctor_event(
    attempt_id: str,
    req: ProctorEventRequest,
    current_user: TokenPayload = Depends(require_role(["student", "super_admin"])),
    db: Session = Depends(get_db)
):
    student = _get_student_for_user(current_user, db)
    attempt = db.execute(
        select(TestAttempt).filter_by(id=attempt_id, student_id=student.id, college_id=current_user.college_id)
    ).scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")

    event = ProctorEvent(
        id=f"proc_{uuid.uuid4().hex[:12]}",
        college_id=current_user.college_id,
        attempt_id=attempt.id,
        student_id=student.id,
        event_type=req.event_type,
        details=req.details,
        timestamp=datetime.datetime.utcnow()
    )
    db.add(event)
    db.commit()

    return {"success": True, "event_id": event.id}

@router.post("/tests/attempts/{attempt_id}/submit")
def submit_practice_test(
    attempt_id: str,
    req: Optional[SubmitTestRequest] = None,
    current_user: TokenPayload = Depends(require_role(["student", "super_admin"])),
    db: Session = Depends(get_db)
):
    student = _get_student_for_user(current_user, db)
    attempt = db.execute(
        select(TestAttempt).filter_by(id=attempt_id, student_id=student.id, college_id=current_user.college_id)
    ).scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")

    questions = db.execute(
        select(PracticeQuestion)
        .filter_by(test_id=attempt.test_id)
        .order_by(PracticeQuestion.question_number)
    ).scalars().all()

    now = datetime.datetime.utcnow()

    # Save any final answers if provided
    if req and req.answers:
        marked_set = set(req.marked_for_review or [])
        existing_answers = {
            a.question_number: a
            for a in db.execute(select(AttemptAnswer).filter_by(attempt_id=attempt.id)).scalars().all()
        }
        q_by_num = {q.question_number: q for q in questions}

        for q_num_raw, val in req.answers.items():
            q_num = int(q_num_raw)
            q = q_by_num.get(q_num)
            if not q:
                continue

            selected_opt = None
            is_review = q_num in marked_set
            if isinstance(val, dict):
                selected_opt = val.get("selected_option")
                if "is_marked_for_review" in val:
                    is_review = val["is_marked_for_review"]
            elif isinstance(val, str):
                selected_opt = val

            if q_num in existing_answers:
                ans = existing_answers[q_num]
                ans.selected_option = selected_opt
                ans.is_marked_for_review = is_review
                ans.saved_at = now
            else:
                ans = AttemptAnswer(
                    id=f"ans_{uuid.uuid4().hex[:12]}",
                    college_id=current_user.college_id,
                    attempt_id=attempt.id,
                    question_id=q.id,
                    question_number=q_num,
                    selected_option=selected_opt,
                    is_marked_for_review=is_review,
                    saved_at=now
                )
                db.add(ans)
        db.flush()

    answers = db.execute(select(AttemptAnswer).filter_by(attempt_id=attempt.id)).scalars().all()
    ans_by_num = {a.question_number: a for a in answers}

    total_score = 0
    section_scores = {}
    topic_scores_map = {}

    for q in questions:
        sec = q.section_name or "General"
        top = q.topic or "General"

        if sec not in section_scores:
            section_scores[sec] = {"score": 0, "total": 0}
        section_scores[sec]["total"] += 1

        top_key = (sec, top)
        if top_key not in topic_scores_map:
            topic_scores_map[top_key] = {"score": 0, "total": 0}
        topic_scores_map[top_key]["total"] += 1

        ans = ans_by_num.get(q.question_number)
        is_correct = False
        if ans and ans.selected_option and ans.selected_option.upper() == q.correct_option.upper():
            is_correct = True
            total_score += 1
            section_scores[sec]["score"] += 1
            topic_scores_map[top_key]["score"] += 1

        if ans:
            ans.is_correct = is_correct

    total_q = len(questions) or 1
    accuracy_pct = round((total_score / total_q) * 100, 1)
    time_taken_sec = int((now - attempt.started_at).total_seconds())
    time_taken_mins = max(1, time_taken_sec // 60)

    attempt.status = "submitted"
    attempt.submitted_at = now
    attempt.score = total_score
    attempt.total_questions = total_q
    attempt.accuracy_pct = accuracy_pct
    attempt.time_taken_sec = time_taken_sec

    old_ts = db.execute(select(TopicScore).filter_by(attempt_id=attempt.id)).scalars().all()
    for ts in old_ts:
        db.delete(ts)

    for (sec, top), counts in topic_scores_map.items():
        pct = (counts["score"] / counts["total"] * 100) if counts["total"] > 0 else 0
        band = "Strong" if pct >= 75 else ("Good" if pct >= 50 else "Needs Support")
        ts = TopicScore(
            id=f"ts_{uuid.uuid4().hex[:12]}",
            college_id=current_user.college_id,
            attempt_id=attempt.id,
            section_name=sec,
            topic=top,
            score=counts["score"],
            total=counts["total"],
            accuracy_pct=round(pct, 1),
            status_band=band
        )
        db.add(ts)

    db.commit()

    section_analysis = [
        {
            "section": sec,
            "score": f"{data['score']}/{data['total']}",
            "percentage": round((data["score"] / data["total"]) * 100, 1) if data["total"] > 0 else 0,
            "status": "Strong" if (data["score"] / data["total"]) >= 0.75 else ("Good" if (data["score"] / data["total"]) >= 0.5 else "Needs Support")
        }
        for sec, data in section_scores.items()
    ]

    questions_review = [
        {
            "number": q.question_number,
            "section": q.section_name,
            "topic": q.topic,
            "text": q.question_text,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d
            },
            "selected_option": ans_by_num.get(q.question_number).selected_option if ans_by_num.get(q.question_number) else None,
            "correct_option": q.correct_option,
            "is_correct": ans_by_num.get(q.question_number).is_correct if ans_by_num.get(q.question_number) else False,
            "explanation": q.explanation
        }
        for q in questions
    ]

    return {
        "success": True,
        "attempt_id": attempt.id,
        "score": total_score,
        "total": total_q,
        "accuracy": f"{accuracy_pct}%",
        "time_taken": f"{time_taken_mins} mins",
        "section_analysis": section_analysis,
        "questions_review": questions_review
    }

@router.get("/tests/attempts/{attempt_id}/result")
def get_attempt_result(
    attempt_id: str,
    current_user: TokenPayload = Depends(require_role(["student", "super_admin"])),
    db: Session = Depends(get_db)
):
    student = _get_student_for_user(current_user, db)
    attempt = db.execute(
        select(TestAttempt).filter_by(id=attempt_id, student_id=student.id, college_id=current_user.college_id)
    ).scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    if attempt.status != "submitted":
        raise HTTPException(status_code=400, detail="Test attempt is not submitted yet")

    questions = db.execute(
        select(PracticeQuestion).filter_by(test_id=attempt.test_id).order_by(PracticeQuestion.question_number)
    ).scalars().all()

    answers = db.execute(select(AttemptAnswer).filter_by(attempt_id=attempt.id)).scalars().all()
    ans_by_num = {a.question_number: a for a in answers}

    topic_scores = db.execute(select(TopicScore).filter_by(attempt_id=attempt.id)).scalars().all()

    section_scores = {}
    for ts in topic_scores:
        if ts.section_name not in section_scores:
            section_scores[ts.section_name] = {"score": 0, "total": 0}
        section_scores[ts.section_name]["score"] += ts.score
        section_scores[ts.section_name]["total"] += ts.total

    section_analysis = [
        {
            "section": sec,
            "score": f"{data['score']}/{data['total']}",
            "percentage": round((data["score"] / data["total"]) * 100, 1) if data["total"] > 0 else 0,
            "status": "Strong" if (data["score"] / data["total"]) >= 0.75 else ("Good" if (data["score"] / data["total"]) >= 0.5 else "Needs Support")
        }
        for sec, data in section_scores.items()
    ]

    time_taken_mins = max(1, (attempt.time_taken_sec or 0) // 60)

    questions_review = [
        {
            "number": q.question_number,
            "section": q.section_name,
            "topic": q.topic,
            "text": q.question_text,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d
            },
            "selected_option": ans_by_num.get(q.question_number).selected_option if ans_by_num.get(q.question_number) else None,
            "correct_option": q.correct_option,
            "is_correct": ans_by_num.get(q.question_number).is_correct if ans_by_num.get(q.question_number) else False,
            "explanation": q.explanation
        }
        for q in questions
    ]

    return {
        "success": True,
        "attempt_id": attempt.id,
        "score": attempt.score,
        "total": attempt.total_questions,
        "accuracy": f"{attempt.accuracy_pct}%",
        "time_taken": f"{time_taken_mins} mins",
        "section_analysis": section_analysis,
        "questions_review": questions_review
    }

# --- SCREEN 29: Virtual Labs (PDF 5) ---
@router.get("/labs")
def get_virtual_labs(db: Session = Depends(get_db)):
    labs = db.execute(select(VirtualLabItem)).scalars().all()
    active_lab = next((lab for lab in labs if lab.is_active_session), None)
    
    return {
        "labs": [
            {
                "id": l.id,
                "name": l.name,
                "category": l.category,
                "description": l.description,
                "eligibility_chip": l.eligibility_chip,
                "status_chip": l.status_chip,
                "tag_color": l.tag_color,
                "footer_text": l.footer_text,
                "requires_approval": l.requires_approval
            }
            for l in labs
        ],
        "active_session": {
            "lab_name": active_lab.name if active_lab else "AI Notebook Lab",
            "active_filename": active_lab.active_filename if active_lab else "rag_notes_demo.ipynb",
            "running_minutes": active_lab.active_minutes if active_lab else 38,
            "session_id": "session_rag_demo_01"
        } if active_lab else None
    }

@router.post("/labs/{lab_id}/launch")
def launch_lab(lab_id: str, db: Session = Depends(get_db)):
    db.execute(update(VirtualLabItem).where(VirtualLabItem.id == lab_id).values(
        is_active_session=True,
        active_filename="workspace_session.ipynb",
        active_minutes=1
    ))
    db.commit()
    return {"status": "started", "session_url": f"/live/lab_{lab_id}"}

@router.post("/labs/{lab_id}/stop")
def stop_lab(lab_id: str, db: Session = Depends(get_db)):
    db.execute(update(VirtualLabItem).where(VirtualLabItem.id == lab_id).values(is_active_session=False))
    db.commit()
    return {"status": "stopped"}

# --- SCREEN 30: Sprint Board (PDF 6) ---
class TaskMoveRequest(BaseModel):
    task_id: str
    target_column: str

class StandupRequest(BaseModel):
    yesterday: str
    today: str
    blockers: Optional[str] = None

@router.get("/projects/board")
def get_sprint_board(db: Session = Depends(get_db)):
    tasks = db.execute(select(SprintTask)).scalars().all()
    
    columns = {"todo": [], "in_progress": [], "code_review": [], "done": []}
    for t in tasks:
        col = t.column_name if t.column_name in columns else "todo"
        columns[col].append({
            "id": t.id,
            "title": t.title,
            "tag": t.tag,
            "tag_type": t.tag_type,
            "assignee_initials": t.assignee_initials,
            "assignee_name": t.assignee_name,
            "story_points": t.story_points,
            "pr_number": t.pr_number
        })
        
    return {
        "team_name": "Team Phoenix",
        "sprint_info": "Sprint 2 of 3",
        "project_title": "Clinic Appointment System",
        "client": "Trainer (Arun K.)",
        "deadline": "Ends Week 8",
        "change_request": "SMS reminder for appointments (CR-04)",
        "progress_pct": 58,
        "story_points": {"completed": 21, "total": 36, "velocity_last": 30},
        "build_status": {"state": "Passing", "deployed_time": "Deployed to staging 2 hrs ago"},
        "columns": columns
    }

@router.post("/projects/tasks/move")
def move_sprint_task(req: TaskMoveRequest, db: Session = Depends(get_db)):
    db.execute(update(SprintTask).where(SprintTask.id == req.task_id).values(column_name=req.target_column))
    db.commit()
    return {"success": True, "task_id": req.task_id, "column": req.target_column}

@router.post("/projects/standup")
def submit_standup(req: StandupRequest):
    return {"success": True, "message": "Daily standup shared with Team Phoenix & Trainer Arun K."}

# --- SCREEN 36: Mock Interviews (PDF 7) ---
class SlotBookRequest(BaseModel):
    slot_id: str

@router.get("/interviews")
def get_mock_interviews(db: Session = Depends(get_db)):
    interview = db.execute(select(MockInterview)).first()
    int_data = interview[0] if interview else None
    
    return {
        "latest_interview": {
            "title": int_data.round_title if int_data else "Mock Interview #2 – Technical",
            "date_info": int_data.interview_date if int_data else "Oct 8 · 40 min",
            "interviewer": int_data.interviewer_name if int_data else "Arun K.",
            "overall_score": int_data.overall_score if int_data else 3.8,
            "service_chip": int_data.service_chip if int_data else "Hire-ready for service roles",
            "product_chip": int_data.product_chip if int_data else "Improve for product roles",
            "rubrics": [
                {"category": "Problem solving", "score": int_data.problem_solving if int_data else 4, "max": 5},
                {"category": "Coding & correctness", "score": int_data.coding_correctness if int_data else 4, "max": 5},
                {"category": "Thinking aloud", "score": int_data.thinking_aloud if int_data else 3, "max": 5},
                {"category": "Core CS knowledge", "score": int_data.core_cs if int_data else 4, "max": 5},
                {"category": "Project explanation", "score": int_data.project_explanation if int_data else 4, "max": 5},
                {"category": "Communication & confidence", "score": int_data.communication if int_data else 3, "max": 5}
            ],
            "trainer_feedback": int_data.feedback_text if int_data else "Strong grasp of graph traversals and Union-Find.",
            "recording_url": int_data.recording_url if int_data else "/videos/mock_02.mp4"
        },
        "progress_trend": [
            {"round": "#1", "score": 3.0, "label": "#1 · 3.0"},
            {"round": "#2", "score": 3.8, "label": "#2 · 3.8"},
            {"target": 4.2, "label": "Target 4.2"}
        ],
        "available_slots": [
            {"id": "slot_01", "time": "Wed, Oct 15 · 4:00 PM", "type": "Technical", "tag_color": "blue"},
            {"id": "slot_02", "time": "Sat, Oct 18 · 10:30 AM", "type": "HR round", "tag_color": "green"},
            {"id": "slot_03", "time": "Sat, Oct 18 · 12:00 PM", "type": "AI-allowed coding", "tag_color": "purple"}
        ]
    }

@router.post("/interviews/book")
def book_interview_slot(req: SlotBookRequest):
    return {"success": True, "message": "Slot booked successfully! Confirmation sent to trainer."}

# --- SCREEN 08: Live Sessions & Recordings (PDF 14) ---
@router.get("/live")
def get_student_live_sessions(db: Session = Depends(get_db)):
    sessions = db.execute(select(SessionItem).order_by(SessionItem.scheduled_start)).scalars().all()
    
    return {
        "hero_session": {
            "badge": "Starting in 4 min",
            "title": "Future Skills: LLM APIs & RAG",
            "time_info": "Thu, Oct 9 · 11:00 AM to 12:00 PM · Arun K. · Lab: AI Notebook pre-loaded",
            "device_check": "Mic & camera check passed",
            "session_id": "sess_thu_rag"
        },
        "week_sessions": [
            {
                "id": s.id,
                "when": s.scheduled_start.strftime("%a %I:%M–") + s.scheduled_end.strftime("%I:%M"),
                "title": s.title,
                "type": s.session_type,
                "status": s.status,
                "recording_url": s.recording_url
            }
            for s in sessions
        ],
        "attendance_summary": {
            "semester": "Semester 5",
            "overall_pct": 92,
            "sessions_attended": "53 of 58 sessions",
            "weekday_pct": 93,
            "saturday_pct": 89,
            "recordings_watched": "4 of 5 for missed"
        },
        "recording_library": [
            {"title": "Cloud deploy walkthrough", "duration": "58 min"},
            {"title": "Docker Compose lab", "duration": "2 hr 51 min"},
            {"title": "Mock interview tips", "duration": "42 min"}
        ]
    }

# --- SCREEN 34: Discussion Groups (PDF 11) ---
class GroupMessageRequest(BaseModel):
    message_text: str
    code_snippet: Optional[str] = None

@router.get("/discussions")
def get_discussions(db: Session = Depends(get_db)):
    groups = db.execute(select(DiscussionGroup)).scalars().all()
    selected_group = next((g for g in groups if g.id == "grp_doubts"), groups[0] if groups else None)
    
    messages = []
    if selected_group:
        messages = db.execute(select(GroupMessage).filter_by(group_id=selected_group.id)).scalars().all()
        
    return {
        "safe_space_banner": "Safe learning space: students chat in moderated groups only. One-to-one messaging between students is turned off. All groups are moderated by trainers.",
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "badge": g.unread_badge,
                "is_locked": g.is_locked_announcement,
                "members_count": g.members_count,
                "online_count": g.online_count,
                "moderators": g.moderators,
                "pinned_note": g.pinned_note
            }
            for g in groups
        ],
        "active_group_id": selected_group.id if selected_group else "",
        "active_group_info": {
            "name": selected_group.name if selected_group else "",
            "members": 42,
            "trainers": 2,
            "doubts_answered": 128,
            "avg_reply_time": "35 min"
        },
        "top_helpers": [
            {"name": "Vikram R", "answers": 24, "medal": "gold"},
            {"name": "Ananya P", "answers": 19, "medal": "silver"},
            {"name": "Sneha N", "answers": 15, "medal": "bronze"}
        ],
        "messages": [
            {
                "id": m.id,
                "sender_name": m.sender_name,
                "sender_role": m.sender_role,
                "sender_initials": m.sender_initials,
                "message_text": m.message_text,
                "code_snippet": m.code_snippet,
                "is_marked_as_answer": m.is_marked_as_answer,
                "reactions_count": m.reactions_count,
                "timestamp": m.timestamp_str
            }
            for m in messages
        ]
    }

@router.post("/discussions/{group_id}/messages")
def send_group_message(
    group_id: str,
    req: GroupMessageRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msg = GroupMessage(
        id=f"msg_{int(datetime.datetime.utcnow().timestamp())}",
        college_id=current_user.college_id,
        group_id=group_id,
        sender_name=current_user.name or "Priya R",
        sender_role=current_user.role.capitalize(),
        sender_initials=current_user.avatar or "PR",
        message_text=req.message_text,
        code_snippet=req.code_snippet,
        timestamp_str=datetime.datetime.now().strftime("%I:%M %p")
    )
    db.add(msg)
    db.commit()
    return {"success": True, "message_id": msg.id}

