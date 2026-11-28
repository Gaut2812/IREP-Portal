"""Sprint Board (screen 30), Phase 2: project details on the board, students add/edit/delete cards, trainers create
and run projects (teams) for their batches."""
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import Notification, PullRequest, Sprint, SprintTask, Team, TeamMember

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN, RAMESH = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_ramesh_01", "parent")
TEAM = "team_phoenix"


@pytest.fixture
def cleanup_tasks():
    made = []
    yield made
    with SessionLocal() as db:
        db.execute(delete(SprintTask).where(SprintTask.id.in_(made or ["_"])))
        db.commit()


def test_board_shows_project_details_and_members():
    b = client.get(f"/api/v1/teams/{TEAM}/board", headers=PRIYA).json()
    assert b["team"]["description"] and len(b["team"]["goals"]) >= 3
    names = [m["name"] for m in b["member_list"]]
    assert "Priya R" in names and b["member_list"][0]["role"] == "lead"
    assert b["can_manage"] is False
    assert client.get(f"/api/v1/teams/{TEAM}/board", headers=ARUN).json()["can_manage"] is True


def test_student_adds_edits_and_deletes_own_card(cleanup_tasks):
    board = client.get(f"/api/v1/teams/{TEAM}/board", headers=PRIYA).json()
    other = next(m for m in board["member_list"] if m["name"] != "Priya R")
    r = client.post(f"/api/v1/teams/{TEAM}/tasks", headers=PRIYA,
                    json={"title": "Write booking API tests", "tag_type": "qa", "story_points": 2, "assignee_student_id": other["student_id"]})
    assert r.status_code == 201
    tid = r.json()["task_id"]
    cleanup_tasks.append(tid)
    todo = next(c for c in client.get(f"/api/v1/teams/{TEAM}/board", headers=PRIYA).json()["columns"] if c["key"] == "todo")
    card = next(t for t in todo["tasks"] if t["id"] == tid)
    assert card["tag"] == "QA" and card["assignee_name"] == other["name"] and card["can_delete"] is True and todo["tasks"][0]["id"] == tid

    assert client.patch(f"/api/v1/tasks/{tid}", headers=PRIYA, json={"title": "Write booking API tests (pytest)", "story_points": 3, "unassign": True}).status_code == 200
    with SessionLocal() as db:
        t = db.get(SprintTask, tid)
        assert t.title.endswith("(pytest)") and t.story_points == 3 and t.assignee_student_id is None and t.created_by_student_id == "std_priya_01"
    assert client.delete(f"/api/v1/tasks/{tid}", headers=PRIYA).status_code == 200
    with SessionLocal() as db:
        assert db.get(SprintTask, tid) is None


def test_card_rules():
    assert client.post(f"/api/v1/teams/{TEAM}/tasks", headers=PRIYA,
                       json={"title": "Assign outside", "assignee_student_id": "std_cse_2_001_6c05"}).status_code == 422   # not a member
    assert client.post(f"/api/v1/teams/{TEAM}/tasks", headers=RAMESH, json={"title": "Parent card"}).status_code == 403
    assert client.post(f"/api/v1/teams/{TEAM}/tasks", headers=_h("usr_priya_01", "student", "col_other_999"), json={"title": "x y z"}).status_code == 404
    with SessionLocal() as db:
        cards = db.execute(select(SprintTask).where(SprintTask.team_id == TEAM)).scalars().all()
        reviewed = set(db.execute(select(PullRequest.task_id)).scalars())
        someone_elses = next(t for t in cards if t.assignee_student_id not in (None, "std_priya_01") and not t.pr_number
                             and t.id not in reviewed and t.column_name != "done")
        with_pr = next(t for t in cards if t.pr_number or t.id in reviewed)
    assert client.delete(f"/api/v1/tasks/{someone_elses.id}", headers=PRIYA).status_code == 403    # not hers
    assert client.delete(f"/api/v1/tasks/{with_pr.id}", headers=ARUN).status_code == 409           # review history points at it


def test_trainer_creates_runs_and_deletes_a_project():
    listing = client.get("/api/v1/trainer/projects", headers=ARUN).json()
    assert any(p["id"] == TEAM for p in listing["projects"])
    free = [s["student_id"] for s in listing["students"] if not s["team_id"]][:3]
    taken = next(s["student_id"] for s in listing["students"] if s["team_id"] == TEAM)
    body = {"name": f"Team {uuid.uuid4().hex[:4]}", "project_title": "Library seat booking", "description": "Book a reading-room seat.",
            "goals": "Book a seat\nSee free seats live", "total_sprints": 2, "sprint_goal": "Login and seat map",
            "member_ids": free, "lead_id": free[0]}
    assert client.post("/api/v1/trainer/projects", headers=ARUN, json={**body, "member_ids": [taken]}).status_code == 409   # already in a team
    assert client.post("/api/v1/trainer/projects", headers=ARUN, json={**body, "member_ids": ["std_not_mine"]}).status_code == 422
    assert client.post("/api/v1/trainer/projects", headers=PRIYA, json=body).status_code == 403
    made = client.post("/api/v1/trainer/projects", headers=ARUN, json=body)
    assert made.status_code == 201
    pid = made.json()["id"]
    try:
        assert made.json()["sprint"]["number"] == 1 and made.json()["members"][0]["role"] == "lead"
        task = client.post(f"/api/v1/teams/{pid}/tasks", headers=ARUN, json={"title": "Seat map UI"}).json()["task_id"]
        nxt = client.post(f"/api/v1/trainer/projects/{pid}/next-sprint", headers=ARUN, json={"goal": "Live availability"}).json()
        assert nxt["sprint"]["number"] == 2
        with SessionLocal() as db:
            assert db.get(SprintTask, task).sprint_id == nxt["sprint"]["id"]                         # unfinished card moved along
        assert client.post(f"/api/v1/trainer/projects/{pid}/next-sprint", headers=ARUN, json={}).status_code == 409   # last sprint
        edited = client.put(f"/api/v1/trainer/projects/{pid}", headers=ARUN, json={"description": "Updated", "repo_full_name": "irep/library"}).json()
        assert edited["description"] == "Updated" and edited["repo"] == "irep/library"
        assert client.delete(f"/api/v1/trainer/projects/{pid}", headers=ARUN).status_code == 200
        with SessionLocal() as db:
            assert db.get(Team, pid) is None and not db.execute(select(TeamMember.id).where(TeamMember.team_id == pid)).first()
        assert client.delete(f"/api/v1/trainer/projects/{TEAM}", headers=ARUN).status_code == 409    # has PRs and stand-ups
    finally:
        with SessionLocal() as db:
            db.execute(delete(SprintTask).where(SprintTask.team_id == pid))
            db.execute(delete(Sprint).where(Sprint.team_id == pid))
            db.execute(delete(TeamMember).where(TeamMember.team_id == pid))
            db.execute(delete(Team).where(Team.id == pid))
            db.execute(delete(Notification).where(Notification.title_en == "New project: Library seat booking"))
            db.commit()
