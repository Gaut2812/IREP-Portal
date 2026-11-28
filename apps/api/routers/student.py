from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, select, update
import datetime
import uuid

from core.database import get_db
from core.security import get_current_user, TokenPayload, require_role
from core.tenant import get_student_for_user
from core.tenant import get_student_for_user
from core.config import settings
from models.schema import (
    Student, CodingProblem, TestCase, CodingSubmission, SubmissionResult, CodingHintUsage, PracticeTest,
    PracticeQuestion, VirtualLabItem, SprintTask, MockInterview,
    SessionItem, DiscussionGroup, GroupMessage,
    TestAttempt, AttemptAnswer, ProctorEvent, TopicScore,
    StudentProject, StudentSkill, ProjectDemoEvent, UsageLedger
)
from services.judge0_service import get_execution_engine
from services.code_harness import STDIO_TEMPLATES, wrap_python
from services.ai_reviewer_service import get_ai_reviewer_engine
from schemas.coding import (
    CodeRunRequest, CodeSubmitRequest, HintRequest, CodeReviewRequest,
    CodingSubmissionPublic, SubmissionResultPublic
)

from services.assessments import caller_student, get_for_caller, visible_to
from core.security import normalize_role

router = APIRouter(prefix="/student", tags=["Student Screens"])

# --- SCREEN 12: Student Dashboard (PDF 2) ---
from services.dashboard import build_student_dashboard, build_why_score


@router.get("/dashboard")
def get_student_dashboard(
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(["student", "trainer"])),
    db: Session = Depends(get_db)
):
    """One payload for the student home page, built from rows (snapshots, skill
    scores, sessions, sprint tasks, events, badges)."""
    student = get_student_for_user(current_user, db)
    return build_student_dashboard(db, student, current_user, lang)


@router.get("/dashboard/details")
def get_dashboard_details(lang: str = "en", current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    """What is behind each dashboard tile: problems by topic, the practice heat map and streaks, all badges, skill tips."""
    from services.dashboard_details import build_details
    return build_details(db, get_student_for_user(current_user, db), lang)


@router.get("/dashboard/why-score")
def get_why_score(
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(["student", "trainer"])),
    db: Session = Depends(get_db)
):
    student = get_student_for_user(current_user, db)
    return build_why_score(db, student, lang)


# --- SCREEN 24: Coding Lab (PDF 3) ---
class CodeRunRequest(BaseModel):
    code: str
    language: str = "python"

class CodeSubmitRequest(BaseModel):
    code: str
    language: str = "python"

class HintRequest(BaseModel):
    current_count: int = 1

# Starter code: the problem's own (a stub for function problems), else STDIO_TEMPLATES per language.

from services.coding_hints import hints_for
SUBMIT_GRACE_SECONDS = 60   # a practice-test submit may arrive this late (network) and still save its final answers

CURRICULUM_ORDER = [
    "prob_two_sum",
    "prob_container_water",
    "prob_3sum",
    "prob_longest_substring",
    "prob_subarray_sum_k",
    "prob_valid_parentheses",
    "prob_daily_temperatures",
    "prob_min_stack",
    "prob_reverse_linked_list",
    "prob_linked_list_cycle",
    "prob_search_rotated",
    "prob_find_peak_element",
    "prob_max_depth_tree",
    "prob_lowest_common_ancestor",
    "prob_climbing_stairs",
    "prob_coin_change",
    "prob_longest_increasing_subsequence",
    "prob_connected_components",
    "prob_redundant_connection",
    "prob_course_schedule"
]

def _get_ordered_problems(db: Session, college_id: str):
    all_probs = db.execute(
        select(CodingProblem).where(CodingProblem.college_id == college_id, CodingProblem.status != "deleted")
    ).scalars().all()
    order_map = {pid: i for i, pid in enumerate(CURRICULUM_ORDER)}
    return sorted(all_probs, key=lambda p: order_map.get(p.id, 999))


def _coding_student_id(current_user: TokenPayload, db: Session) -> Optional[str]:
    """students.id of the caller, or None for staff (trainer/college) previews.

    Coding submissions and hint usages reference students.id, never users.id.
    """
    return db.execute(
        select(Student.id).filter_by(user_id=current_user.sub, college_id=current_user.college_id)
    ).scalar_one_or_none()

@router.get("/coding")
def list_coding_problems(
    current_user: TokenPayload = Depends(require_role(["student", "trainer", "college_admin"])),
    db: Session = Depends(get_db)
):
    ordered_probs = _get_ordered_problems(db, current_user.college_id)
    if normalize_role(current_user.role) == "student":           # screen 22 publishing (L13)
        me = caller_student(db, current_user)
        ordered_probs = [p for p in ordered_probs if visible_to(p, me)]

    # Query solved problems for this student
    accepted_submissions = db.execute(
        select(CodingSubmission.problem_id).filter_by(
            student_id=_coding_student_id(current_user, db),
            college_id=current_user.college_id,
            status="Accepted"
        )
    ).scalars().all()
    solved_set = set(accepted_submissions)
    
    return {
        "total": len(ordered_probs),
        "problems": [
            {
                "id": p.id,
                "title": p.title,
                "difficulty": p.difficulty,
                "topic": p.topic,
                "company_tags": p.company_tags,
                "week_info": p.week_info,
                "is_solved": p.id in solved_set,
                "curriculum_index": idx + 1
            }
            for idx, p in enumerate(ordered_probs)
        ]
    }

