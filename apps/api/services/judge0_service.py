import os
import sys
import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from core.config import settings

logger = logging.getLogger("irep.execution")
logger.setLevel(logging.INFO)

# Judge0 Standard Language IDs (CE standard)
JUDGE0_LANGUAGE_IDS: Dict[str, int] = {
    "python": 71,       # Python (3.8.1)
    "java": 62,         # Java (OpenJDK 13.0.1)
    "cpp": 54,          # C++ (GCC 9.2.0)
    "javascript": 63    # JavaScript (Node.js 12.14.0)
}

# Judge0 Status IDs
JUDGE0_STATUS_ACCEPTED = 3
JUDGE0_STATUS_WRONG_ANSWER = 4
JUDGE0_STATUS_TIME_LIMIT_EXCEEDED = 5
JUDGE0_STATUS_COMPILATION_ERROR = 6
JUDGE0_STATUS_RUNTIME_ERROR_SIGSEGV = 7
JUDGE0_STATUS_RUNTIME_ERROR_SIGXFSZ = 8
JUDGE0_STATUS_RUNTIME_ERROR_SIGFPE = 9
JUDGE0_STATUS_RUNTIME_ERROR_SIGABRT = 10
JUDGE0_STATUS_RUNTIME_ERROR_NZEC = 11
JUDGE0_STATUS_RUNTIME_ERROR_OTHER = 12
JUDGE0_STATUS_INTERNAL_ERROR = 13
JUDGE0_STATUS_EXEC_FORMAT_ERROR = 14

@dataclass
class TestCaseResultDTO:
    """Individual test case execution result."""
    __test__ = False
    test_case_id: str
    name: str
    status: str            # "Passed", "Wrong Answer", "Time Limit Exceeded", "Compile Error", "Runtime Error"
    runtime_ms: int
    memory_mb: float
    is_hidden: bool
    actual_output: Optional[str] = None
    error_output: Optional[str] = None
    raw_server_error: Optional[str] = None  # Server-only log, never sent to student


@dataclass
class ExecutionSummaryDTO:
    """Aggregated outcome of executing code against a suite of test cases."""
    status: str            # "Accepted", "Wrong Answer", "Compile Error", "Time Limit Exceeded", "Runtime Error"
    runtime_ms: int
    memory_mb: float
    tests_passed: int
    tests_total: int
    cases: List[TestCaseResultDTO] = field(default_factory=list)
    error_message: Optional[str] = None
    raw_server_error: Optional[str] = None


class CodeExecutionEngine(ABC):
    """Abstract interface for code execution engines."""

    @abstractmethod
    def execute_test_case(
        self,
        code: str,
        language: str,
        test_case_id: str,
        test_name: str,
        input_data: str,
        expected_output: str,
        is_hidden: bool = False,
        time_limit_ms: int = 2000,
        memory_limit_mb: int = 256
    ) -> TestCaseResultDTO:
        pass

    @abstractmethod
    def execute_suite(
        self,
        code: str,
        language: str,
        test_cases: List[Any],
        time_limit_ms: int = 2000,
        memory_limit_mb: int = 256
    ) -> ExecutionSummaryDTO:
        pass


def _extract_case_attr(tc: Any, attr: str, default: Any = "") -> Any:
    if isinstance(tc, dict):
        return tc.get(attr, default)
    return getattr(tc, attr, default)

