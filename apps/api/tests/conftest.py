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
os.environ.setdefault("OTP_RESPONSE_FLOOR_MS", "0")        # tested on purpose in tests/test_security_review.py

import pytest

_results: list = []

# Token-only test accounts: some tests sign tokens for users that are not in the demo seed (other
# colleges, a second trainer). Since a token is accepted only for an existing, active user
# (core/active_users.py), they get real rows here. Emails use the reserved .invalid domain.
TOKEN_TEST_USERS = {
    "usr_trainer_01": ("col_demo_001", "trainer"),
    "usr_other_trainer": ("col_other_999", "trainer"),
    "usr_other_99": ("col_other_999", "student"),
    "usr_other_01": ("col_other_999", "student"),
    "usr_x": ("col_other_999", "college_admin"),
    "usr_cse_5_001_x": ("col_demo_001", "student"),
}


@pytest.fixture(scope="session", autouse=True)
def token_test_users():
    from core.database import SessionLocal
    from core.security import get_password_hash
    from models.schema import User
    db = SessionLocal()
    try:
        for uid, (cid, role) in TOKEN_TEST_USERS.items():
            if db.get(User, uid) is None:
                db.add(User(id=uid, college_id=cid, email=f"{uid}@tests.invalid", role=role, name=uid,
                            avatar_initials="TT", hashed_password=get_password_hash(uid)))
        db.commit()
    finally:
        db.close()
    yield


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