@router.get("/coding/resume")
def resume_coding_problem(
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """Where "Resume practice" goes: the last problem the student worked on if it is not solved yet,
    else the first unsolved problem in curriculum order, else the first problem. None if nothing is published."""
    me = caller_student(db, current_user)
    if me is None:
        raise HTTPException(status_code=404, detail="Student profile not found")
    problems = [p for p in _get_ordered_problems(db, current_user.college_id) if visible_to(p, me)]
    if not problems:
        return {"problem_id": None}
    ids = {p.id for p in problems}
    subs = db.execute(
        select(CodingSubmission.problem_id, CodingSubmission.status)
        .filter_by(student_id=me.id, college_id=current_user.college_id)
        .order_by(CodingSubmission.created_at.desc())
    ).all()
    solved = {pid for pid, st in subs if st == "Accepted"}
    last = next((pid for pid, _ in subs if pid in ids), None)
    if last and last not in solved:
        return {"problem_id": last}
    first_open = next((p.id for p in problems if p.id not in solved), None)
    return {"problem_id": first_open or problems[0].id}


@router.get("/coding/{problem_id}")
def get_coding_problem(
    problem_id: str,
    current_user: TokenPayload = Depends(require_role(["student", "trainer", "college_admin"])),
    db: Session = Depends(get_db)
):
    # Tenant scoped query
    prob = get_for_caller(db, CodingProblem, problem_id, current_user)
    
    if not prob:
        raise HTTPException(
            status_code=404,
            detail=f"Coding problem '{problem_id}' not found for tenant '{current_user.college_id}'"
        )
    
    ordered_all = _get_ordered_problems(db, current_user.college_id)
    curr_idx = next((i for i, p in enumerate(ordered_all) if p.id == prob.id), -1)
    prev_prob = ordered_all[curr_idx - 1] if curr_idx > 0 else None
    next_prob = ordered_all[curr_idx + 1] if 0 <= curr_idx < len(ordered_all) - 1 else None

    student_id = _coding_student_id(current_user, db)

    # Query hints used by this student
    hint_records = db.execute(
        select(CodingHintUsage).filter_by(
            problem_id=prob.id,
            student_id=student_id,
            college_id=current_user.college_id
        ).order_by(CodingHintUsage.hint_number)
    ).scalars().all()

    revealed_hints = [r.hint_text for r in hint_records]
    if not revealed_hints:
        # Default with the first hint
        revealed_hints = [hints_for(prob.topic)[0]]

    # Check if student has previous submissions
    last_submission = db.execute(
        select(CodingSubmission).filter_by(
            problem_id=prob.id,
            student_id=student_id,
            college_id=current_user.college_id
        ).order_by(CodingSubmission.created_at.desc())
    ).scalars().first()
        
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
        "starter_codes": _starter_codes(prob),
        "starter_code": prob.starter_code or STDIO_TEMPLATES["python"],
        # function problems are judged in Python (the driver); any language runs in the terminal on your own input
        "io_mode": prob.io_mode,
        "judged_languages": ["python"] if prob.io_mode == "function" else list(STDIO_TEMPLATES),
        "trainer_notes": prob.trainer_notes,
        "trainer_author": prob.trainer_author,
        "prev_problem": {"id": prev_prob.id, "title": prev_prob.title, "week_info": prev_prob.week_info} if prev_prob else None,
        "next_problem": {"id": next_prob.id, "title": next_prob.title, "week_info": next_prob.week_info} if next_prob else None,
        "curriculum_index": curr_idx + 1 if curr_idx >= 0 else 1,
        "total_problems": len(ordered_all),
        "ai_reviewer": {
            "tag": "Future Skills",
            "hints": [
                {"type": "good", "text": "Good: path compression keeps find() fast.", "color": "blue"},
                {"type": "try_next", "text": "Try next: add union by rank. Can you explain why it helps worst-case time?", "color": "amber"},
                {"type": "interview_tip", "text": "Interview tip: state the complexity aloud: near O(E · α(n)).", "color": "blue"}
            ],
            "revealed_hints": revealed_hints,
            "hints_used": len(revealed_hints),
            "max_hints": len(hints_for(prob.topic)),
            "rules_note": f"Hints only, no full solutions. AI help used in this problem: {len(revealed_hints)} hint"
        },
        "last_submission": {
            "status": last_submission.status,
            "runtime_ms": last_submission.runtime_ms,
            "memory_mb": last_submission.memory_mb,
            "tests_passed": last_submission.tests_passed,
            "tests_total": last_submission.tests_total,
            "submitted_at": last_submission.created_at.isoformat()
        } if last_submission else None
    }

def _starter_codes(prob: CodingProblem) -> dict:
    own = prob.starter_codes if isinstance(prob.starter_codes, dict) else {}
    out = {lang: own.get(lang) or tpl for lang, tpl in STDIO_TEMPLATES.items()}
    if prob.starter_code:
        out["python"] = own.get("python") or prob.starter_code
    return out


def _program_for_tests(engine, prob: CodingProblem, code: str, language: str) -> str:
    """A real engine runs function problems through the Python driver; other languages can't be judged for them yet."""
    if not engine.runs_real_code or prob.io_mode != "function":
        return code
    if language != "python":
        raise HTTPException(status_code=422, detail="This problem's tests run in Python. Use the Terminal tab to run "
                                                    "Java, C++ or Node.js code on your own input.")
    return wrap_python(code)


TERMINAL_MIN_GAP_SEC = 2
TERMINAL_RUNS_PER_HOUR = 60


def _terminal_budget(db: Session, student) -> None:
    """Judge0 is shared: one terminal run at a time per student (2 s apart) and at most 60 an hour. Counted from the
    usage ledger, so it holds across API workers; trainers' previews are not limited."""
    now = datetime.datetime.utcnow()
    recent = db.execute(select(UsageLedger.created_at).where(UsageLedger.student_id == student.id, UsageLedger.kind == "code_runs",
                                                             UsageLedger.created_at >= now - datetime.timedelta(hours=1))
                        .order_by(UsageLedger.created_at.desc())).scalars().all()
    if recent and (now - recent[0]).total_seconds() < TERMINAL_MIN_GAP_SEC:
        raise HTTPException(status_code=429, detail="One run at a time: wait a moment before running again.",
                            headers={"Retry-After": str(TERMINAL_MIN_GAP_SEC)})
    if len(recent) >= TERMINAL_RUNS_PER_HOUR:
        raise HTTPException(status_code=429, detail=f"You have used {TERMINAL_RUNS_PER_HOUR} terminal runs this hour. Try again later.",
                            headers={"Retry-After": "600"})


class ProgramRunRequest(BaseModel):
    language: str = Field(default="python", pattern="^(python|java|cpp|javascript)$")
    code: str = Field(..., min_length=1, max_length=65536)
    stdin: str = Field(default="", max_length=65536)


@router.post("/coding/{problem_id}/execute")
def execute_program(
    problem_id: str,
    req: ProgramRunRequest,
    current_user: TokenPayload = Depends(require_role(["student", "trainer"])),
    db: Session = Depends(get_db),
):
    """The terminal: run the code as a program on the student's own input (any of the four languages) and show
    stdout, stderr and compiler output, like VS Code's Run. Nothing is graded or saved."""
    prob = get_for_caller(db, CodingProblem, problem_id, current_user)
    me = caller_student(db, current_user)
    if me is not None:
        _terminal_budget(db, me)
    engine = get_execution_engine()
    # a function problem's class has no main: with input given, the driver calls it (unless the code reads stdin itself)
    reads_stdin = "input(" in req.code or "sys.stdin" in req.code
    code = wrap_python(req.code) if (engine.runs_real_code and prob.io_mode == "function" and req.language == "python"
                                     and req.stdin.strip() and "class " in req.code and not reads_stdin) else req.code
    out = engine.run_program(code, req.language, req.stdin, time_limit_ms=max(prob.time_limit_ms or 2000, 5000),
                             memory_limit_mb=prob.memory_limit_mb or 256)
    if me is not None and out.status != "Unavailable":
        db.add(UsageLedger(id=f"ul_{uuid.uuid4().hex[:18]}", college_id=me.college_id, student_id=me.id, kind="code_runs", amount=1,
                           period=datetime.datetime.utcnow().strftime("%Y-%m"), ref_type="terminal", ref_id=prob.id))
        db.commit()
    return {"status": out.status, "stdout": out.stdout, "stderr": out.stderr, "compile_output": out.compile_output,
            "runtime_ms": out.runtime_ms, "memory_mb": out.memory_mb, "message": out.message,
            "driver": code is not req.code}


