import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

# ---------------------------------------------------------------------------
# TEST CASES SCHEMAS
# ---------------------------------------------------------------------------

class TestCaseSamplePublic(BaseModel):
    """Student-facing sample test case representation.
    Only sample cases (is_hidden == False) are serialized through this schema.
    """
    __test__ = False
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: Optional[str] = None
    test_order: int
    input_data: str
    expected_output: str
    explanation: Optional[str] = None


class TestCaseInternal(BaseModel):
    """Server-internal / Trainer-authoring representation of a test case.
    Includes sensitive hidden test inputs and expected outputs.
    MUST NEVER be exposed to student endpoints.
    """
    __test__ = False
    model_config = ConfigDict(from_attributes=True)

    id: str
    problem_id: str
    test_order: int
    is_hidden: bool
    name: Optional[str] = None
    input_data: str
    expected_output: str
    explanation: Optional[str] = None
    created_at: Optional[datetime.datetime] = None


# ---------------------------------------------------------------------------
# SUBMISSION RESULTS SCHEMAS
# ---------------------------------------------------------------------------

class SubmissionResultPublic(BaseModel):
    """Student-facing test execution outcome for sample test cases.
    Guarantees hidden test inputs and expected outputs are NEVER exposed.
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    test_case_id: Optional[str] = None
    name: str = "Test Case"
    status: str
    runtime_ms: Optional[int] = None
    memory_mb: Optional[float] = None
    is_hidden: bool = False
    actual_output: Optional[str] = None
    error_output: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sanitize_result(cls, data: Any):
        if hasattr(data, "__dict__"):
            # ORM Model instance or DTO
            tc = getattr(data, "test_case", None)
            is_hidden = getattr(data, "is_hidden", getattr(tc, "is_hidden", False))
            name = getattr(data, "name", getattr(tc, "name", "Test Case")) or "Test Case"
            actual = None if is_hidden else getattr(data, "actual_output", None)
            raw_err = getattr(data, "error_output", None)
            err = "Test execution failed on hidden test." if (is_hidden and raw_err) else raw_err
            return {
                "id": getattr(data, "id", None),
                "test_case_id": getattr(data, "test_case_id", None),
                "name": name,
                "status": data.status,
                "runtime_ms": data.runtime_ms,
                "memory_mb": data.memory_mb,
                "is_hidden": is_hidden,
                "actual_output": actual,
                "error_output": err,
            }
        elif isinstance(data, dict):
            if data.get("is_hidden"):
                data["actual_output"] = None
                if data.get("error_output"):
                    data["error_output"] = "Test execution failed on hidden test."
        return data


class SubmissionResultInternal(BaseModel):
    """Server-internal evaluation result with full raw diffs for trainer inspection."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    test_case_id: str
    status: str
    runtime_ms: Optional[int] = None
    memory_mb: Optional[float] = None
    actual_output: Optional[str] = None
    expected_output: Optional[str] = None
    error_output: Optional[str] = None


# ---------------------------------------------------------------------------
# CODING PROBLEMS SCHEMAS
# ---------------------------------------------------------------------------

class CodingProblemPublic(BaseModel):
    """Student-facing problem details.
    Contains statement, constraints, starter codes, and ONLY sample test cases.
    Hidden test cases are excluded entirely.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: Optional[str] = None
    title: str
    difficulty: str
    topic: str
    company_tags: Optional[str] = ""
    week_info: Optional[str] = ""
    statement: str
    example_input: Optional[str] = ""
    example_output: Optional[str] = ""
    constraints: str
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    starter_codes: Dict[str, str] = Field(default_factory=dict)
    starter_code: Optional[str] = ""
    sample_test_cases: List[TestCaseSamplePublic] = Field(default_factory=list)
    total_tests_count: int = 0
    sample_tests_count: int = 0
    trainer_notes: Optional[str] = None
    trainer_author: Optional[str] = "Arun K."
    ai_reviewer: Optional[Dict[str, Any]] = None
    last_submission: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def filter_hidden_tests(cls, data: Any):
        if hasattr(data, "__dict__"):
            test_cases = getattr(data, "test_cases", []) or []
            sample_cases = [tc for tc in test_cases if not getattr(tc, "is_hidden", False)]
            return {
                "id": data.id,
                "slug": getattr(data, "slug", None),
                "title": data.title,
                "difficulty": data.difficulty,
                "topic": data.topic,
                "company_tags": getattr(data, "company_tags", "") or "",
                "week_info": getattr(data, "week_info", "") or "",
                "statement": data.statement,
                "example_input": getattr(data, "example_input", "") or "",
                "example_output": getattr(data, "example_output", "") or "",
                "constraints": data.constraints,
                "time_limit_ms": getattr(data, "time_limit_ms", 2000) or 2000,
                "memory_limit_mb": getattr(data, "memory_limit_mb", 256) or 256,
                "starter_codes": getattr(data, "starter_codes", {}) or {},
                "starter_code": getattr(data, "starter_code", "") or "",
                "sample_test_cases": sample_cases,
                "total_tests_count": len(test_cases),
                "sample_tests_count": len(sample_cases),
                "trainer_notes": getattr(data, "trainer_notes", None),
                "trainer_author": getattr(data, "trainer_author", "Arun K."),
                "ai_reviewer": getattr(data, "ai_reviewer", None),
                "last_submission": getattr(data, "last_submission", None)
            }
        return data


class CodingProblemInternal(BaseModel):
    """Internal / Authoring representation of a coding problem with all test cases."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    college_id: str
    slug: Optional[str] = None
    title: str
    difficulty: str
    topic: str
    company_tags: str
    week_info: str
    statement: str
    constraints: str
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    starter_codes: Dict[str, str] = Field(default_factory=dict)
    test_cases: List[TestCaseInternal] = Field(default_factory=list)
    trainer_notes: Optional[str] = None
    trainer_author: str = "Arun K."
    created_at: Optional[datetime.datetime] = None


