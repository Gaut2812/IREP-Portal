import sys
sys.path.insert(0, r"d:\IREP Portal")

from apps.api.core.database import SessionLocal
from apps.api.routers import student, trainer, college, parent, live
from apps.api.core.security import TokenPayload

def test_direct_functions():
    db = SessionLocal()
    try:
        user = TokenPayload(
            sub="usr_priya_01",
            email="priya.r@demo.edu",
            role="student",
            college_id="col_demo_001",
            name="Priya R",
            avatar="PR"
        )
        
        print("1. Testing student.get_student_dashboard...", flush=True)
        res = student.get_student_dashboard(current_user=user, db=db)
        print("Student dashboard score:", res["student"]["readiness_score"], flush=True)
        assert res["student"]["readiness_score"] == 74
        
        print("2. Testing student.get_coding_problem...", flush=True)
        prob = student.get_coding_problem("prob_connected_components", db=db)
        print("Coding problem title:", prob["title"], flush=True)
        assert "Connected Components" in prob["title"]
        
        print("3. Testing student.get_practice_test...", flush=True)
        test = student.get_practice_test("test_service_aptitude", db=db)
        print("Practice test questions:", len(test["questions"]), flush=True)
        assert len(test["questions"]) == 30
        
        print("4. Testing student.get_virtual_labs...", flush=True)
        labs = student.get_virtual_labs(db=db)
        print("Virtual labs count:", len(labs["labs"]), flush=True)
        assert len(labs["labs"]) == 6
        
        print("5. Testing student.get_sprint_board...", flush=True)
        board = student.get_sprint_board(db=db)
        print("Sprint board team:", board["team_name"], "Progress:", board["progress_pct"], flush=True)
        assert board["progress_pct"] == 58
        
        print("6. Testing student.get_mock_interviews...", flush=True)
        interviews = student.get_mock_interviews(db=db)
        print("Mock interview score:", interviews["latest_interview"]["overall_score"], flush=True)
        assert interviews["latest_interview"]["overall_score"] == 3.8
        
        print("7. Testing trainer.get_trainer_dashboard...", flush=True)
        t_dash = trainer.get_trainer_dashboard(db=db)
        print("Trainer active batches:", t_dash["kpis"]["active_batches"]["value"], flush=True)
        assert t_dash["kpis"]["active_batches"]["value"] == "5"
        
        print("8. Testing college.get_college_dashboard...", flush=True)
        c_dash = college.get_college_dashboard(db=db)
        print("College enrolled students:", c_dash["kpis"]["students_enrolled"]["value"], flush=True)
        assert c_dash["kpis"]["students_enrolled"]["value"] == "612"
        
        print("9. Testing parent.get_parent_overview...", flush=True)
        p_view = parent.get_parent_overview(lang="en", db=db)
        print("Parent view ward:", p_view["ward"]["name"], flush=True)
        assert p_view["ward"]["name"] == "Priya R"
        
        print("10. Testing live.get_live_classroom_state...", flush=True)
        live_room = live.get_live_classroom_state("sess_thu_rag")
        print("Live classroom title:", live_room["title"], flush=True)
        assert "LLM APIs & RAG" in live_room["title"]
        
        print("\n=======================================================", flush=True)
        print("SUCCESS! ALL 10 MODULES DIRECTLY VERIFIED & WORKING!", flush=True)
        print("=======================================================", flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    test_direct_functions()