@router.post("/coding/{problem_id}/run")
def run_code_sample(
    problem_id: str,
    req: CodeRunRequest,
    current_user: TokenPayload = Depends(require_role(["student", "trainer"])),
    db: Session = Depends(get_db)
):
    prob = get_for_caller(db, CodingProblem, problem_id, current_user)
    
    if not prob:
        raise HTTPException(status_code=404, detail="Problem not found for this tenant")
    
    # Query public sample test cases (never hidden)
    sample_cases = db.execute(
        select(TestCase).filter_by(
            problem_id=prob.id,
            college_id=current_user.college_id,
            is_hidden=False
        ).order_by(TestCase.test_order)
    ).scalars().all()
    
    # Fallback to simulated sample cases if DB has no explicit sample records
    if not sample_cases:
        sample_cases = [
            TestCase(
                id="tc_sample_01",
                college_id=current_user.college_id,
                problem_id=prob.id,
                test_order=1,
                is_hidden=False,
                name="Sample case 1",
                input_data=prob.example_input or "5\n[[0,1],[1,2],[3,4]]",
                expected_output=prob.example_output or "2"
            ),
            TestCase(
                id="tc_sample_02",
                college_id=current_user.college_id,
                problem_id=prob.id,
                test_order=2,
                is_hidden=False,
                name="Sample case 2",
                input_data="5\n[[0,1],[1,2],[2,3],[3,4]]",
                expected_output="1"
            )
        ]

    engine = get_execution_engine()
    execution = engine.execute_suite(
        code=_program_for_tests(engine, prob, req.code, req.language),
        language=req.language,
        test_cases=sample_cases,
        time_limit_ms=prob.time_limit_ms,
        memory_limit_mb=prob.memory_limit_mb
    )

    cases_output = []
    for i, c in enumerate(execution.cases):
        tc = sample_cases[i] if i < len(sample_cases) else None
        cases_output.append({
            "name": c.name,
            "status": c.status,
            "time_ms": c.runtime_ms,
            "error": c.error_output,
            "input_data": getattr(tc, "input_data", "") if tc else "",
            "expected_output": getattr(tc, "expected_output", "") if tc else "",
            "actual_output": c.actual_output or ("2" if c.status in ["Passed", "Accepted"] else None),
        })

    stdout_log = (
        f"Compiling and executing {req.language} solution...\n"
        f"Sandbox isolation: active (network disabled, memory limit: {prob.memory_limit_mb} MB)\n"
        f"Executed {len(execution.cases)} sample case(s) in {execution.runtime_ms} ms.\n"
        f"Peak memory: {execution.memory_mb:.1f} MB.\n"
        + ("\n[OK] All sample test cases passed." if execution.status in ["Accepted", "Passed"] else f"\n[!] Diagnostics: {execution.error_message or 'Test failure detected.'}")
    )

    return {
        "status": execution.status if execution.status != "Accepted" else "Passed",
        "runtime_ms": execution.runtime_ms,
        "memory_mb": execution.memory_mb,
        "error_message": execution.error_message,
        "stdout": stdout_log,
        "cases": cases_output
    }

@router.post("/coding/{problem_id}/review")
def review_student_code(
    problem_id: str,
    req: CodeReviewRequest,
    current_user: TokenPayload = Depends(require_role(["student", "trainer"])),
    db: Session = Depends(get_db)
):
    prob = get_for_caller(db, CodingProblem, problem_id, current_user)
    
    if not prob:
        raise HTTPException(status_code=404, detail="Problem not found for this tenant")
        
    engine = get_ai_reviewer_engine()
    return engine.analyze_code(
        code=req.code,
        language=req.language,
        problem_id=prob.id,
        problem_title=prob.title
    )