class Judge0HttpAdapter(CodeExecutionEngine):
    """Production execution adapter communicating with live Judge0 REST API."""

    def __init__(self, base_url: Optional[str] = None, auth_token: Optional[str] = None, auth_header: Optional[str] = None):
        self.base_url = (base_url or settings.JUDGE0_URL).rstrip("/")
        self.auth_token = auth_token if auth_token is not None else settings.JUDGE0_AUTH_TOKEN
        self.auth_header = auth_header or settings.JUDGE0_AUTH_HEADER
        self.timeout = 10.0

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.auth_token:
            headers[self.auth_header] = self.auth_token
        return headers

    def execute_test_case(
        self,
        code: str,
        language: str,
        test_case_id: str,
        test_name: str,
        input_data: str,
        expected_output: str,
        is_hidden: bool = False,
        time_limit_ms: int = 2000,
        memory_limit_mb: int = 256
    ) -> TestCaseResultDTO:
        import httpx

        lang_id = JUDGE0_LANGUAGE_IDS.get(language.lower())
        if not lang_id:
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Compile Error",
                runtime_ms=0,
                memory_mb=0.0,
                is_hidden=is_hidden,
                error_output="Unsupported language",
                raw_server_error=f"Language '{language}' not mapped in JUDGE0_LANGUAGE_IDS"
            )

        payload = {
            "source_code": base64.b64encode(code.encode("utf-8")).decode("ascii"),
            "language_id": lang_id,
            "stdin": base64.b64encode(input_data.encode("utf-8")).decode("ascii"),
            "expected_output": base64.b64encode(expected_output.encode("utf-8")).decode("ascii"),
            "cpu_time_limit": max(0.5, time_limit_ms / 1000.0),
            "memory_limit": max(1024, memory_limit_mb * 1024),
            "max_file_size": 1024,
            "enable_network": False  # Enforce sandbox network boundary (Condition 3)
        }

        url = f"{self.base_url}/submissions?base64_encoded=true&wait=true"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[Judge0HttpAdapter] Failed to contact Judge0 at {url}: {err_msg}")
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Runtime Error",
                runtime_ms=0,
                memory_mb=0.0,
                is_hidden=is_hidden,
                error_output="Execution service unavailable.",
                raw_server_error=f"Judge0 connection error: {err_msg}"
            )

        # Parse Judge0 response
        status_id = data.get("status", {}).get("id", JUDGE0_STATUS_INTERNAL_ERROR)
        time_sec = float(data.get("time") or 0.0)
        runtime_ms = int(time_sec * 1000)
        memory_kb = float(data.get("memory") or 0.0)
        memory_mb = round(memory_kb / 1024.0, 2)

        def decode_b64(val: Optional[str]) -> Optional[str]:
            if not val:
                return None
            try:
                return base64.b64decode(val.encode("ascii")).decode("utf-8", errors="replace").strip()
            except Exception:
                return val.strip()

        stdout = decode_b64(data.get("stdout"))
        compile_output = decode_b64(data.get("compile_output"))
        stderr = decode_b64(data.get("stderr"))
        raw_error = compile_output or stderr

        if status_id == JUDGE0_STATUS_ACCEPTED:
            status_str = "Passed"
        elif status_id == JUDGE0_STATUS_WRONG_ANSWER:
            status_str = "Wrong Answer"
        elif status_id == JUDGE0_STATUS_TIME_LIMIT_EXCEEDED:
            status_str = "Time Limit Exceeded"
        elif status_id == JUDGE0_STATUS_COMPILATION_ERROR:
            status_str = "Compile Error"
        else:
            status_str = "Runtime Error"

        if raw_error:
            logger.warning(f"[Judge0 Server Log] Test {test_case_id} failed ({status_str}): {raw_error}")

        return TestCaseResultDTO(
            test_case_id=test_case_id,
            name=test_name,
            status=status_str,
            runtime_ms=runtime_ms,
            memory_mb=memory_mb,
            is_hidden=is_hidden,
            actual_output=None if is_hidden else stdout,
            error_output="Test execution failed on hidden test." if (is_hidden and raw_error) else raw_error,
            raw_server_error=raw_error
        )

    def execute_suite(
        self,
        code: str,
        language: str,
        test_cases: List[Any],
        time_limit_ms: int = 2000,
        memory_limit_mb: int = 256
    ) -> ExecutionSummaryDTO:
        results: List[TestCaseResultDTO] = []
        max_time = 0
        max_mem = 0.0
        passed_count = 0
        first_error_msg = None
        first_raw_server_error = None

        for tc in test_cases:
            tc_id = str(_extract_case_attr(tc, "id", ""))
            name = str(_extract_case_attr(tc, "name", "Test Case"))
            input_data = str(_extract_case_attr(tc, "input_data", ""))
            expected_output = str(_extract_case_attr(tc, "expected_output", ""))
            is_hidden = bool(_extract_case_attr(tc, "is_hidden", False))

            res = self.execute_test_case(
                code=code,
                language=language,
                test_case_id=tc_id,
                test_name=name,
                input_data=input_data,
                expected_output=expected_output,
                is_hidden=is_hidden,
                time_limit_ms=time_limit_ms,
                memory_limit_mb=memory_limit_mb
            )
            results.append(res)
            max_time = max(max_time, res.runtime_ms)
            max_mem = max(max_mem, res.memory_mb)

            if res.status == "Passed":
                passed_count += 1
            else:
                if not first_error_msg:
                    first_error_msg = res.error_output
                    first_raw_server_error = res.raw_server_error

        total = len(test_cases)
        overall_status = "Accepted" if (total > 0 and passed_count == total) else (
            results[0].status if (results and passed_count == 0) else "Wrong Answer"
        )

        return ExecutionSummaryDTO(
            status=overall_status,
            runtime_ms=max_time,
            memory_mb=max_mem,
            tests_passed=passed_count,
            tests_total=total,
            cases=results,
            error_message=first_error_msg,
            raw_server_error=first_raw_server_error
        )


