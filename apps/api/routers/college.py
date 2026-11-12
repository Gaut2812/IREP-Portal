from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db

router = APIRouter(prefix="/college", tags=["College Screens"])

# --- SCREEN 19: College / Placement Cell Dashboard (PDF 9) ---
@router.get("/dashboard")
def get_college_dashboard(db: Session = Depends(get_db)):
    return {
        "college_name": "Demo Engineering College",
        "title": "Program Overview",
        "kpis": {
            "students_enrolled": {"value": "612", "subtext": "Sem 2 to 7 · 4 branches"},
            "avg_attendance": {"value": "89%", "subtext": "Above 85% target", "status": "positive"},
            "certifications": {"value": "184", "subtext": "▲ 41 this semester", "status": "positive"},
            "internships": {"value": "73", "subtext": "Sem 6 batch · 64%", "status": "positive"}
        },
        "readiness_distribution": [
            {"band": "Placement Ready", "percentage": 48, "color": "green"},
            {"band": "Nearly Ready", "percentage": 36, "color": "amber"},
            {"band": "Needs Support", "percentage": 16, "color": "red"}
        ],
        "branch_readiness": [
            {"branch": "CSE", "students": 228, "attendance": "91%", "avg_score": 78, "trend": "+5"},
            {"branch": "IT", "students": 164, "attendance": "88%", "avg_score": 73, "trend": "+3"},
            {"branch": "AI & DS", "students": 142, "attendance": "90%", "avg_score": 77, "trend": "+6"},
            {"branch": "Cybersecurity", "students": 78, "attendance": "86%", "avg_score": 70, "trend": "+2"}
        ],
        "cumulative_certifications": [
            {"month": "Jun", "count": 28},
            {"month": "Jul", "count": 54},
            {"month": "Aug", "count": 92},
            {"month": "Sep", "count": 143},
            {"month": "Oct", "count": 184}
        ],
        "upcoming_events": [
            {"title": "Mock Drive 1 · Sem 7", "date": "Oct 25"},
            {"title": "Project Demo Day", "date": "Nov 8"},
            {"title": "Parent review meeting", "date": "Nov 15"},
            {"title": "Guest session: GCC leaders", "date": "Nov 22"}
        ],
        "mou_reports": [
            {"title": "September progress report", "type": "PDF", "size": "1.2 MB"},
            {"title": "Sem 4 performance report", "type": "PDF", "size": "2.4 MB"},
            {"title": "Placement readiness analysis", "type": "PDF", "size": "1.8 MB"}
        ]
    }

