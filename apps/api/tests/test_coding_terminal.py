"""Coding lab, Phase 2: the terminal (run my program on my input), real judging through Judge0 (HTTP mocked
here), and starter code that never contains the answer."""
import base64
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from core.security import create_access_token
from main import app
from services import judge0_service
from services.code_harness import DRIVER_MARK, STDIO_TEMPLATES
from services.judge0_service import Judge0HttpAdapter, MockJudge0Adapter

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, RAMESH = _h("usr_priya_01", "student"), _h("usr_ramesh_01", "parent")
b64 = lambda s: base64.b64encode(s.encode()).decode()


class FakeJudge0:
    """Stands in for httpx.Client: records what the adapter sends, answers like Judge0."""
    sent = []
    answer = {}

    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def post(self, url, json=None, headers=None):
        FakeJudge0.sent.append(json)
        return httpx.Response(200, json=FakeJudge0.answer, request=httpx.Request("POST", url))


@pytest.fixture(autouse=True)
def fresh_run_budget():
    """Terminal runs are rate limited per student (usage ledger): each test starts with none."""
    from sqlalchemy import delete
    from core.database import SessionLocal
    from models.schema import UsageLedger

    def clear():
        with SessionLocal() as db:
            db.execute(delete(UsageLedger).where(UsageLedger.student_id == "std_priya_01", UsageLedger.kind == "code_runs"))
            db.commit()
    clear()
    yield
    clear()


@pytest.fixture
def judge0(monkeypatch):
    FakeJudge0.sent = []
    monkeypatch.setattr(httpx, "Client", FakeJudge0)
    monkeypatch.setattr(judge0_service.settings, "JUDGE0_ADAPTER", "judge0")
    return FakeJudge0


def test_terminal_without_a_runner_says_so_instead_of_inventing_output():
    r = client.post("/api/v1/student/coding/prob_two_sum/execute", headers=PRIYA,
                    json={"language": "java", "code": STDIO_TEMPLATES["java"], "stdin": "hello"})
    assert r.status_code == 200
    assert r.json()["status"] == "Unavailable" and r.json()["stdout"] == ""


def test_terminal_runs_any_language_on_judge0_and_returns_its_output(judge0):
    judge0.answer = {"status": {"id": 3, "description": "Accepted"}, "stdout": b64("hello\n"), "stderr": None, "time": "0.012", "memory": 9216}
    r = client.post("/api/v1/student/coding/prob_two_sum/execute", headers=PRIYA,
                    json={"language": "cpp", "code": STDIO_TEMPLATES["cpp"], "stdin": "hello"})
    out = r.json()
    assert out["status"] == "Finished" and out["stdout"] == "hello" and out["runtime_ms"] == 12 and out["memory_mb"] == 9.0
    sent = judge0.sent[-1]
    assert sent["language_id"] == 54 and base64.b64decode(sent["stdin"]).decode() == "hello"
    assert sent["enable_network"] is False and "expected_output" not in sent        # we compare answers ourselves


def test_terminal_shows_compiler_errors(judge0):
    judge0.answer = {"status": {"id": 6, "description": "Compilation Error"}, "compile_output": b64("main.cpp:3: error: expected ';'")}
    out = client.post("/api/v1/student/coding/prob_two_sum/execute", headers=PRIYA,
                      json={"language": "cpp", "code": "int main(){return 0}", "stdin": ""}).json()
    assert out["status"] == "Compile Error" and "expected ';'" in out["compile_output"]


def test_terminal_guards():
    body = {"language": "python", "code": "print(1)", "stdin": ""}
    assert client.post("/api/v1/student/coding/prob_two_sum/execute", headers=RAMESH, json=body).status_code == 403
    assert client.post("/api/v1/student/coding/prob_two_sum/execute", headers=_h("usr_priya_01", "student", "col_other_999"), json=body).status_code == 404
    assert client.post("/api/v1/student/coding/prob_two_sum/execute", headers=PRIYA, json={**body, "language": "ruby"}).status_code == 422


def test_function_problem_is_judged_through_the_driver_and_ignores_json_spacing(judge0):
    judge0.answer = {"status": {"id": 3}, "stdout": b64("[0, 1]\n"), "time": "0.02", "memory": 8000}
    r = client.post("/api/v1/student/coding/prob_two_sum/run", headers=PRIYA,
                    json={"language": "python", "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n"})
    assert r.status_code == 200 and r.json()["cases"][0]["status"] == "Passed"
    program = base64.b64decode(judge0.sent[0]["source_code"]).decode()
    assert DRIVER_MARK in program and "class ListNode" in program


def test_function_problem_tests_run_in_python_only(judge0):
    r = client.post("/api/v1/student/coding/prob_two_sum/run", headers=PRIYA,
                    json={"language": "java", "code": "class Solution { }"})
    assert r.status_code == 422 and "Terminal" in r.json()["detail"]


def test_starter_code_never_contains_the_answer():
    d = client.get("/api/v1/student/coding/prob_two_sum", headers=PRIYA).json()
    assert d["io_mode"] == "function" and d["judged_languages"] == ["python"]
    assert "def twoSum" in d["starter_codes"]["python"] and "return" not in d["starter_codes"]["python"]
    for lang in ("java", "cpp", "javascript"):                                       # no other problem's answer either
        assert "countComponents" not in d["starter_codes"][lang] and d["starter_codes"][lang] == STDIO_TEMPLATES[lang]


def test_the_fake_engine_is_never_mistaken_for_a_real_one():
    assert MockJudge0Adapter.runs_real_code is False and Judge0HttpAdapter.runs_real_code is True
    assert MockJudge0Adapter().run_program("print(1)", "python", "").status == "Unavailable"


def test_terminal_runs_are_metered_and_rate_limited(judge0):
    from sqlalchemy import delete
    from core.database import SessionLocal
    from models.schema import UsageLedger
    judge0.answer = {"status": {"id": 3}, "stdout": b64("ok\n"), "time": "0.01", "memory": 1000}
    body = {"language": "python", "code": "print('ok')", "stdin": ""}
    try:
        assert client.post("/api/v1/student/coding/prob_two_sum/execute", headers=PRIYA, json=body).status_code == 200
        again = client.post("/api/v1/student/coding/prob_two_sum/execute", headers=PRIYA, json=body)
        assert again.status_code == 429 and again.headers["Retry-After"] == "2"           # one run at a time
        with SessionLocal() as db:
            assert db.query(UsageLedger).filter_by(student_id="std_priya_01", kind="code_runs").count() >= 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(UsageLedger).where(UsageLedger.student_id == "std_priya_01", UsageLedger.kind == "code_runs"))
            db.commit()


def test_http_timeout_outlasts_the_sandbox_wall_time(judge0, monkeypatch):
    seen = {}

    class Timed(FakeJudge0):
        def __init__(self, *a, timeout=None, **k):
            seen["timeout"] = timeout
    monkeypatch.setattr(httpx, "Client", Timed)
    judge0.answer = {"status": {"id": 3}, "stdout": b64("x"), "time": "0.01", "memory": 1}
    Judge0HttpAdapter().run_program("print(1)", "python", "", time_limit_ms=5000)
    assert seen["timeout"] >= 5 * 3 + 10                                            # wall limit (3x CPU) plus margin