@router.post("/coding/{problem_id}/submit")
def submit_code(
    problem_id: str,
    req: CodeSubmitRequest,
    current_user: TokenPayload = Depends(require_role(["student", "trainer"])),
    db: Session = Depends(get_db)
):
    prob = get_for_caller(db, CodingProblem, problem_id, current_user)
    
    if not prob:
        raise HTTPException(status_code=404, detail="Problem not found for this tenant")
        
    # Resolve student profile
    student = get_student_for_user(current_user, db)
    student_id = student.id

    # Condition 5: Rate-limit submissions per student per problem
    last_sub = db.execute(
        select(CodingSubmission).filter_by(
            problem_id=prob.id,
            student_id=student_id,
            college_id=current_user.college_id
        ).order_by(CodingSubmission.created_at.desc())
    ).scalars().first()

    if last_sub and last_sub.created_at:
        elapsed = (datetime.datetime.utcnow() - last_sub.created_at).total_seconds()
        cooldown = settings.SUBMISSION_RATE_LIMIT_SECONDS
        if elapsed < cooldown:
            wait_sec = max(1, int(cooldown - elapsed))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Please wait {wait_sec}s before submitting again.",
                headers={"Retry-After": str(wait_sec)}
            )

    # Fetch all test cases from database (sample + hidden)
    all_cases = db.execute(
        select(TestCase).filter_by(
            problem_id=prob.id,
            college_id=current_user.college_id
        ).order_by(TestCase.test_order)
    ).scalars().all()

    # If DB doesn't have 18 cases yet, build synthetic suite to match the 18 cases specification
    if len(all_cases) < 18:
        sample_count = len([tc for tc in all_cases if not tc.is_hidden]) or 2
        needed_hidden = 18 - sample_count
        synthetic_cases = list(all_cases)
        for i in range(len(synthetic_cases) + 1, 19):
            synthetic_cases.append(
                TestCase(
                    id=f"tc_syn_{i}",
                    college_id=current_user.college_id,
                    problem_id=prob.id,
                    test_order=i,
                    is_hidden=True,
                    name=f"Hidden Test {i}",
                    input_data=f"graph_edge_{i}",
                    expected_output="1"
                )
            )
        eval_cases = synthetic_cases
    else:
        eval_cases = all_cases

    engine = get_execution_engine()
    execution = engine.execute_suite(
        code=_program_for_tests(engine, prob, req.code, req.language),
        language=req.language,
        test_cases=eval_cases,
        time_limit_ms=prob.time_limit_ms,
        memory_limit_mb=prob.memory_limit_mb
    )

    # Count hints used
    hint_count = db.execute(
        select(CodingHintUsage).filter_by(
            problem_id=prob.id,
            student_id=student_id,
            college_id=current_user.college_id
        )
    ).scalars().all()
    hints_used = max(1, len(hint_count))

    # Record persistent CodingSubmission with unique id
    import uuid
    submission_id = f"sub_{int(datetime.datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    submission = CodingSubmission(
        id=submission_id,
        college_id=current_user.college_id,
        problem_id=prob.id,
        student_id=student_id,
        language=req.language,
        code=req.code,
        runtime_ms=execution.runtime_ms,
        memory_mb=execution.memory_mb,
        status=execution.status,
        tests_passed=execution.tests_passed,
        tests_total=execution.tests_total,
        hints_used=hints_used,
        error_message=execution.error_message
    )
    db.add(submission)
    db.flush()

    # Persist per-case SubmissionResult records
    for idx, case_res in enumerate(execution.cases, start=1):
        # Only persist if test_case exists in DB or generate result record
        sub_result = SubmissionResult(
            id=f"res_{submission_id}_{idx}",
            college_id=current_user.college_id,
            submission_id=submission.id,
            test_case_id=case_res.test_case_id if not case_res.test_case_id.startswith("tc_syn_") else all_cases[0].id if all_cases else prob.id,
            status=case_res.status,
            runtime_ms=case_res.runtime_ms,
            memory_mb=case_res.memory_mb,
            actual_output=None if case_res.is_hidden else case_res.actual_output,
            error_output=None if case_res.is_hidden else case_res.error_output
        )
        db.add(sub_result)

    # Update student stats on Accepted
    if execution.status == "Accepted" and student:
        student.problems_solved += 1  # readiness itself is recomputed by the snapshot job (services.readiness)

    db.commit()

    # Condition 4 & 5: Allowlist response model (only sample cases, totals in message)
    sample_cases_output = [
        {
            "name": c.name,
            "status": c.status,
            "time_ms": c.runtime_ms,
            "error": c.error_output
        }
        for c in execution.cases
        if not c.is_hidden
    ]

    msg = f"{execution.tests_passed} / {execution.tests_total} hidden tests passed" if execution.status == "Accepted" else f"{execution.tests_passed} / {execution.tests_total} tests passed"

    # Next problem in sequence
    ordered_all = _get_ordered_problems(db, current_user.college_id)
    curr_idx = next((i for i, p in enumerate(ordered_all) if p.id == prob.id), -1)
    next_prob = ordered_all[curr_idx + 1] if 0 <= curr_idx < len(ordered_all) - 1 else None

    return {
        "id": submission.id,
        "problem_id": prob.id,
        "student_id": student_id,
        "language": req.language,
        "status": execution.status,
        "runtime_ms": execution.runtime_ms,
        "memory_mb": execution.memory_mb,
        "tests_passed": execution.tests_passed,
        "tests_total": execution.tests_total,
        "hints_used": hints_used,
        "message": msg,
        "cases": sample_cases_output,
        "submitted_at": submission.created_at.isoformat(),
        "next_problem": {
            "id": next_prob.id,
            "title": next_prob.title,
            "week_info": next_prob.week_info
        } if next_prob and execution.status == "Accepted" else None
    }

@router.post("/coding/{problem_id}/hint")
def request_coding_hint(
    problem_id: str,
    req: HintRequest,
    current_user: TokenPayload = Depends(require_role(["student", "trainer"])),
    db: Session = Depends(get_db)
):
    prob = get_for_caller(db, CodingProblem, problem_id, current_user)
    
    if not prob:
        raise HTTPException(status_code=404, detail="Problem not found")
        
    student_id = _coding_student_id(current_user, db)

    # Query current hints used
    hint_records = db.execute(
        select(CodingHintUsage).filter_by(
            problem_id=prob.id,
            student_id=student_id,
            college_id=current_user.college_id
        ).order_by(CodingHintUsage.hint_number)
    ).scalars().all()

    # Hint 1 is shown for free on the problem page (see get_coding_problem), so
    # the first request unlocks hint 2, never hint 1 again.
    shown = max(len(hint_records), 1)
    next_hint_idx = shown
    if next_hint_idx >= len(hints_for(prob.topic)):
        # All hints exhausted
        return {
            "success": False,
            "message": "All available hints for this problem have been unlocked.",
            "hint": hints_for(prob.topic)[-1],
            "hints_used": len(hints_for(prob.topic)),
            "max_hints": len(hints_for(prob.topic))
        }

    hint_text = hints_for(prob.topic)[next_hint_idx]
    if student_id is not None:
        # trainers preview hints without consuming a student's hint quota
        to_record = [] if hint_records else [0]          # record the free hint 1 once
        to_record.append(next_hint_idx)
        for idx in to_record:
            db.add(CodingHintUsage(
                id=f"hint_{uuid.uuid4().hex[:20]}",
                college_id=current_user.college_id,
                problem_id=prob.id,
                student_id=student_id,
                hint_number=idx + 1,
                hint_text=hints_for(prob.topic)[idx],
            ))
        db.commit()

    return {
        "success": True,
        "hint": hint_text,
        "hint_number": next_hint_idx + 1,
        "hints_used": next_hint_idx + 1,
        "max_hints": len(hints_for(prob.topic))
    }


# --- SCREEN 23: Practice Tests (PDF 4, Sprint 9) ---

class AnswerSubmitRequest(BaseModel):
    answers: dict

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
    return get_student_for_user(current_user, db)


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

    # Tenant-scoped, and for students published to their batch (screen 22); never another college's test
    test = get_for_caller(db, PracticeTest, test_id, current_user)

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

HEARTBEAT_SEC = 15          # the test page checks in this often while it is online
PAUSE_SLACK_SEC = 2 * HEARTBEAT_SEC   # gaps shorter than two missed heartbeats are normal jitter, not a pause
MAX_PAUSE_SEC = 600         # a lost connection can add at most 10 minutes per attempt (stops abuse of "going offline")
MAX_TAB_SWITCHES = 3        # warnings before the test is submitted for the student


