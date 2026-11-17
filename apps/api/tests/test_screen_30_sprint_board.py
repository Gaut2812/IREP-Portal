"""Screen 30 Sprint Board: membership, metrics, moves, PR gate, stand-ups,
change requests, signed GitHub webhook, tenant/role guards."""
import json
import sys
from pathlib import Path

api_root = str(Path(__file__).resolve().parents[1])
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import SprintTask, BuildRun, User, PullRequest
from services.sprint_board import github_signature
from seed.seed_screen30 import seed_screen30

client = TestClient(app)


def _token(sub: str, role: str, college_id: str = "col_demo_001", name: str = "Priya R"):
    return {"Authorization": f"Bearer {create_access_token({'sub': sub, 'role': role, 'college_id': college_id, 'name': name})}"}


PRIYA = _token("usr_priya_01", "student")
ARUN = _token("usr_arun_01", "trainer", name="Arun Kumar")


@pytest.fixture(autouse=True)
def board_state():
    db = SessionLocal()
    try:
        seed_screen30(db)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        seed_screen30(db)
        db.commit()
    finally:
        db.close()


def _cols(d):
    return {c["key"]: [t["id"] for t in c["tasks"]] for c in d["columns"]}


def test_board_matches_pdf6():
    assert client.get("/api/v1/student/projects/my-team", headers=PRIYA).json()["team_id"] == "team_phoenix"
    d = client.get("/api/v1/teams/team_phoenix/board", headers=PRIYA).json()
    assert d["team"]["name"] == "Team Phoenix" and d["team"]["project_title"] == "Clinic Appointment System"
    assert d["sprint"]["number"] == 2 and d["sprint"]["total"] == 3 and d["sprint"]["ends_week"] == 8
    assert d["change_request"]["code"] == "CR-04"
    assert d["metrics"] == {"progress_pct": 58, "points_done": 21, "points_total": 36, "velocity_last": 30, "tasks_done": 4, "tasks_total": 12}
    assert d["build"]["status"] == "passing" and d["build"]["environment"] == "staging"
    cols = _cols(d)
    assert [len(cols[k]) for k in ("todo", "in_progress", "code_review", "done")] == [3, 3, 2, 4]
    review = {t["id"]: t for c in d["columns"] for t in c["tasks"]}
    assert review["task_07"]["pr_number"] == "#41" and review["task_08"]["pr_number"] == "#39"


def test_move_reorders_and_persists():
    r = client.patch("/api/v1/tasks/task_03/move", json={"column": "in_progress", "position": 0}, headers=PRIYA)
    assert r.status_code == 200 and r.json()["position"] == 0
    cols = _cols(client.get("/api/v1/teams/team_phoenix/board", headers=PRIYA).json())
    assert cols["in_progress"][0] == "task_03" and "task_03" not in cols["todo"]
    db = SessionLocal()
    try:
        todo = db.execute(select(SprintTask).filter_by(team_id="team_phoenix", column_name="todo").order_by(SprintTask.position)).scalars().all()
        assert [t.position for t in todo] == list(range(len(todo)))
    finally:
        db.close()
    assert client.patch("/api/v1/tasks/task_03/move", json={"column": "archive"}, headers=PRIYA).status_code == 422


def test_done_requires_approved_pull_request():
    r = client.patch("/api/v1/tasks/task_08/move", json={"column": "done"}, headers=PRIYA)
    assert r.status_code == 409
    # trainer approves PR #39 (Screen 31) -> the card reaches Done
    client.post("/api/v1/trainer/reviews/pr_39/action", json={"action": "approve", "review_feedback": "Good"}, headers=ARUN)
    cols = _cols(client.get("/api/v1/teams/team_phoenix/board", headers=PRIYA).json())
    assert "task_08" in cols["done"]
    # cards without a PR move freely
    assert client.patch("/api/v1/tasks/task_09/move", json={"column": "todo"}, headers=PRIYA).status_code == 200


