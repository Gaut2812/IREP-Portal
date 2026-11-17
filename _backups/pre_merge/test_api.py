import sys
from pathlib import Path

<<<<<<< HEAD
api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

repo_root = str(Path(__file__).resolve().parent.parent.parent.parent)
=======
repo_root = str(Path(__file__).resolve().parents[3])
api_root = str(Path(__file__).resolve().parents[1])
>>>>>>> 785127072bc90e5c4f2d6360d76aebc8b2648e80
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root_and_health():
    response = client.get("/")
    assert response.status_code == 200
    assert "IREP" in response.json()["portal"]

def test_auth_login_student():
    response = client.post("/api/v1/auth/login", json={
        "role": "student",
        "identifier": "priya.r@demo.edu",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "student"

def test_student_dashboard():
    response = client.get("/api/v1/student/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["student"]["readiness_score"] == 74
    assert len(data["skill_progress"]) == 6

def test_coding_lab():
    response = client.get("/api/v1/student/coding/prob_connected_components")
    assert response.status_code == 200
    data = response.json()
    assert "Connected Components" in data["title"]
    assert data["difficulty"] == "Medium"

def test_trainer_dashboard():
    response = client.get("/api/v1/trainer/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["kpis"]["active_batches"]["value"] == "5"

def test_college_dashboard():
    response = client.get("/api/v1/college/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["kpis"]["students_enrolled"]["value"] == "612"

def test_parent_overview():
    response = client.get("/api/v1/parent/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["ward"]["name"] == "Priya R"
    assert data["kpis"]["readiness_score"] == 74

def test_live_classroom():
    response = client.get("/api/v1/live/sess_thu_rag")
    assert response.status_code == 200
    data = response.json()
    assert "LLM APIs & RAG" in data["title"]

