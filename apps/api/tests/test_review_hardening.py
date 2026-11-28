"""Regression tests for the gaps found in the Nov 2026 black-box review.

- trainer code-review routes were open to any signed-in role (a student could approve their own PR)
- review decisions wrote no audit row and told nobody
- anonymous requests became a demo user outside local development (staging, a mistyped ENVIRONMENT, Keycloak)
- every coding problem served the same Union-Find hints
- a non-numeric answer key crashed the test autosave (500)
- the super admin's /college/overview failed (a read wrote a default config row and blocked the request audit)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import AuditLog, Notification, PullRequest

client = TestClient(app)


def _h(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Test"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": name})}


TRAINER = _h("usr_arun_01", "trainer", name="Arun Kumar")
STUDENT = _h("usr_priya_01", "student", name="Priya R")
PARENT = _h("usr_ramesh_01", "parent", name="Mr. Ramesh K")
COLLEGE = _h("usr_kavitha_01", "college_admin", name="Dr. Kavitha")


@pytest.mark.parametrize("who", [STUDENT, PARENT, COLLEGE])
def test_only_trainers_reach_code_reviews(who):
    assert client.get("/api/v1/trainer/reviews", headers=who).status_code == 403
    assert client.get("/api/v1/trainer/reviews/pr_41", headers=who).status_code == 403
    r = client.post("/api/v1/trainer/reviews/pr_41/action", headers=who,
                    json={"action": "approve", "review_feedback": "self-approved", "code_quality_score": 5,
                          "test_coverage_score": 5, "modularity_score": 5})
    assert r.status_code == 403
    assert client.post("/api/v1/trainer/reviews/pr_41/comments", headers=who,
                       json={"file_path": "a.py", "line_number": 1, "comment_text": "x"}).status_code == 403


def test_review_decision_is_audited_and_the_author_is_told():
    from models.schema import Student
    db = SessionLocal()
    try:
        pr = db.execute(select(PullRequest).filter_by(id="pr_41")).scalar_one()
        before_status = pr.status
        author = db.execute(select(Student.user_id).where(Student.id == pr.author_id)).scalar_one()
        assert author != "usr_priya_01"                          # Rahul's PR (the seed used to credit Priya)
        n_notes = db.query(Notification).filter(Notification.user_id == author,
                                                Notification.title_en == f"Changes requested on PR {pr.pr_number}").count()
    finally:
        db.close()
    r = client.post("/api/v1/trainer/reviews/pr_41/action", headers=TRAINER,
                    json={"action": "request_changes", "review_feedback": "Add tests", "code_quality_score": 3,
                          "test_coverage_score": 2, "modularity_score": 3})
    assert r.status_code == 200
    db = SessionLocal()
    try:
        audit = db.execute(select(AuditLog).where(AuditLog.action == "code_review.request_changes", AuditLog.entity_id == "pr_41")
                           .order_by(AuditLog.created_at.desc())).scalars().first()
        assert audit is not None and audit.actor_user_id == "usr_arun_01"
        after = db.query(Notification).filter(Notification.user_id == author,
                                              Notification.title_en.like("Changes requested on PR %")).count()
        assert after > n_notes
        note = db.query(Notification).filter(Notification.user_id == author,
                                             Notification.title_en.like("Changes requested on PR %")).first()
        assert note.title_ta                                     # Tamil variant for the student's language
        # restore the seeded state for other tests
        pr = db.execute(select(PullRequest).filter_by(id="pr_41")).scalar_one()
        pr.status = before_status
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("env,provider", [("staging", "local"), ("prod", "local"), ("Production", "local"), ("development", "keycloak")])
def test_anonymous_requests_are_refused_outside_local_development(env, provider):
    orig = settings.ENVIRONMENT, settings.AUTH_PROVIDER
    settings.ENVIRONMENT, settings.AUTH_PROVIDER = env, provider
    try:
        assert client.get("/api/v1/student/dashboard").status_code == 401
        assert client.get("/api/v1/trainer/dashboard", headers={"X-Demo-Role": "trainer"}).status_code == 401
    finally:
        settings.ENVIRONMENT, settings.AUTH_PROVIDER = orig


def test_local_development_keeps_the_demo_fallback():
    assert settings.ENVIRONMENT.lower() in ("development", "dev", "local", "test")
    assert client.get("/api/v1/student/dashboard").status_code == 200


def test_hints_follow_the_problem_topic():
    two_sum = client.get("/api/v1/student/coding/prob_two_sum", headers=TRAINER).json()
    graph = client.get("/api/v1/student/coding/prob_connected_components", headers=TRAINER).json()
    h1 = two_sum["ai_reviewer"]["revealed_hints"][0]
    h2 = graph["ai_reviewer"]["revealed_hints"][0]
    assert h1 != h2
    assert "connectivity" in h2.lower()
    assert "connected" not in h1.lower() and "union" not in h1.lower()
    # a trainer previews the next hint without spending a student's quota, and it is about this problem
    nxt = client.post("/api/v1/student/coding/prob_two_sum/hint", headers=TRAINER, json={"current_count": 1}).json()
    assert nxt["success"] is True and "edge" not in nxt["hint"].lower()


def test_answer_keys_must_be_question_numbers():
    start = client.post("/api/v1/student/tests/test_service_aptitude/attempts", headers=STUDENT)
    assert start.status_code == 200
    attempt_id = start.json()["attempt_id"]
    r = client.put(f"/api/v1/student/tests/attempts/{attempt_id}/answers", headers=STUDENT,
                   json={"answers": {"not-a-number": "A"}})
    if r.status_code == 400:                       # the seeded attempt may already be submitted: nothing to save
        pytest.skip("no attempt in progress")
    assert r.status_code == 422


def test_super_admin_reads_the_college_overview():
    db = SessionLocal()
    try:
        from models.schema import User
        sup = db.execute(select(User).where(User.role == "super_admin")).scalars().first()
    finally:
        db.close()
    assert sup is not None
    r = client.get("/api/v1/college/overview", headers=_h(sup.id, "super_admin", sup.college_id))
    assert r.status_code == 200


def test_api_docs_authorize_button_signs_in():
    """The docs' Authorize button posts to the scheme's tokenUrl (/auth/token); it used to 404, so every
    call from the docs ran as the demo student and trainer or parent routes answered 403."""
    r = client.post("/api/v1/auth/token", data={"username": "arun.k@demo.edu", "password": "password123"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/trainer/dashboard", headers=h).status_code == 200
    assert client.post("/api/v1/auth/token", data={"username": "arun.k@demo.edu", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/token", data={"username": "nobody@demo.edu", "password": "x"}).status_code == 401


def test_api_docs_token_is_gone_in_keycloak_mode():
    orig = settings.AUTH_PROVIDER
    settings.AUTH_PROVIDER = "keycloak"
    try:
        assert client.post("/api/v1/auth/token", data={"username": "arun.k@demo.edu", "password": "password123"}).status_code == 410
    finally:
        settings.AUTH_PROVIDER = orig


def test_a_submitted_test_cannot_be_resubmitted_or_regraded():
    """Submit used to accept new answers on a graded attempt and re-measure the time ("1184 mins")."""
    import datetime
    from models.schema import TestAttempt
    start = client.post("/api/v1/student/tests/test_service_aptitude/attempts", headers=STUDENT)
    assert start.status_code == 200
    attempt_id = start.json()["attempt_id"]
    first = client.post(f"/api/v1/student/tests/attempts/{attempt_id}/submit", headers=STUDENT, json={"answers": {}})
    assert first.status_code == 200
    db = SessionLocal()
    try:
        a = db.get(TestAttempt, attempt_id)
        graded = (a.score, a.time_taken_sec, a.submitted_at)
        # pretend the student comes back an hour later with every answer
        a.started_at -= datetime.timedelta(hours=1)
        db.commit()
    finally:
        db.close()
    again = client.post(f"/api/v1/student/tests/attempts/{attempt_id}/submit", headers=STUDENT,
                        json={"answers": {str(n): "A" for n in range(1, 31)}})
    assert again.status_code == 200 and again.json()["score"] == first.json()["score"]
    db = SessionLocal()
    try:
        a = db.get(TestAttempt, attempt_id)
        assert (a.score, a.time_taken_sec, a.submitted_at) == graded
    finally:
        db.close()


def test_a_late_submit_counts_only_answers_saved_in_time():
    import datetime
    from models.schema import TestAttempt
    attempt_id = client.post("/api/v1/student/tests/test_service_aptitude/attempts", headers=STUDENT).json()["attempt_id"]
    db = SessionLocal()
    try:
        a = db.get(TestAttempt, attempt_id)
        if a.status != "in_progress":
            pytest.skip("no attempt in progress")
        limit = a.ends_at - a.started_at
        a.started_at -= datetime.timedelta(hours=2)           # the time ran out long ago
        a.ends_at = a.started_at + limit
        db.commit()
    finally:
        db.close()
    r = client.post(f"/api/v1/student/tests/attempts/{attempt_id}/submit", headers=STUDENT,
                    json={"answers": {str(n): "A" for n in range(1, 31)}})
    assert r.status_code == 200
    db = SessionLocal()
    try:
        a = db.get(TestAttempt, attempt_id)
        assert a.time_taken_sec <= int(limit.total_seconds())  # never longer than the test
        from models.schema import AttemptAnswer
        late = db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.selected_option == "A").count()
        saved_before = late                                     # nothing sent after the deadline was stored
        assert saved_before == 0
    finally:
        db.close()
