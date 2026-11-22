"""Shared pytest setup.

Link tags: mark a test with @pytest.mark.link("L07", ...) when it proves a
link in docs/INTERCONNECT.md. With LINK_REPORT=path set, the outcome of every
tagged test is written there as JSON for scripts/link_gate.py.
"""
import json
import os

# The suite signs parents in many times from one client ("testclient") and audit rows outlive a run:
# per-IP OTP limits are lifted here and tested on purpose in tests/test_security_review.py.
os.environ.setdefault("OTP_IP_REQUESTS_PER_WINDOW", "100000")
os.environ.setdefault("OTP_IP_VERIFY_FAILS_PER_WINDOW", "100000")

import pytest

_results: list = []


def pytest_configure(config):
    config.addinivalue_line("markers", "link(*ids): proves the listed interconnect links (L01..L43)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    links = [lid for m in item.iter_markers(name="link") for lid in m.args]
    if not links:
        return
    # one record per test: the call phase decides, but a setup/teardown error fails it
    if rep.when == "call" or (rep.when in ("setup", "teardown") and rep.failed):
        _results.append({"test": item.nodeid, "links": links, "outcome": rep.outcome, "phase": rep.when})


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("LINK_REPORT")
    if not path:
        return
    merged: dict = {}
    for r in _results:
        prev = merged.get(r["test"])
        if prev is None or r["outcome"] != "passed":
            merged[r["test"]] = r
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "pytest", "results": list(merged.values())}, f, indent=1)