# ---------------------------------------------------------------------------
# SUBMISSION INPUT / OUTPUT SCHEMAS
# ---------------------------------------------------------------------------

class CodeRunRequest(BaseModel):
    """Payload sent by student to run code against sample cases."""
    language: str = Field(default="python", pattern="^(python|java|cpp|javascript)$")
    code: str = Field(default="", max_length=65536)


class CodeSubmitRequest(BaseModel):
    """Payload sent by student to officially submit code for grading."""
    language: str = Field(default="python", pattern="^(python|java|cpp|javascript)$")
    code: str = Field(..., min_length=1, max_length=65536)


class HintRequest(BaseModel):
    """Payload to request the next progressive hint."""
    current_count: int = Field(default=1, ge=1, le=3)


class CodeRunResponse(BaseModel):
    """Student response when running against sample test cases."""
    model_config = ConfigDict(from_attributes=True)

    status: str
    runtime_ms: int = 0
    memory_mb: float = 0.0
    error_message: Optional[str] = None
    cases: List[SubmissionResultPublic] = Field(default_factory=list)


class CodingSubmissionPublic(BaseModel):
    """Student-facing allowlist response for official submission (Condition 4 & 5).
    Guarantees:
    - Hidden results use a dedicated allowlist: pass or fail and the total count only.
    - No stdout, stderr, input, expected output, test index or per-test timing for hidden tests.
    - Only sample test cases appear in the cases list.
    - Message presents summary count only (e.g., '18 / 18 hidden tests passed' or '17 / 18 tests passed').
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    problem_id: str
    student_id: str
    language: str
    status: str
    runtime_ms: Optional[int] = None
    memory_mb: Optional[float] = None
    tests_passed: int = 0
    tests_total: int = 0
    hints_used: int = 0
    message: str = ""
    cases: List[SubmissionResultPublic] = Field(default_factory=list)
    created_at: datetime.datetime

    @model_validator(mode="before")
    @classmethod
    def enforce_hidden_allowlist(cls, data: Any):
        if hasattr(data, "__dict__"):
            results = getattr(data, "results", []) or []
            # Allowlist: ONLY sample test cases are exposed in the cases list
            sample_results = []
            for r in results:
                tc = getattr(r, "test_case", None)
                is_hidden = getattr(r, "is_hidden", getattr(tc, "is_hidden", False))
                if not is_hidden:
                    sample_results.append(r)

            tests_passed = getattr(data, "tests_passed", 0)
            tests_total = getattr(data, "tests_total", 0)
            status = getattr(data, "status", "Pending")
            msg = getattr(data, "message", None)
            if not msg:
                if status == "Accepted":
                    msg = f"{tests_passed} / {tests_total} hidden tests passed"
                else:
                    msg = f"{tests_passed} / {tests_total} tests passed"

            return {
                "id": data.id,
                "problem_id": data.problem_id,
                "student_id": data.student_id,
                "language": data.language,
                "status": status,
                "runtime_ms": data.runtime_ms,
                "memory_mb": data.memory_mb,
                "tests_passed": tests_passed,
                "tests_total": tests_total,
                "hints_used": getattr(data, "hints_used", 0),
                "message": msg,
                "cases": sample_results,
                "created_at": data.created_at,
            }
        elif isinstance(data, dict):
            # Dict input
            raw_cases = data.get("cases") or data.get("results") or []
            sample_cases = [c for c in raw_cases if not (c.get("is_hidden") if isinstance(c, dict) else getattr(c, "is_hidden", False))]
            data["cases"] = sample_cases
            if "message" not in data or not data["message"]:
                p = data.get("tests_passed", 0)
                t = data.get("tests_total", 0)
                if data.get("status") == "Accepted":
                    data["message"] = f"{p} / {t} hidden tests passed"
                else:
                    data["message"] = f"{p} / {t} tests passed"
        return data


class CodingSubmissionInternal(BaseModel):
    """Server-internal representation of a submission with full results for trainer/evaluator."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    college_id: str
    problem_id: str
    student_id: str
    language: str
    code: str
    status: str
    runtime_ms: Optional[int] = None
    memory_mb: Optional[float] = None
    tests_passed: int = 0
    tests_total: int = 0
    hints_used: int = 0
    error_message: Optional[str] = None
    results: List[SubmissionResultInternal] = Field(default_factory=list)
    created_at: datetime.datetime
