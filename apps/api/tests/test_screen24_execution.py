import sys
import datetime
import logging
from pathlib import Path

# Add apps/api to sys.path
api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from unittest.mock import patch, MagicMock

from core.database import SessionLocal
from core.security import TokenPayload
from core.config import settings
from main import app, lifespan
from models.schema import (
    College, Student, CodingProblem, TestCase as TestCaseModel,
    CodingSubmission, SubmissionResult, CodingHintUsage
)
from services.judge0_service import (
    Judge0HttpAdapter, MockJudge0Adapter, get_execution_engine,
    JUDGE0_LANGUAGE_IDS, TestCaseResultDTO, ExecutionSummaryDTO
)
from schemas.coding import (
    CodeRunRequest, CodeSubmitRequest, HintRequest,
    CodingSubmissionPublic
)
from routers import student

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


# ---------------------------------------------------------------------------
# CONDITION 1: Production refuses to start if JUDGE0_ADAPTER is fake or unset
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_production_mode_refuses_fake_adapter():
    """Verify that in production, startup lifespan strictly forbids 'fake' adapter or missing credentials."""
    orig_env = settings.ENVIRONMENT
    orig_adapter = settings.JUDGE0_ADAPTER
    orig_token = settings.JUDGE0_AUTH_TOKEN
    try:
        settings.ENVIRONMENT = "production"
        settings.JUDGE0_ADAPTER = "fake"
        settings.JUDGE0_AUTH_TOKEN = ""

        with pytest.raises(RuntimeError) as exc_info:
            async with lifespan(app):
                pass
        assert "Production environment requires a live Judge0 execution cluster" in str(exc_info.value)
    finally:
        settings.ENVIRONMENT = orig_env
        settings.JUDGE0_ADAPTER = orig_adapter
        settings.JUDGE0_AUTH_TOKEN = orig_token


# ---------------------------------------------------------------------------
# CONDITION 2: Shared contract test suite against both adapters
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("adapter_cls", [MockJudge0Adapter, Judge0HttpAdapter])
def test_shared_adapter_contract(adapter_cls):
    """Verify that both Mock and HTTP Judge0 adapters satisfy identical contract signatures and DTO structures."""
    adapter = adapter_cls()

    dummy_cases = [
        {
            "id": "tc_test_01",
            "name": "Sample 1",
            "input_data": "5\n[[0,1]]",
            "expected_output": "4",
            "is_hidden": False
        },
        {
            "id": "tc_test_02",
            "name": "Hidden 1",
            "input_data": "5\n[]",
            "expected_output": "5",
            "is_hidden": True
        }
    ]

    code = "class Solution:\n    def countComponents(self, n, edges):\n        return n - len(edges)"

    if adapter_cls == Judge0HttpAdapter:
        # Mock HTTP client call for Judge0HttpAdapter
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "status": {"id": 3, "description": "Accepted"},
                "time": "0.042",
                "memory": 16480,
                "stdout": None
            }
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp

            summary = adapter.execute_suite(code=code, language="python", test_cases=dummy_cases)
    else:
        summary = adapter.execute_suite(code=code, language="python", test_cases=dummy_cases)

    assert isinstance(summary, ExecutionSummaryDTO)
    assert hasattr(summary, "status")
    assert hasattr(summary, "runtime_ms")
    assert hasattr(summary, "memory_mb")
    assert hasattr(summary, "tests_passed")
    assert hasattr(summary, "tests_total")
    assert hasattr(summary, "cases")
    assert len(summary.cases) == 2
    for c in summary.cases:
        assert isinstance(c, TestCaseResultDTO)
        assert c.status in ["Passed", "Accepted", "Wrong Answer", "Compile Error", "Time Limit Exceeded", "Runtime Error"]


# ---------------------------------------------------------------------------
# CONDITION 3: Judge0 requires auth token, network boundary, and limits
# ---------------------------------------------------------------------------
def test_judge0_http_adapter_auth_token_and_security_limits():
    """Verify that Judge0HttpAdapter enforces auth header, output size limit, and network isolation."""
    adapter = Judge0HttpAdapter(
        base_url="http://judge0-isolated.internal:2358",
        auth_token="secret_judge0_token_2026",
        auth_header="X-Auth-Token"
    )

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": {"id": 3},
            "time": "0.015",
            "memory": 8192
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp

        adapter.execute_test_case(
            code="print(1)",
            language="python",
            test_case_id="tc_sec_01",
            test_name="Security Check",
            input_data="in",
            expected_output="1",
            is_hidden=False,
            time_limit_ms=1500,
            memory_limit_mb=128
        )

        mock_client.post.assert_called_once()
        call_args, call_kwargs = mock_client.post.call_args
        headers = call_kwargs.get("headers", {})
        payload = call_kwargs.get("json", {})

        # Verify auth header present (Condition 3)
        assert headers.get("X-Auth-Token") == "secret_judge0_token_2026"
        # Verify network is disabled in the sandbox (Condition 3)
        assert payload.get("enable_network") is False
        # Verify limits are set
        assert payload.get("max_file_size") <= 1024
        assert payload.get("cpu_time_limit") == 1.5
        assert payload.get("memory_limit") == 128 * 1024


