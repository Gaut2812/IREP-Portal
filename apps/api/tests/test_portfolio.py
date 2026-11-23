import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models.schema import StudentProject, StudentSkill, ProjectDemoEvent

client = TestClient(app)

@pytest.fixture
def student_auth_headers():
    token = create_access_token(data={
        "sub": "usr_priya_01",
        "role": "student",
        "college_id": "col_demo_001",
        "name": "Priya R"
    })
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def other_tenant_auth_headers():
    token = create_access_token(data={
        "sub": "usr_other_99",
        "role": "student",
        "college_id": "col_other_999",
        "name": "Other Student"
    })
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def parent_auth_headers():
    token = create_access_token(data={
        "sub": "usr_ramesh_01",
        "role": "parent",
        "college_id": "col_demo_001",
        "name": "Mr. Ramesh K"
    })
    return {"Authorization": f"Bearer {token}"}

def test_get_student_portfolio_success(student_auth_headers):
    response = client.get("/api/v1/student/portfolio", headers=student_auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert "student" in data
    assert data["student"]["name"] == "Priya R"
    assert data["student"]["readiness_score"] >= 74
    assert data["student"]["branch"] == "AI & DS"

    assert "projects" in data
    assert len(data["projects"]) >= 2
    titles = [p["title"] for p in data["projects"]]
    assert "Crop Price Predictor" in titles
    assert "Clinic Appointment & Token System" in titles

    # Check tech stack is parsed list
    crop_proj = next(p for p in data["projects"] if p["title"] == "Crop Price Predictor")
    assert isinstance(crop_proj["tech_stack"], list)
    assert "FastAPI" in crop_proj["tech_stack"]
    assert crop_proj["trainer_verified"] is True

    # Check skills
    assert "verified_skills" in data
    assert len(data["verified_skills"]) >= 4
    skill_names = [s["skill_name"] for s in data["verified_skills"]]
    assert "Data Structures & Algorithms" in skill_names

def test_crud_student_portfolio_project(student_auth_headers):
    # 1. Create project
    create_payload = {
        "title": "Autonomous Drone Fleet Tracker",
        "tagline": "Real-time telemetry and battery life estimation for quadcopters",
        "category": "iot",
        "description": "Engineered drone flight log ingestion via WebSockets and Kalman filter trajectory prediction.",
        "parent_summary": "Priya built a live radar screen that monitors delivery drone flights and battery levels.",
        "role_description": "Designed WebSocket server and Kalman filter trajectory estimation in Python.",
        "team_size": 2,
        "team_name": "Team AeroTrack",
        "tech_stack": ["Python", "FastAPI", "WebSockets", "NumPy"],
        "github_url": "https://github.com/priya-r/drone-fleet-tracker",
        "live_demo_url": "https://drone-demo.demo.edu",
        "status": "deployed",
        "is_featured": True
    }
    create_res = client.post("/api/v1/student/portfolio/projects", json=create_payload, headers=student_auth_headers)
    assert create_res.status_code == 200
    created_data = create_res.json()
    assert created_data["success"] is True
    proj_id = created_data["project"]["id"]

    # Verify persisted in DB
    db = SessionLocal()
    try:
        p_db = db.execute(select(StudentProject).filter_by(id=proj_id)).scalar_one_or_none()
        assert p_db is not None
        assert p_db.title == "Autonomous Drone Fleet Tracker"
        assert p_db.college_id == "col_demo_001"
    finally:
        db.close()

    # 2. Update project
    update_payload = {
        "title": "Autonomous Drone Fleet Tracker v2",
        "team_size": 3,
        "tech_stack": ["Python", "FastAPI", "WebSockets", "NumPy", "Docker"]
    }
    update_res = client.put(f"/api/v1/student/portfolio/projects/{proj_id}", json=update_payload, headers=student_auth_headers)
    assert update_res.status_code == 200

    # 3. Delete project
    del_res = client.delete(f"/api/v1/student/portfolio/projects/{proj_id}", headers=student_auth_headers)
    assert del_res.status_code == 200

    # Verify deleted from DB
    db = SessionLocal()
    try:
        p_db_deleted = db.execute(select(StudentProject).filter_by(id=proj_id)).scalar_one_or_none()
        assert p_db_deleted is None
    finally:
        db.close()

def test_tenant_scoping_isolation(student_auth_headers, other_tenant_auth_headers):
    # Other tenant cannot access or update demo college project
    res = client.put(
        "/api/v1/student/portfolio/projects/proj_crop_01",
        json={"title": "Hacked Title"},
        headers=other_tenant_auth_headers
    )
    assert res.status_code == 404

    # Other tenant cannot delete demo college project
    res_del = client.delete(
        "/api/v1/student/portfolio/projects/proj_crop_01",
        headers=other_tenant_auth_headers
    )
    assert res_del.status_code == 404

@pytest.mark.link("L15")
def test_get_parent_portfolio(parent_auth_headers):
    response = client.get("/api/v1/parent/portfolio", headers=parent_auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert "ward" in data
    assert data["ward"]["name"] == "Priya R"

    assert "milestone_progress" in data
    assert data["milestone_progress"]["progress_percent"] == 58
    assert "Sprint 2" in data["milestone_progress"]["sprint_name"]

    assert "featured_projects" in data
    assert len(data["featured_projects"]) >= 2
    # Ensure what_ward_built is populated for parents
    for p in data["featured_projects"]:
        assert "what_ward_built" in p
        assert len(p["what_ward_built"]) > 10

    assert "demo_day_invitation" in data
    assert "Project Demo Day" in data["demo_day_invitation"]["title"]
    assert "event_date" in data["demo_day_invitation"]

    assert "mentor_evaluation" in data
    assert data["mentor_evaluation"]["trainer_name"] == "Arun Kumar"

def test_parent_demo_day_rsvp(parent_auth_headers):
    # RSVP attending
    rsvp_payload = {
        "event_id": "event_demo_day_nov",
        "status": "attending",
        "guest_count": 2
    }
    res = client.post("/api/v1/parent/portfolio/rsvp", json=rsvp_payload, headers=parent_auth_headers)
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["rsvp_status"] == "attending"

    # Verify database state
    db = SessionLocal()
    try:
        ev = db.execute(select(ProjectDemoEvent).filter_by(id="event_demo_day_nov")).scalar_one_or_none()
        assert ev is not None
        assert ev.rsvp_status == "attending"
        assert ev.guest_count == 2
    finally:
        db.close()

    # RSVP declined
    rsvp_payload_decline = {
        "event_id": "event_demo_day_nov",
        "status": "declined",
        "guest_count": 1
    }
    res_dec = client.post("/api/v1/parent/portfolio/rsvp", json=rsvp_payload_decline, headers=parent_auth_headers)
    assert res_dec.status_code == 200
    assert res_dec.json()["rsvp_status"] == "declined"