def test_standup_upsert_and_list():
    body = {"yesterday": "Prompt chaining for triage", "today": "Unit tests", "blockers": "Waiting on PR #39 review"}
    a = client.post("/api/v1/sprints/sprint_phoenix_2/standups", json=body, headers=PRIYA)
    b = client.post("/api/v1/sprints/sprint_phoenix_2/standups", json={**body, "today": "Booking tests"}, headers=PRIYA)
    assert a.json()["standup_id"] == b.json()["standup_id"]
    rows = client.get("/api/v1/sprints/sprint_phoenix_2/standups", headers=ARUN).json()["standups"]
    mine = [r for r in rows if r["name"] == "Priya R"]
    assert mine and mine[0]["today"] == "Booking tests"
    assert client.post("/api/v1/sprints/sprint_phoenix_2/standups", json={"yesterday": "x"}, headers=PRIYA).status_code == 422


def test_trainer_change_request_adds_card():
    assert client.post("/api/v1/teams/team_phoenix/change-requests", json={"title": "Export to PDF"}, headers=PRIYA).status_code == 403
    r = client.post("/api/v1/teams/team_phoenix/change-requests", json={"title": "Export to PDF", "description": "Clinic wants PDF slips"}, headers=ARUN)
    assert r.status_code == 200 and r.json()["code"] == "CR-02"
    d = client.get("/api/v1/teams/team_phoenix/board", headers=PRIYA).json()
    assert _cols(d)["todo"][0] == r.json()["task_id"]
    assert d["metrics"]["points_total"] == 39


def test_github_webhook_signed_events():
    def post(event: str, payload: dict, sign=True):
        body = json.dumps(payload).encode()
        headers = {"X-GitHub-Event": event, "Content-Type": "application/json"}
        if sign:
            headers["X-Hub-Signature-256"] = github_signature(body)
        return client.post("/api/v1/webhooks/github", content=body, headers=headers)

    repo = {"full_name": "irep-demo/clinic-appointment-system"}
    assert post("pull_request", {"action": "closed", "repository": repo, "pull_request": {"number": 41, "merged": True}}, sign=False).status_code == 401
    r = post("pull_request", {"action": "closed", "repository": repo, "pull_request": {"number": 41, "merged": True}})
    assert r.status_code == 200 and r.json()["column"] == "done"
    r = post("workflow_run", {"action": "completed", "repository": repo, "workflow_run": {"run_number": 449, "name": "CI", "conclusion": "failure", "html_url": "https://example.com/449"}})
    assert r.json()["build"] == "failing"
    d = client.get("/api/v1/teams/team_phoenix/board", headers=PRIYA).json()
    assert d["build"]["status"] == "failing" and d["build"]["run_number"] == 449
    assert "task_07" in _cols(d)["done"]
    assert post("pull_request", {"action": "opened", "repository": {"full_name": "someone/else"}, "pull_request": {"number": 1}}).json().get("ignored")


def test_guards():
    db = SessionLocal()
    try:
        outsider = db.execute(select(User).filter_by(name="Divya M")).scalars().first()
    finally:
        db.close()
    other = _token(outsider.id, "student", name="Divya M")
    assert client.get("/api/v1/teams/team_phoenix/board", headers=other).status_code == 404
    assert client.patch("/api/v1/tasks/task_03/move", json={"column": "done"}, headers=other).status_code == 404
    assert client.get("/api/v1/teams/team_phoenix/board", headers=_token("usr_meena_01", "trainer", name="Meena S")).status_code == 404
    assert client.get("/api/v1/teams/team_phoenix/board", headers=_token("usr_ramesh_01", "parent")).status_code == 403
    assert client.get("/api/v1/teams/team_phoenix/board", headers=_token("usr_priya_01", "student", college_id="col_other_999")).status_code == 404
    assert client.get("/api/v1/teams/team_phoenix/board", headers=ARUN).status_code == 200