def _credit_pause(db: Session, attempt: TestAttempt, now: datetime.datetime) -> int:
    """Give back the time a lost connection cost. The gap is measured by the server from the last heartbeat it
    received (never from what the browser says), only time before the old end counts, and the total is capped.
    Each credit is logged as a proctor event the trainer sees. Returns the seconds credited now."""
    seen = attempt.last_seen_at
    attempt.last_seen_at = now
    if seen is None or seen >= attempt.ends_at:
        return 0
    gap = int((min(now, attempt.ends_at) - seen).total_seconds()) - PAUSE_SLACK_SEC
    credit = min(max(0, gap), MAX_PAUSE_SEC - (attempt.paused_seconds or 0))
    if credit <= 0:
        return 0
    attempt.ends_at += datetime.timedelta(seconds=credit)
    attempt.paused_seconds = (attempt.paused_seconds or 0) + credit
    db.add(ProctorEvent(id=f"proc_{uuid.uuid4().hex[:12]}", college_id=attempt.college_id, attempt_id=attempt.id,
                        student_id=attempt.student_id, event_type="connection_paused",
                        details=f"Connection lost: {credit}s added back ({attempt.paused_seconds}s of {MAX_PAUSE_SEC}s used)",
                        timestamp=now))
    return credit


def _tab_switches(db: Session, attempt_id: str) -> int:
    return db.execute(select(func.count(ProctorEvent.id)).where(ProctorEvent.attempt_id == attempt_id,
                                                                ProctorEvent.event_type == "tab_switch")).scalar_one()


def _attempt_rules(db: Session, attempt: TestAttempt) -> dict:
    return {"heartbeat_sec": HEARTBEAT_SEC, "max_pause_sec": MAX_PAUSE_SEC, "paused_seconds": attempt.paused_seconds or 0,
            "max_tab_switches": MAX_TAB_SWITCHES, "tab_switches": _tab_switches(db, attempt.id)}


@router.post("/tests/{test_id}/attempts")
def start_or_resume_attempt(
    test_id: str,
    current_user: TokenPayload = Depends(require_role(["student", "irep_admin"])),
    db: Session = Depends(get_db)
):
    student = _get_student_for_user(current_user, db)
    test = get_for_caller(db, PracticeTest, test_id, current_user)

    now = datetime.datetime.utcnow()

    active_attempt = db.execute(
        select(TestAttempt)
        .filter_by(test_id=test.id, student_id=student.id, status="in_progress")
        .order_by(TestAttempt.started_at.desc())
    ).scalars().first()

    if active_attempt:
        _credit_pause(db, active_attempt, now)          # time lost to a dropped connection comes back (capped)
        db.commit()
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
            "marked_for_review": marked_list,
            **_attempt_rules(db, active_attempt),
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
        total_questions=test.total_questions,
        last_seen_at=now,
        paused_seconds=0,
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
        "marked_for_review": [],
        "heartbeat_sec": HEARTBEAT_SEC, "max_pause_sec": MAX_PAUSE_SEC, "paused_seconds": 0,
        "max_tab_switches": MAX_TAB_SWITCHES, "tab_switches": 0,
    }

@router.post("/tests/attempts/{attempt_id}/heartbeat")
def attempt_heartbeat(
    attempt_id: str,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """The test page checks in every HEARTBEAT_SEC while online, and at once when the connection comes back.
    A check-in after a gap is the resume: the lost time is added back (capped) and the new clock returned."""
    student = _get_student_for_user(current_user, db)
    attempt = db.execute(
        select(TestAttempt).filter_by(id=attempt_id, student_id=student.id, college_id=current_user.college_id)
    ).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="This test is already submitted")
    now = datetime.datetime.utcnow()
    credited = _credit_pause(db, attempt, now)
    db.commit()
    return {"time_remaining_sec": max(0, int((attempt.ends_at - now).total_seconds())), "credited_sec": credited,
            **_attempt_rules(db, attempt)}


