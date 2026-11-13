import sys
from pathlib import Path
import pytest

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

from services.judge0_service import (
    JUDGE0_LANGUAGE_IDS,
    MockJudge0Adapter,
    Judge0HttpAdapter,
    TestCaseResultDTO
)

def test_judge0_language_ids_mappings():
    """Verify that all required languages map to standard positive integer IDs in Judge0."""
    required_languages = {"python", "java", "cpp", "javascript"}
    assert required_languages.issubset(set(JUDGE0_LANGUAGE_IDS.keys())), (
        f"Missing languages in JUDGE0_LANGUAGE_IDS: {required_languages - set(JUDGE0_LANGUAGE_IDS.keys())}"
    )

    for lang, lang_id in JUDGE0_LANGUAGE_IDS.items():
        assert isinstance(lang_id, int), f"Language ID for {lang} must be an integer, got {type(lang_id)}"
        assert lang_id > 0, f"Language ID for {lang} must be positive, got {lang_id}"

    # Specific standard Judge0 CE IDs verification
    assert JUDGE0_LANGUAGE_IDS["python"] == 71   # Python 3.8.1
    assert JUDGE0_LANGUAGE_IDS["java"] == 62     # Java OpenJDK 13.0.1
    assert JUDGE0_LANGUAGE_IDS["cpp"] == 54      # C++ GCC 9.2.0
    assert JUDGE0_LANGUAGE_IDS["javascript"] == 63  # Node.js 12.14.0

def test_missing_or_unsupported_language_fails_fast_in_mock():
    """Verify that passing an unknown language to Mock adapter returns Compile Error with Unsupported language."""
    adapter = MockJudge0Adapter()
    res = adapter.execute_test_case(
        code="puts 'hello'",
        language="ruby",
        test_case_id="tc_1",
        test_name="Ruby test",
        input_data="",
        expected_output="hello"
    )
    assert res.status == "Compile Error"
    assert res.error_output == "Unsupported language"
    assert "ruby" in res.raw_server_error

def test_judge0_http_adapter_validates_language():
    """Verify Judge0HttpAdapter validates language against JUDGE0_LANGUAGE_IDS."""
    adapter = Judge0HttpAdapter(base_url="http://localhost:2358", auth_token="test-token")
    res = adapter.execute_test_case(
        code="fn main() {}",
        language="rust",
        test_case_id="tc_2",
        test_name="Rust test",
        input_data="",
        expected_output=""
    )
    assert res.status == "Compile Error"
    assert res.error_output == "Unsupported language"
    assert "rust" in res.raw_server_error
