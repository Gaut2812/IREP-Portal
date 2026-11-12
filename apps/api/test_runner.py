import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parent.parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import asyncio
from httpx import AsyncClient, ASGITransport
from apps.api.main import app

async def run_all_tests():
    print("Initializing HTTPX AsyncClient with ASGITransport...", flush=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("Testing / ...", flush=True)
        res = await client.get("/")
        assert res.status_code == 200, f"Root failed: {res.text}"
        print("PASS: /", flush=True)

        print("Testing /api/v1/auth/login ...", flush=True)
        res = await client.post("/api/v1/auth/login", json={
            "role": "student",
            "identifier": "priya.r@demo.edu",
            "password": "password123"
        })
        assert res.status_code == 200, f"Login failed: {res.text}"
        token = res.json()["access_token"]
        print("PASS: login successful, token received!", flush=True)

        headers = {"Authorization": f"Bearer {token}"}

        print("Testing /api/v1/student/dashboard ...", flush=True)
        res = await client.get("/api/v1/student/dashboard", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["student"]["readiness_score"] == 74
        print(f"PASS: Student Dashboard! Score: {data['student']['readiness_score']}", flush=True)

        print("Testing /api/v1/student/coding/prob_connected_components ...", flush=True)
        res = await client.get("/api/v1/student/coding/prob_connected_components", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Coding Lab! Problem: {res.json()['title']}", flush=True)

        print("Testing /api/v1/student/tests/test_service_aptitude ...", flush=True)
        res = await client.get("/api/v1/student/tests/test_service_aptitude", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Practice Tests! Total questions: {len(res.json()['questions'])}", flush=True)

        print("Testing /api/v1/student/labs ...", flush=True)
        res = await client.get("/api/v1/student/labs", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Virtual Labs! Active session: {res.json()['active_session']['lab_name']}", flush=True)

        print("Testing /api/v1/student/projects/board ...", flush=True)
        res = await client.get("/api/v1/student/projects/board", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Sprint Board! Team: {res.json()['team_name']}, Progress: {res.json()['progress_pct']}%", flush=True)

        print("Testing /api/v1/student/interviews ...", flush=True)
        res = await client.get("/api/v1/student/interviews", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Mock Interviews! Score: {res.json()['latest_interview']['overall_score']}", flush=True)

        print("Testing /api/v1/trainer/dashboard ...", flush=True)
        res = await client.get("/api/v1/trainer/dashboard", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Trainer Dashboard! Batches: {res.json()['kpis']['active_batches']['value']}", flush=True)

        print("Testing /api/v1/college/dashboard ...", flush=True)
        res = await client.get("/api/v1/college/dashboard", headers=headers)
        assert res.status_code == 200
        print(f"PASS: College Dashboard! Enrolled: {res.json()['kpis']['students_enrolled']['value']}", flush=True)

        print("Testing /api/v1/parent/overview ...", flush=True)
        res = await client.get("/api/v1/parent/overview", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Parent View! Ward: {res.json()['ward']['name']}", flush=True)

        print("Testing /api/v1/live/sess_thu_rag ...", flush=True)
        res = await client.get("/api/v1/live/sess_thu_rag", headers=headers)
        assert res.status_code == 200
        print(f"PASS: Live Classroom! Title: {res.json()['title']}", flush=True)

        print("\n>>> ALL 12 BACKEND ENDPOINTS TESTED AND VERIFIED 100% OPERATIONAL! <<<", flush=True)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