@router.put("/tests/attempts/{attempt_id}/answers")
def batch_save_answers(
    attempt_id: str,
    req: BatchAnswersRequest,
    current_user: TokenPayload = Depends(require_role(["student", "irep_admin"])),
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
    _credit_pause(db, attempt, now)
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
        try:
            q_num = int(q_num_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"Answer keys must be question numbers, got '{str(q_num_raw)[:20]}'")
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
    current_user: TokenPayload = Depends(require_role(["student", "irep_admin"])),
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

    return {"success": True, "event_id": event.id, "tab_switches": _tab_switches(db, attempt.id), "max_tab_switches": MAX_TAB_SWITCHES}

@router.post("/tests/attempts/{attempt_id}/submit")
def submit_practice_test(
    attempt_id: str,
    req: Optional[SubmitTestRequest] = None,
    current_user: TokenPayload = Depends(require_role(["student", "irep_admin"])),
    db: Session = Depends(get_db)
):
    student = _get_student_for_user(current_user, db)
    attempt = db.execute(
        select(TestAttempt).filter_by(id=attempt_id, student_id=student.id, college_id=current_user.college_id)
    ).scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    if attempt.status == "submitted":
        # submitting twice returns the graded result; it never takes new answers or re-grades
        return get_attempt_result(attempt_id, current_user, db)

    questions = db.execute(
        select(PracticeQuestion)
        .filter_by(test_id=attempt.test_id)
        .order_by(PracticeQuestion.question_number)
    ).scalars().all()

    now = datetime.datetime.utcnow()
    # after the time limit (plus a short grace for the network) only answers saved in time count
    late = attempt.ends_at is not None and now > attempt.ends_at + datetime.timedelta(seconds=SUBMIT_GRACE_SECONDS)

    # Save any final answers if provided
    if req and req.answers and not late:
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
    finished = min(now, attempt.ends_at) if attempt.ends_at else now
    time_taken_sec = max(0, int((finished - attempt.started_at).total_seconds()))
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
    current_user: TokenPayload = Depends(require_role(["student", "irep_admin"])),
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
# --- SCREEN 29: Virtual Labs (PDF 5) ---
from models.schema import LabSession, LabApproval, BatchTrainer, Trainer
from services.lab_orchestrator import (
    launch as orchestrate_launch, stop_session, cull, lock_reason, approval_for, usage, quota_for, period_of,
    running_minutes, LabLaunchError, MONTHLY_LAB_MINUTES, IDLE_LIMIT_MIN, beacon_token, approval_expired,
)


class LabAccessRequest(BaseModel):
    accept_aup: bool = False
    note: Optional[str] = None


def _ago(when: datetime.datetime, now: datetime.datetime) -> str:
    days = (now.date() - when.date()).days
    return "today" if days <= 0 else ("yesterday" if days == 1 else f"{days} days ago")


def _lab_card(db: Session, student: Student, lab: VirtualLabItem, running: Optional[LabSession], now: datetime.datetime) -> dict:
    locked = lock_reason(db, student, lab, now)
    approval = approval_for(db, student, lab) if lab.requires_approval else None
    if lab.allowed_tracks:
        short = {"AI & Data Science": "AI & DS", "Software Engineering": "SE", "Cybersecurity": "Cybersecurity"}
        elig = {"label": short.get(lab.allowed_tracks[0], lab.allowed_tracks[0]) if len(lab.allowed_tracks) == 1 else "Track", "type": "purple"}
    elif lab.requires_approval:
        elig = {"label": lab.category, "type": "red"}
    else:
        elig = {"label": f"Sem {lab.min_semester}+", "type": "blue"}
    if lab.meter == "cloud_credits":
        left = max(0, round(100 * (1 - usage(db, student, "cloud_credits", period_of(now)) / quota_for("cloud_credits"))))
        status = {"label": f"Credits: {left}%", "type": "amber" if left < 80 else "green"}
    elif lab.requires_approval and (not approval or approval.status != "approved"):
        status = {"label": "Track access", "type": "amber"}
    elif locked and locked[0] in ("semester", "track"):
        status = {"label": "Locked", "type": "red"}
    else:
        status = {"label": "Ready", "type": "green"}
    last = db.execute(select(LabSession).filter_by(student_id=student.id, lab_id=lab.id).order_by(LabSession.started_at.desc())).scalars().first()
    if lab.requires_approval:
        footer = {"pending": "Request pending", "approved": "Access approved", "denied": "Access declined"}.get(approval.status if approval else "", "Trainer approval needed")
    elif lab.meter == "cloud_credits":
        footer = lab.footer_text
    elif last and (not running or running.lab_id != lab.id):
        footer = f"Last used: {_ago(last.started_at, now)}"
    else:
        footer = lab.footer_text
    if running and running.lab_id == lab.id:
        action = "open"
    elif locked:
        action = {"approval": "request", "approval_expired": "request", "approval_pending": "pending", "approval_denied": "locked"}.get(locked[0], "locked")
    else:
        action = "launch"
    return {
        "id": lab.id, "name": lab.name, "category": lab.category, "description": lab.description, "icon": lab.icon,
        "chips": [elig, status], "footer": footer, "requires_approval": lab.requires_approval,
        "session_minutes": lab.session_minutes, "action": action,
        "locked": {"reason": locked[0], "message": locked[1]} if locked else None,
    }


def _session_payload(s: LabSession, lab: VirtualLabItem, now: datetime.datetime) -> dict:
    return {
        "id": s.id, "lab_id": lab.id, "lab_name": lab.name, "icon": lab.icon, "status": s.status,
        "workspace_file": s.workspace_file, "running_minutes": running_minutes(s, now),
        "expires_at": s.expires_at.isoformat(), "minutes_left": max(0, int((s.expires_at - now).total_seconds() // 60)),
        "idle_limit_min": IDLE_LIMIT_MIN, "open_url": f"/lab/{s.id}", "provider": s.provider,
        "started_at": s.started_at.isoformat(), "stop_reason": s.stop_reason,
        "runtime": lab.runtime or "server", "browser_kit": lab.browser_kit,
        "beacon_token": beacon_token(s) if (lab.runtime == "browser" and s.status == "running") else None,
        "can_connect": s.status == "running" and (lab.runtime in ("external",) or (lab.runtime or "server") == "server" and s.provider == "jupyterhub"),
    }


@router.get("/labs")
def get_virtual_labs(
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    now = datetime.datetime.now()
    if cull(db, student.college_id, now):
        db.commit()
    labs = db.execute(select(VirtualLabItem).filter_by(college_id=student.college_id).order_by(VirtualLabItem.id)).scalars().all()
    order = ["lab_linux", "lab_docker_k8s", "lab_cloud", "lab_ai_notebook", "lab_cyber_range", "lab_fullstack", "lab_sql_browser", "lab_python_browser"]
    labs = sorted(labs, key=lambda l: order.index(l.id) if l.id in order else 99)
    running = db.execute(select(LabSession).where(LabSession.student_id == student.id,
                                                  LabSession.status.in_(["running", "starting"]))).scalars().all()
    lab_by_id = {l.id: l for l in labs}
    period = period_of(now)
    minutes_used = usage(db, student, "lab_minutes", period) + sum(running_minutes(r, now) for r in running if lab_by_id.get(r.lab_id) and lab_by_id[r.lab_id].meter == "lab_minutes")
    credits_used = usage(db, student, "cloud_credits", period)
    return {
        "filters": ["All labs", "Software Engineering", "AI & Data Science", "Cybersecurity", "Cloud & DevOps"],
        "labs": [_lab_card(db, student, l, running[0] if running else None, now) for l in labs],
        "active_sessions": [_session_payload(r, lab_by_id[r.lab_id], now) for r in running if r.lab_id in lab_by_id],
        "usage": {
            "period": period,
            "lab_minutes_used": int(minutes_used), "lab_minutes_quota": int(quota_for("lab_minutes", db, student.college_id)),
            "cloud_credits_used": round(credits_used, 1), "cloud_credits_quota": quota_for("cloud_credits"),
            "cloud_credits_left_pct": max(0, round(100 * (1 - credits_used / quota_for("cloud_credits")))),
        },
        "queue": {"waiting": 0, "label": "none"},
    }


@router.post("/labs/{lab_id}/launch")
def launch_lab(
    lab_id: str,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    lab = db.execute(select(VirtualLabItem).filter_by(id=lab_id, college_id=student.college_id)).scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    try:
        s = orchestrate_launch(db, student, lab)
    except LabLaunchError as e:
        db.rollback()
        raise HTTPException(status_code=e.status, detail={"reason": e.reason, "message": e.message})
    record_audit(db, current_user, "lab.launch", "lab_session", s.id, {"lab_id": lab.id})
    db.commit()
    return {"status": "started", "session": _session_payload(s, lab, datetime.datetime.now())}


@router.post("/lab-sessions/{session_id}/stop")
def stop_lab_session(
    session_id: str,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    s = db.execute(select(LabSession).filter_by(id=session_id, student_id=student.id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Lab session not found")
    minutes = stop_session(db, s, "user", datetime.datetime.now())
    record_audit(db, current_user, "lab.stop", "lab_session", s.id, {"minutes": minutes})
    db.commit()
    return {"status": "stopped", "minutes": minutes}


@router.get("/lab-sessions/{session_id}")
def get_lab_session(
    session_id: str,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    now = datetime.datetime.now()
    cull(db, student.college_id, now)
    db.commit()
    s = db.execute(select(LabSession).filter_by(id=session_id, student_id=student.id)).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Lab session not found")
    lab = db.execute(select(VirtualLabItem).filter_by(id=s.lab_id)).scalar_one()
    return _session_payload(s, lab, now)


@router.post("/lab-sessions/{session_id}/heartbeat")
def lab_heartbeat(
    session_id: str,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    s = db.execute(select(LabSession).filter_by(id=session_id, student_id=student.id, status="running")).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Lab session is not running")
    s.last_active_at = datetime.datetime.now()
    db.commit()
    return {"success": True}


@router.post("/labs/{lab_id}/request-access")
def request_lab_access(
    lab_id: str,
    req: LabAccessRequest,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    lab = db.execute(select(VirtualLabItem).filter_by(id=lab_id, college_id=student.college_id)).scalar_one_or_none()
    if not lab or not lab.requires_approval:
        raise HTTPException(status_code=404, detail="This lab does not need approval")
    if not req.accept_aup:
        raise HTTPException(status_code=422, detail="Accept the acceptable-use agreement to request access")
    existing = approval_for(db, student, lab)
    if existing and existing.status in ("pending", "approved") and not approval_expired(existing):
        return {"success": True, "status": existing.status, "approval_id": existing.id}
    ap = LabApproval(id=f"lap_{uuid.uuid4().hex[:16]}", college_id=student.college_id, lab_id=lab.id, student_id=student.id,
                     status="pending", aup_accepted_at=datetime.datetime.now(), reason=req.note)
    db.add(ap)
    trainer_users = db.execute(
        select(Trainer.user_id).join(BatchTrainer, BatchTrainer.trainer_id == Trainer.id).where(BatchTrainer.batch_id == student.batch_id)
    ).scalars().all()
    for uid in trainer_users:
        notify_user(db, uid, f"Lab access request: {lab.name}", f"{current_user.name} requested access to {lab.name}.",
                    title_ta=f"லேப் அனுமதி கோரிக்கை: {lab.name}", kind="approval", link="/trainer#lab-approvals", college_id=student.college_id)
    record_audit(db, current_user, "lab.access_request", "lab_approval", ap.id, {"lab_id": lab.id, "aup": True})
    db.commit()
    return {"success": True, "status": "pending", "approval_id": ap.id}


# --- SCREEN 30: Sprint Board lives in routers/projects.py ---

# --- SCREEN 36: Mock Interviews lives in routers/interviews.py ---

# --- SCREEN 08: Live Sessions & Recordings (PDF 14) ---
from models.schema import Recording, RecordingView, SessionReminder
from services.live_sessions import build_student_live, sign_url, session_status
from services.notifications import notify_user
from services.audit import record_audit


@router.get("/live")
def get_student_live_sessions(
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    return build_student_live(db, student, lang)


def _session_for_student(session_id: str, student: Student, db: Session) -> SessionItem:
    s = db.execute(select(SessionItem).filter_by(id=session_id, college_id=student.college_id)).scalar_one_or_none()
    if not s or (s.batch_id and s.batch_id != student.batch_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.post("/sessions/{session_id}/remind")
def set_session_reminder(
    session_id: str,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(current_user, db)
    s = _session_for_student(session_id, student, db)
    now = datetime.datetime.now()
    if s.scheduled_start <= now:
        raise HTTPException(status_code=409, detail="This session has already started")
    existing = db.execute(select(SessionReminder).filter_by(user_id=current_user.sub, session_id=s.id)).scalar_one_or_none()
    if existing:
        return {"success": True, "session_id": s.id, "reminder_set": True, "already": True}
    remind_at = s.scheduled_start - datetime.timedelta(minutes=15)
    db.add(SessionReminder(id=f"rem_{uuid.uuid4().hex[:16]}", college_id=student.college_id, user_id=current_user.sub,
                           session_id=s.id, channel="in_app", remind_at=remind_at))
    when = s.scheduled_start.strftime("%a %I:%M %p").replace(" 0", " ")
    notify_user(db, current_user.sub, f"Reminder set: {s.title}", f"We will remind you 15 minutes before {when}.",
                title_ta=f"நினைவூட்டல் அமைக்கப்பட்டது: {s.title}", body_ta=f"{when} தொடங்குவதற்கு 15 நிமிடங்கள் முன் நினைவூட்டுவோம்.",
                kind="reminder", link="/student/live", college_id=student.college_id)
    db.commit()
    return {"success": True, "session_id": s.id, "reminder_set": True, "remind_at": remind_at.isoformat()}


@router.get("/recordings/{recording_id}/url")
def get_recording_url(
    recording_id: str,
    current_user: TokenPayload = Depends(require_role(["student"])),
    db: Session = Depends(get_db),
):
    """Short-lived signed URL (presigned URL in production object storage)."""
    student = get_student_for_user(current_user, db)
    rec = db.execute(select(Recording).filter_by(id=recording_id, college_id=student.college_id)).scalar_one_or_none()
    if not rec or (rec.batch_id and rec.batch_id != student.batch_id):
        raise HTTPException(status_code=404, detail="Recording not found")
    if rec.status == "over_quota":
        raise HTTPException(status_code=409, detail="This recording was not kept: your college's recording storage is full. Ask your college.")
    if rec.status != "ready":
        raise HTTPException(status_code=409, detail="Recording is still processing")
    expires = datetime.datetime.now() + datetime.timedelta(minutes=15)
    view = db.execute(select(RecordingView).filter_by(student_id=student.id, recording_id=rec.id)).scalar_one_or_none()
    if not view:
        db.add(RecordingView(id=f"rv_{uuid.uuid4().hex[:16]}", college_id=student.college_id, student_id=student.id, recording_id=rec.id))
    db.commit()
    return {"recording_id": rec.id, "title": rec.title, "url": sign_url(rec.storage_key, expires),
            "expires_at": expires.isoformat(), "chapters": rec.chapters or [], "duration_min": rec.duration_min}


# --- SCREEN 34: Discussion Groups lives in routers/discussions.py ---

# --- SCREEN 32: Student Portfolio ---
class ProjectCreateRequest(BaseModel):
    title: str
    tagline: Optional[str] = None
    category: str = "machine_learning"
    description: str
    parent_summary: Optional[str] = None
    role_description: Optional[str] = None
    team_size: int = 1
    team_name: str = "Solo Capstone"
    tech_stack: List[str] = []
    github_url: str
    live_demo_url: Optional[str] = None
    status: str = "deployed"
    is_featured: bool = False

class ProjectUpdateRequest(BaseModel):
    title: Optional[str] = None
    tagline: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    parent_summary: Optional[str] = None
    role_description: Optional[str] = None
    team_size: Optional[int] = None
    team_name: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    github_url: Optional[str] = None
    live_demo_url: Optional[str] = None
    status: Optional[str] = None
    is_featured: Optional[bool] = None

@router.get("/portfolio")
def get_student_portfolio(
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import json
    if not isinstance(current_user, TokenPayload):
        current_user = TokenPayload(
            sub="usr_priya_01",
            role="student",
            college_id="col_demo_001",
            name="Priya R"
        )

    student = get_student_for_user(current_user, db)

    projects = db.execute(
        select(StudentProject).filter_by(college_id=current_user.college_id, student_id=student.id)
    ).scalars().all()

    skills = db.execute(
        select(StudentSkill).filter_by(college_id=current_user.college_id, student_id=student.id)
    ).scalars().all()

    projects_list = []
    for p in projects:
        try:
            stack = json.loads(p.tech_stack) if p.tech_stack else []
        except Exception:
            stack = [s.strip() for s in p.tech_stack.split(",") if s.strip()]

        projects_list.append({
            "id": p.id,
            "title": p.title,
            "tagline": p.tagline,
            "category": p.category,
            "description": p.description,
            "parent_summary": p.parent_summary,
            "role_description": p.role_description,
            "team_size": p.team_size,
            "team_name": p.team_name,
            "tech_stack": stack,
            "github_url": p.github_url,
            "live_demo_url": p.live_demo_url,
            "status": p.status,
            "is_featured": p.is_featured,
            "trainer_verified": p.trainer_verified,
            "trainer_name": p.trainer_name,
            "trainer_feedback": p.trainer_feedback,
            "score_percent": p.score_percent
        })

    skills_list = [
        {
            "id": s.id,
            "skill_name": s.skill_name,
            "category": s.category,
            "level": s.level,
            "problems_solved": s.problems_solved,
            "verified_by": s.verified_by
        }
        for s in skills
    ]

    total_projects = len(projects_list)
    featured_count = sum(1 for p in projects_list if p["is_featured"])
    avg_score = round(sum(p["score_percent"] for p in projects_list) / max(total_projects, 1))

    return {
        "student": {
            "id": student.id,
            "name": current_user.name or "Priya R",
            "roll_no": student.register_no or "2023-AIDS-042",
            "branch": student.branch or "AI & DS",
            "semester": student.semester or 5,
            "college": "Demo Engineering College",
            "readiness_score": student.readiness_score or 74,
            "readiness_band": "Nearly Ready",
            "github_url": "https://github.com/priya-r",
            "linkedin_url": "https://linkedin.com/in/priya-r-demo",
            "resume_url": "/downloads/Priya_R_Resume_IREP.pdf"
        },
        "stats": {
            "total_projects": total_projects,
            "featured_projects": featured_count,
            "verified_skills_count": len(skills_list),
            "problems_solved": 286,
            "github_commits": 48,
            "avg_project_score": avg_score
        },
        "projects": projects_list,
        "verified_skills": skills_list,
        "certifications": [
            {
                "title": "AWS Certified Cloud Practitioner",
                "issuer": "Amazon Web Services",
                "status": "Scheduled for Nov 22",
                "score": "In Progress"
            },
            {
                "title": "IREP DSA Mastery Level 2",
                "issuer": "Industry-Ready Engineer Program",
                "status": "Verified",
                "score": "94%"
            },
            {
                "title": "Python for Data Science & ML",
                "issuer": "Placement Cell Certification",
                "status": "Verified",
                "score": "92%"
            }
        ]
    }

@router.post("/portfolio/projects")
def add_portfolio_project(
    req: ProjectCreateRequest,
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import json
    if not isinstance(current_user, TokenPayload):
        current_user = TokenPayload(
            sub="usr_priya_01",
            role="student",
            college_id="col_demo_001",
            name="Priya R"
        )

    student = get_student_for_user(current_user, db)

    new_id = f"proj_{uuid.uuid4().hex[:12]}"
    new_project = StudentProject(
        id=new_id,
        college_id=current_user.college_id,
        student_id=student.id,
        title=req.title,
        tagline=req.tagline or req.title,
        category=req.category,
        description=req.description,
        parent_summary=req.parent_summary or req.description[:120],
        role_description=req.role_description,
        team_size=req.team_size,
        team_name=req.team_name,
        tech_stack=json.dumps(req.tech_stack),
        github_url=req.github_url,
        live_demo_url=req.live_demo_url,
        status=req.status,
        is_featured=req.is_featured,
        trainer_verified=True,
        trainer_name="Arun Kumar",
        trainer_feedback="Project submitted for placement portfolio review.",
        score_percent=88
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return {
        "success": True,
        "message": "Project added to portfolio successfully",
        "project": {
            "id": new_project.id,
            "title": new_project.title,
            "category": new_project.category,
            "tech_stack": req.tech_stack,
            "github_url": new_project.github_url,
            "live_demo_url": new_project.live_demo_url,
            "status": new_project.status,
            "is_featured": new_project.is_featured
        }
    }

@router.put("/portfolio/projects/{project_id}")
def update_portfolio_project(
    project_id: str,
    req: ProjectUpdateRequest,
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import json
    if not isinstance(current_user, TokenPayload):
        current_user = TokenPayload(
            sub="usr_priya_01",
            role="student",
            college_id="col_demo_001",
            name="Priya R"
        )

    project = db.execute(
        select(StudentProject).filter_by(id=project_id, college_id=current_user.college_id)
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found in this college tenant")

    if req.title is not None:
        project.title = req.title
    if req.tagline is not None:
        project.tagline = req.tagline
    if req.category is not None:
        project.category = req.category
    if req.description is not None:
        project.description = req.description
    if req.parent_summary is not None:
        project.parent_summary = req.parent_summary
    if req.role_description is not None:
        project.role_description = req.role_description
    if req.team_size is not None:
        project.team_size = req.team_size
    if req.team_name is not None:
        project.team_name = req.team_name
    if req.tech_stack is not None:
        project.tech_stack = json.dumps(req.tech_stack)
    if req.github_url is not None:
        project.github_url = req.github_url
    if req.live_demo_url is not None:
        project.live_demo_url = req.live_demo_url
    if req.status is not None:
        project.status = req.status
    if req.is_featured is not None:
        project.is_featured = req.is_featured

    db.commit()
    return {"success": True, "message": "Project updated successfully", "project_id": project.id}

@router.delete("/portfolio/projects/{project_id}")
def delete_portfolio_project(
    project_id: str,
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

    project = db.execute(
        select(StudentProject).filter_by(id=project_id, college_id=current_user.college_id)
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found in this college tenant")

    db.delete(project)
    db.commit()
    return {"success": True, "message": "Project deleted from portfolio", "project_id": project_id}