class MockJudge0Adapter(CodeExecutionEngine):
    """Deterministic simulated code execution adapter matching the Judge0 contract.
    Used for local dev, offline CI, and deterministic Playwright tests.
    """

    def execute_test_case(
        self,
        code: str,
        language: str,
        test_case_id: str,
        test_name: str,
        input_data: str,
        expected_output: str,
        is_hidden: bool = False,
        time_limit_ms: int = 2000,
        memory_limit_mb: int = 256
    ) -> TestCaseResultDTO:
        lang_id = JUDGE0_LANGUAGE_IDS.get(language.lower())
        if not lang_id:
            raw_err = f"Language '{language}' not mapped in JUDGE0_LANGUAGE_IDS"
            logger.warning(f"[MockJudge0 Server Log] Unsupported language: {raw_err}")
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Compile Error",
                runtime_ms=0,
                memory_mb=0.0,
                is_hidden=is_hidden,
                error_output="Unsupported language",
                raw_server_error=raw_err
            )

        clean_code = (code or "").strip()
        if not clean_code:
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Compile Error",
                runtime_ms=0,
                memory_mb=0.0,
                is_hidden=is_hidden,
                error_output="Empty code submitted.",
                raw_server_error="Source file contains 0 non-whitespace tokens."
            )

        # Check for syntax errors / missing required functions
        has_definition = any(keyword in clean_code for keyword in ["def ", "class ", "function ", "int ", "public "])
        if not has_definition:
            raw_err = "SyntaxError: missing entry function definition in source code."
            logger.warning(f"[MockJudge0 Server Log] Syntax error on {test_case_id}: {raw_err}")
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Compile Error",
                runtime_ms=12,
                memory_mb=14.2,
                is_hidden=is_hidden,
                error_output="Test execution failed on hidden test." if is_hidden else raw_err,
                raw_server_error=raw_err
            )

        # Simulated logic evaluation
        # If code contains correct solution patterns (e.g. Solution and countComponents / find / union)
        is_correct = "countComponents" in clean_code and ("union" in clean_code or "find" in clean_code or "parent" in clean_code or "n - len" in clean_code or "return" in clean_code)
        
        # Check explicit failing triggers for testing
        if "raise TimeoutError" in clean_code or "while True" in clean_code:
            raw_err = "Time Limit Exceeded: Process exceeded maximum execution time of 2000ms"
            logger.warning(f"[MockJudge0 Server Log] TLE on {test_case_id}: {raw_err}")
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Time Limit Exceeded",
                runtime_ms=time_limit_ms + 50,
                memory_mb=18.4,
                is_hidden=is_hidden,
                error_output="Test execution failed on hidden test." if is_hidden else "Time Limit Exceeded.",
                raw_server_error=raw_err
            )

        if "raise Exception" in clean_code or "ZeroDivisionError" in clean_code:
            raw_err = "ZeroDivisionError: division by zero at line 4 in countComponents"
            logger.warning(f"[MockJudge0 Server Log] Runtime error on {test_case_id}: {raw_err}")
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Runtime Error",
                runtime_ms=18,
                memory_mb=15.2,
                is_hidden=is_hidden,
                error_output="Test execution failed on hidden test." if is_hidden else "Runtime Error: division by zero",
                raw_server_error=raw_err
            )

        if is_correct:
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Passed",
                runtime_ms=42,
                memory_mb=16.1,
                is_hidden=is_hidden,
                actual_output=None if is_hidden else expected_output.strip()
            )
        else:
            raw_err = f"Expected output: {expected_output.strip()!r}, got: '0'"
            logger.warning(f"[MockJudge0 Server Log] Wrong answer on {test_case_id}: {raw_err}")
            return TestCaseResultDTO(
                test_case_id=test_case_id,
                name=test_name,
                status="Wrong Answer",
                runtime_ms=25,
                memory_mb=15.0,
                is_hidden=is_hidden,
                actual_output=None if is_hidden else "0",
                error_output="Test execution failed on hidden test." if is_hidden else "Output did not match expected result.",
                raw_server_error=raw_err
            )

    def execute_suite(
        self,
        code: str,
        language: str,
        test_cases: List[Any],
        time_limit_ms: int = 2000,
        memory_limit_mb: int = 256
    ) -> ExecutionSummaryDTO:
        results: List[TestCaseResultDTO] = []
        max_time = 0
        max_mem = 0.0
        passed_count = 0
        first_error_msg = None
        first_raw_server_error = None

        for tc in test_cases:
            tc_id = str(_extract_case_attr(tc, "id", ""))
            name = str(_extract_case_attr(tc, "name", "Test Case"))
            input_data = str(_extract_case_attr(tc, "input_data", ""))
            expected_output = str(_extract_case_attr(tc, "expected_output", ""))
            is_hidden = bool(_extract_case_attr(tc, "is_hidden", False))

            res = self.execute_test_case(
                code=code,
                language=language,
                test_case_id=tc_id,
                test_name=name,
                input_data=input_data,
                expected_output=expected_output,
                is_hidden=is_hidden,
                time_limit_ms=time_limit_ms,
                memory_limit_mb=memory_limit_mb
            )
            results.append(res)
            max_time = max(max_time, res.runtime_ms)
            max_mem = max(max_mem, res.memory_mb)

            if res.status == "Passed":
                passed_count += 1
            else:
                if not first_error_msg:
                    first_error_msg = res.error_output
                    first_raw_server_error = res.raw_server_error

        total = len(test_cases)
        overall_status = "Accepted" if (total > 0 and passed_count == total) else (
            results[0].status if (results and passed_count == 0) else "Wrong Answer"
        )

        return ExecutionSummaryDTO(
            status=overall_status,
            runtime_ms=max_time,
            memory_mb=max_mem,
            tests_passed=passed_count,
            tests_total=total,
            cases=results,
            error_message=first_error_msg,
            raw_server_error=first_raw_server_error
        )


def get_execution_engine() -> CodeExecutionEngine:
    """Factory creating the appropriate execution engine adapter."""
    adapter_name = settings.JUDGE0_ADAPTER.lower().strip()
    if adapter_name == "judge0":
        return Judge0HttpAdapter()
    return MockJudge0Adapter()
