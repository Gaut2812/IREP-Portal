import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parents[3])
api_root = str(Path(__file__).resolve().parents[1])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi import HTTPException
from core.database import SessionLocal
from routers import student
from routers.student import BatchAnswersRequest, ProctorEventRequest, SubmitTestRequest
from core.security import TokenPayload
from models.schema import TestAttempt, AttemptAnswer, ProctorEvent, TopicScore

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def student_user():
    return TokenPayload(
        sub="usr_priya_01",
        email="priya.r@demo.edu",
        role="student",
        college_id="col_demo_001",
        name="Priya R"
    )

@pytest.fixture
def non_student_user():
    return TokenPayload(
        sub="usr_ramesh_01",
        email="ramesh.k@example.com",
        role="parent",
        college_id="col_demo_001",
        name="Mr. Ramesh K"
    )

def test_get_practice_test_anti_cheat_and_tenant(db_session, student_user):
    res = student.get_practice_test("test_service_aptitude", current_user=student_user, db=db_session)
    assert res["id"] == "test_service_aptitude"
    assert "Service Company Pattern" in res["title"]
    assert len(res["questions"]) == 30
    assert len(res["sections"]) == 3
    
    # Anti-cheating verification: correct_option and explanation must NOT be exposed
    for q in res["questions"]:
        assert "correct_option" not in q
        assert "explanation" not in q
        assert "options" in q
        assert "A" in q["options"]
        assert "B" in q["options"]

def test_start_and_resume_attempt(db_session, student_user):
    att = student.start_or_resume_attempt("test_service_aptitude", current_user=student_user, db=db_session)
    assert att["status"] == "in_progress"
    assert "attempt_id" in att
    assert att["time_remaining_sec"] > 0
    assert "ends_at" in att

def test_batch_save_answers(db_session, student_user):
    att = student.start_or_resume_attempt("test_service_aptitude", current_user=student_user, db=db_session)
    attempt_id = att["attempt_id"]
    
    req = BatchAnswersRequest(
        answers={"12": "B", "1": "A", "2": "C"},
        marked_for_review=[7, 14]
    )
    save_res = student.batch_save_answers(attempt_id, req, current_user=student_user, db=db_session)
    assert save_res["success"] is True
    assert save_res["saved_count"] == 3

    # Check persistence in database
    answers = db_session.query(AttemptAnswer).filter_by(attempt_id=attempt_id).all()
    q12 = next(a for a in answers if a.question_number == 12)
    assert q12.selected_option == "B"

def test_proctor_event_logging(db_session, student_user):
    att = student.start_or_resume_attempt("test_service_aptitude", current_user=student_user, db=db_session)
    attempt_id = att["attempt_id"]

    req = ProctorEventRequest(
        event_type="tab_switch",
        details="Student switched away from practice test tab"
    )
    event_res = student.log_proctor_event(attempt_id, req, current_user=student_user, db=db_session)
    assert event_res["success"] is True
    assert event_res["event_id"].startswith("proc_")

    logged_event = db_session.query(ProctorEvent).filter_by(id=event_res["event_id"]).first()
    assert logged_event is not None
    assert logged_event.event_type == "tab_switch"

def test_submit_and_scoring(db_session, student_user):
    att = student.start_or_resume_attempt("test_service_aptitude", current_user=student_user, db=db_session)
    attempt_id = att["attempt_id"]

    sub_req = SubmitTestRequest(
        answers={"12": "B"},
        marked_for_review=[12]
    )
    res = student.submit_practice_test(attempt_id, sub_req, current_user=student_user, db=db_session)
    assert res["success"] is True
    assert "score" in res
    assert res["total"] == 30
    assert "accuracy" in res
    assert "time_taken" in res
    assert len(res["section_analysis"]) == 3
    assert len(res["questions_review"]) == 30

    # Review mode exposes explanation and correct_option
    q12_review = next(q for q in res["questions_review"] if q["number"] == 12)
    assert q12_review["selected_option"] == "B"
    assert q12_review["correct_option"] == "B"
    assert q12_review["is_correct"] is True
    assert "explanation" in q12_review and q12_review["explanation"] is not None

def test_get_attempt_result(db_session, student_user):
    att = student.start_or_resume_attempt("test_service_aptitude", current_user=student_user, db=db_session)
    attempt_id = att["attempt_id"]
    
    # Submitting first
    student.submit_practice_test(attempt_id, SubmitTestRequest(), current_user=student_user, db=db_session)
    
    result = student.get_attempt_result(attempt_id, current_user=student_user, db=db_session)
    assert result["success"] is True
    assert result["attempt_id"] == attempt_id
    assert len(result["questions_review"]) == 30

def test_prevent_modifying_submitted_attempt(db_session, student_user):
    att = student.start_or_resume_attempt("test_service_aptitude", current_user=student_user, db=db_session)
    attempt_id = att["attempt_id"]
    
    # Submit attempt
    student.submit_practice_test(attempt_id, SubmitTestRequest(), current_user=student_user, db=db_session)

    # Attempting to save answers after submission must raise HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        student.batch_save_answers(
            attempt_id,
            BatchAnswersRequest(answers={"1": "A"}),
            current_user=student_user,
            db=db_session
        )
    assert exc_info.value.status_code == 400
