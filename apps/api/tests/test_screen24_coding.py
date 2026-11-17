import sys
from pathlib import Path

# Add apps/api to sys.path
api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi import HTTPException
from core.database import SessionLocal
from core.security import TokenPayload
from routers import student
from models.schema import CodingProblem, CodingSubmission, CodingHintUsage

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def student_user():
    return TokenPayload(
        sub="usr_priya_01",
        email="priya.r@demo.edu",
        role="student",
        college_id="col_demo_001",
        name="Priya R",
        avatar="PR"
    )

@pytest.fixture
def other_tenant_user():
    return TokenPayload(
        sub="usr_other_01",
        email="other@other.edu",
        role="student",
        college_id="col_other_999",
        name="Other Student",
        avatar="OS"
    )

def test_get_coding_problem_success(db, student_user):
    """Test retrieving existing problem with tenant isolation."""
    prob = student.get_coding_problem("prob_connected_components", current_user=student_user, db=db)
    assert prob["id"] == "prob_connected_components"
    assert "Connected Components" in prob["title"]
    assert prob["difficulty"] == "Medium"
    assert prob["topic"] == "Union-Find"
    assert "starter_codes" in prob
    assert "python" in prob["starter_codes"]
    assert "java" in prob["starter_codes"]
    assert "cpp" in prob["starter_codes"]
    assert "javascript" in prob["starter_codes"]
    assert "ai_reviewer" in prob
    assert len(prob["ai_reviewer"]["hints"]) == 3
    assert len(prob["ai_reviewer"]["revealed_hints"]) >= 1

def test_get_coding_problem_tenant_isolation(db, other_tenant_user):
    """Test that student from different college cannot access another college's problem."""
    with pytest.raises(HTTPException) as exc_info:
        student.get_coding_problem("prob_connected_components", current_user=other_tenant_user, db=db)
    assert exc_info.value.status_code == 404

def test_get_coding_problem_not_found(db, student_user):
    """Test 404 for nonexistent problem ID."""
    with pytest.raises(HTTPException) as exc_info:
        student.get_coding_problem("prob_non_existent_999", current_user=student_user, db=db)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()

def test_run_sample_code_success(db, student_user):
    """Test running sample code cases."""
    req = student.CodeRunRequest(
        code="class Solution:\n    def countComponents(self, n, edges):\n        return n",
        language="python"
    )
    result = student.run_code_sample("prob_connected_components", req=req, current_user=student_user, db=db)
    assert result["status"] == "Passed"
    assert result["runtime_ms"] > 0
    assert result["memory_mb"] > 0
    assert len(result["cases"]) == 2

def test_run_sample_code_empty_code(db, student_user):
    """Test compile error on empty code."""
    req = student.CodeRunRequest(code="", language="python")
    result = student.run_code_sample("prob_connected_components", req=req, current_user=student_user, db=db)
    assert result["status"] == "Compile Error"

def test_submit_code_persistence_and_scoring(db, student_user):
    """Test submitting solution, saving submission, and updating student readiness score."""
    import datetime
    from sqlalchemy import update
    # Reset cooldown so test run isn't blocked by rate limiter
    db.execute(
        update(CodingSubmission)
        .filter_by(student_id="std_priya_01")
        .values(created_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=30))
    )
    db.commit()

    req = student.CodeSubmitRequest(
        code="class Solution:\n    def countComponents(self, n: int, edges: list[list[int]]) -> int:\n        return n - len(edges)",
        language="python"
    )
    result = student.submit_code("prob_connected_components", req=req, current_user=student_user, db=db)
    assert result["status"] == "Accepted"
    assert result["tests_passed"] == 18
    assert result["tests_total"] == 18
    # Allowlist model: only sample cases appear in result["cases"] (Condition 4 & 5)
    assert len(result["cases"]) == 2
    assert "18 / 18 hidden tests passed" in result["message"]

    # Verify submission was saved in database
    sub = db.query(CodingSubmission).filter_by(
        problem_id="prob_connected_components",
        student_id=student_user.sub
    ).order_by(CodingSubmission.created_at.desc()).first()
    assert sub is not None
    assert sub.status == "Accepted"
    assert sub.tests_passed == 18

def test_request_hint_quota(db, student_user):
    """Test requesting hints with quota progression."""
    req = student.HintRequest(current_count=1)
    res = student.request_coding_hint("prob_connected_components", req=req, current_user=student_user, db=db)
    assert "hint" in res
    assert res["max_hints"] == 3
    assert res["hints_used"] <= 3

def test_list_coding_problems(db, student_user):
    """Test listing problems for student's tenant."""
    res = student.list_coding_problems(current_user=student_user, db=db)
    assert "problems" in res
    assert len(res["problems"]) >= 1
    assert any(p["id"] == "prob_connected_components" for p in res["problems"])
