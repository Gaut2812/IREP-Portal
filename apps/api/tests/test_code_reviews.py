import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import PullRequest, PullRequestFile, PullRequestComment, SprintTask, StudentProject

client = TestClient(app)

@pytest.fixture
def trainer_auth_headers():
    token = create_access_token(data={
        "sub": "usr_trainer_01",
        "role": "trainer",
        "college_id": "col_demo_001",
        "name": "Arun Kumar"
    })
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def other_tenant_auth_headers():
    token = create_access_token(data={
        "sub": "usr_other_trainer",
        "role": "trainer",
        "college_id": "col_other_999",
        "name": "Other Trainer"
    })
    return {"Authorization": f"Bearer {token}"}

def test_list_trainer_reviews_success(trainer_auth_headers):
    res = client.get("/api/v1/trainer/reviews", headers=trainer_auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "prs" in data
    assert "counts" in data
    assert data["counts"]["total"] >= 4

    pr_numbers = [p["pr_number"] for p in data["prs"]]
    assert "#39" in pr_numbers
    assert "#41" in pr_numbers

    # Test filtering by status
    pending_res = client.get("/api/v1/trainer/reviews?status=pending", headers=trainer_auth_headers)
    assert pending_res.status_code == 200
    for p in pending_res.json()["prs"]:
        assert p["status"] == "pending"

def test_get_pr_detail_with_diff_and_checks(trainer_auth_headers):
    res = client.get("/api/v1/trainer/reviews/pr_39", headers=trainer_auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "pr" in data
    assert data["pr"]["pr_number"] == "#39"
    assert data["pr"]["author_name"] == "Priya R"

    assert "files" in data
    assert len(data["files"]) >= 2
    filenames = [f["filename"] for f in data["files"]]
    assert "services/booking_service.py" in filenames
    assert "tests/test_booking.py" in filenames

    # Verify diff content presence
    service_file = next(f for f in data["files"] if f["filename"] == "services/booking_service.py")
    assert "@@" in service_file["diff_content"]
    assert "+" in service_file["diff_content"]

    assert "automated_checks" in data
    assert data["automated_checks"]["all_passed"] is True
    assert data["automated_checks"]["tests_passed"] == 14

    assert "comments" in data
    assert len(data["comments"]) >= 1
    assert "Arun Kumar" in data["comments"][0]["author_name"]

@pytest.mark.link("L14")
def test_approve_pr_advances_sprint_task_and_verifies_portfolio(trainer_auth_headers):
    # Approve PR #39 (linked to task_08 on Sprint Board & proj_clinic_02 in Portfolio)
    action_payload = {
        "action": "approve",
        "review_feedback": "Outstanding test coverage! Clean exception handling and atomic transactions.",
        "code_quality_score": 5,
        "test_coverage_score": 5,
        "modularity_score": 5,
        "score_percent": 96
    }
    res = client.post("/api/v1/trainer/reviews/pr_39/action", json=action_payload, headers=trainer_auth_headers)
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["status"] == "approved"

    # Verify database state updates
    db = SessionLocal()
    try:
        # 1. PullRequest status is approved
        pr = db.execute(select(PullRequest).filter_by(id="pr_39")).scalar_one_or_none()
        assert pr is not None
        assert pr.status == "approved"
        assert pr.reviewed_by == "Arun Kumar"

        # 2. SprintTask is auto-advanced to 'done'
        task = db.execute(select(SprintTask).filter_by(id="task_08")).scalar_one_or_none()
        assert task is not None
        assert task.column_name == "done"

        # 3. StudentProject in Portfolio is auto-verified with trainer feedback
        proj = db.execute(select(StudentProject).filter_by(id="proj_clinic_02")).scalar_one_or_none()
        assert proj is not None
        assert proj.trainer_verified is True
        assert proj.score_percent == 96
        assert "Outstanding test coverage" in proj.trainer_feedback
    finally:
        db.close()

@pytest.mark.link("L14")
def test_request_changes_pr_moves_task_to_in_progress(trainer_auth_headers):
    action_payload = {
        "action": "request_changes",
        "review_feedback": "Please add unit tests for token expiry edge case before merging.",
        "code_quality_score": 3,
        "test_coverage_score": 2,
        "modularity_score": 4
    }
    res = client.post("/api/v1/trainer/reviews/pr_41/action", json=action_payload, headers=trainer_auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "changes_requested"

    # Verify database state
    db = SessionLocal()
    try:
        pr = db.execute(select(PullRequest).filter_by(id="pr_41")).scalar_one_or_none()
        assert pr.status == "changes_requested"

        # SprintTask task_07 moved to in_progress
        task = db.execute(select(SprintTask).filter_by(id="task_07")).scalar_one_or_none()
        assert task is not None
        assert task.column_name == "in_progress"
    finally:
        db.close()

def test_add_inline_comment(trainer_auth_headers):
    comment_payload = {
        "file_id": "prf_39_01",
        "line_number": 45,
        "comment_text": "Verify whether audit_log.record should be called inside or outside the database transaction block."
    }
    res = client.post("/api/v1/trainer/reviews/pr_39/comments", json=comment_payload, headers=trainer_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["comment"]["line_number"] == 45
    assert "audit_log" in data["comment"]["comment_text"]

    # Verify persisted in database
    db = SessionLocal()
    try:
        comment_id = data["comment"]["id"]
        c = db.execute(select(PullRequestComment).filter_by(id=comment_id)).scalar_one_or_none()
        assert c is not None
        assert c.pr_id == "pr_39"
        assert c.author_name == "Arun Kumar"
    finally:
        db.close()

def test_tenant_scoping_isolation(trainer_auth_headers, other_tenant_auth_headers):
    # Other college trainer cannot see demo college PR
    res = client.get("/api/v1/trainer/reviews/pr_39", headers=other_tenant_auth_headers)
    assert res.status_code == 404

    # Other college trainer cannot approve demo college PR
    action_payload = {
        "action": "approve",
        "review_feedback": "Cross-tenant attempt."
    }
    res_act = client.post("/api/v1/trainer/reviews/pr_39/action", json=action_payload, headers=other_tenant_auth_headers)
    assert res_act.status_code == 404