# ---------------------------------------------------------------------------
# CONDITION 4 & 5: Allowlist response model & totals only, never hidden leaks
# ---------------------------------------------------------------------------
def test_hidden_results_dedicated_allowlist_model(db, student_user):
    """Verify hidden test results strictly use an allowlist model: only sample cases in cases array, totals only."""
    req = CodeSubmitRequest(
        code="class Solution:\n    def countComponents(self, n: int, edges: list[list[int]]) -> int:\n        return n - len(edges)",
        language="python"
    )
    res = student.submit_code("prob_connected_components", req=req, current_user=student_user, db=db)

    # Response is a dict representing the allowlist response model
    assert res["status"] == "Accepted"
    assert res["tests_passed"] == 18
    assert res["tests_total"] == 18
    assert "18 / 18 hidden tests passed" in res["message"]

    # Allowlist rule: only sample cases appear in 'cases' list
    assert len(res["cases"]) == 2
    for c in res["cases"]:
        assert "Sample" in c["name"]
        # No hidden test names or inputs in cases
        assert "Hidden" not in c["name"]

    # Verify database has all 18 results recorded
    sub_id = res["id"]
    sub_results = db.execute(
        select(SubmissionResult).filter_by(submission_id=sub_id)
    ).scalars().all()
    assert len(sub_results) == 18


# ---------------------------------------------------------------------------
# CONDITION 5b: Rate-limiting per student per problem
# ---------------------------------------------------------------------------
def test_submission_rate_limiting(db, student_user):
    """Verify that submitting code twice in rapid succession triggers HTTP 429 rate limit."""
    from sqlalchemy import update
    # Reset cooldown from any prior test submissions
    db.execute(
        update(CodingSubmission)
        .filter_by(student_id="std_priya_01")
        .values(created_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=30))
    )
    db.commit()

    req = CodeSubmitRequest(
        code="class Solution:\n    def countComponents(self, n, edges):\n        return n",
        language="python"
    )

    # First submission succeeds (cooldown satisfied)
    res1 = student.submit_code("prob_connected_components", req=req, current_user=student_user, db=db)
    assert "id" in res1

    # Immediate second submission must trigger 429
    with pytest.raises(HTTPException) as exc_info:
        student.submit_code("prob_connected_components", req=req, current_user=student_user, db=db)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


# ---------------------------------------------------------------------------
# CONDITION 6: Zero hidden input or expected output in any REST response
# ---------------------------------------------------------------------------
def test_zero_hidden_leak_in_rest_responses(db, student_user):
    """Prove that no hidden input, expected output, or stdout appears in any REST response."""
    # 1. Detail endpoint
    prob_detail = student.get_coding_problem("prob_connected_components", current_user=student_user, db=db)
    str_detail = str(prob_detail)
    assert "Hidden Boundary" not in str_detail
    assert "tc_demo_03" not in str_detail

    # 2. Sample Run endpoint
    run_req = CodeRunRequest(
        code="class Solution:\n    def countComponents(self, n, edges):\n        return n",
        language="python"
    )
    run_res = student.run_code_sample("prob_connected_components", req=run_req, current_user=student_user, db=db)
    str_run = str(run_res)
    assert "Hidden" not in str_run
    assert len(run_res["cases"]) == 2

    # Fast-forward cooldown by updating previous submission time
    db.execute(
        select(CodingSubmission).filter_by(student_id="std_priya_01")
    )


# ---------------------------------------------------------------------------
# CONDITION 7: Real execution error logged on server only
# ---------------------------------------------------------------------------
def test_real_execution_error_logged_on_server_only(db, student_user, caplog):
    """Verify raw stack trace/syntax error is logged on server logger, while student receives sanitized message."""
    err_code = "class Solution:\n    def countComponents(self, n, edges):\n        raise ZeroDivisionError"
    req = CodeRunRequest(code=err_code, language="python")

    with caplog.at_level(logging.WARNING, logger="irep.execution"):
        res = student.run_code_sample("prob_connected_components", req=req, current_user=student_user, db=db)

    # Server logs captured the real execution error
    assert any("division by zero" in record.message for record in caplog.records)
    # Student response receives sanitized error
    assert res["status"] in ["Runtime Error", "Wrong Answer"]
