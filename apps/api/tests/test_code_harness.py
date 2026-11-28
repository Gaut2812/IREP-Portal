"""The judge driver for function (LeetCode-style) problems: every seeded problem's REFERENCE answer, wrapped by the
driver, must print each test's expected output. This proves the expected outputs and the driver agree before any
student code meets Judge0. Only our own reference code runs here (in a subprocess); student code never runs on
this host (rule 10)."""
import ast
import subprocess
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest

from seed.seed_data import CONNECTED_COMPONENTS_REFERENCE, get_screen24_test_cases
from seed.seed_weekly_dsa import WEEKLY_DSA_DATA
from services.code_harness import make_stub, outputs_match, wrap_python


def _cases():
    for p in WEEKLY_DSA_DATA:
        for tc_id, given, expected, _ in p["sample_cases"]:
            yield pytest.param(p["starter_code"], given, expected, id=f"{p['id']}-{tc_id}")
    for tc in get_screen24_test_cases():
        yield pytest.param(CONNECTED_COMPONENTS_REFERENCE, tc.input_data, tc.expected_output, id=f"connected-{tc.id}")


def _run(program: str, stdin: str) -> str:
    done = subprocess.run([sys.executable, "-I", "-c", program], input=stdin, capture_output=True, text=True, timeout=20)
    assert done.returncode == 0, done.stderr
    return done.stdout


@pytest.mark.parametrize("reference,given,expected", list(_cases()))
def test_reference_answer_passes_through_the_driver(reference, given, expected):
    assert outputs_match(_run(wrap_python(reference), given), expected)


def test_a_stub_fails_the_tests_instead_of_crashing_the_driver():
    stub = make_stub(WEEKLY_DSA_DATA[0]["starter_code"])                      # twoSum with `pass`
    assert not outputs_match(_run(wrap_python(stub), "nums = [2,7,11,15], target = 9"), "[0,1]")


@pytest.mark.parametrize("p", WEEKLY_DSA_DATA, ids=lambda p: p["id"])
def test_starter_stub_keeps_signatures_and_hides_the_answer(p):
    ref, stub = p["starter_code"], make_stub(p["starter_code"])
    ast.parse(stub)                                                           # valid Python
    ref_defs = [n.name for n in ast.walk(ast.parse(ref)) if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.col_offset <= 4]
    stub_defs = [n.name for n in ast.walk(ast.parse(stub)) if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
    assert stub_defs == ref_defs                                              # same classes and methods, nested helpers dropped
    assert "return" not in stub and stub.count("pass") >= 1


def test_outputs_match_ignores_json_spacing_but_not_values():
    assert outputs_match("[0, 1]\n", "[0,1]") and outputs_match("true", "true") and outputs_match(" no  cycle ", "no cycle")
    assert not outputs_match("[1,0]", "[0,1]") and not outputs_match("false", "true")
