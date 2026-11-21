from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import json

from core.database import get_db
from core.security import get_current_user, TokenPayload, require_role
from core.tenant import get_child_for_parent, get_parent_children, get_user_name
from models.schema import ParentMonthlyRecord, Student, StudentProject, StudentSkill, ProjectDemoEvent, User, Certificate

BAND_TA = {"Placement Ready": "வேலைவாய்ப்புக்கு தயார்", "Nearly Ready": "கிட்டத்தட்ட தயார்", "Needs Support": "ஆதரவு தேவை"}

router = APIRouter(prefix="/parent", tags=["Parent Screens"])

class RSVPRequest(BaseModel):
    event_id: str
    status: str # attending, declined, none
    guest_count: int = 1

# --- SCREEN 15: Parent View (PDF 10) ---
from services.parent_overview import build_parent_overview
from services.audit import record_audit


@router.get("/me/children")
def list_my_children(
    current_user: TokenPayload = Depends(require_role(["parent"])),
    db: Session = Depends(get_db),
):
    children = get_parent_children(current_user, db)
    return {
        "children": [
            {
                "id": c.id,
                "name": get_user_name(db, c.user_id, "Student"),
                "semester": c.semester,
                "branch": c.branch,
                "batch_name": c.batch_name,
            }
            for c in children
        ]
    }


@router.get("/overview")
def get_parent_overview(
    lang: str = "en",
    child_id: Optional[str] = None,
    current_user: TokenPayload = Depends(require_role(["parent"])),
    db: Session = Depends(get_db),
):
    """Screen 15 overview for one child (defaults to the first linked child)."""
    child = get_child_for_parent(current_user, db, child_id)
    child_name = get_user_name(db, child.user_id, "Student")
    return build_parent_overview(db, child, child_name, current_user, lang)


@router.get("/children/{child_id}/overview")
def get_child_overview(
    child_id: str,
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(["parent"])),
    db: Session = Depends(get_db),
):
    child = get_child_for_parent(current_user, db, child_id)
    child_name = get_user_name(db, child.user_id, "Student")
    return build_parent_overview(db, child, child_name, current_user, lang)


@router.post("/rsvp", include_in_schema=False)
def submit_rsvp_legacy(
    req: RSVPRequest,
    current_user: TokenPayload = Depends(require_role(["parent"])),
    db: Session = Depends(get_db),
):
    """Legacy Screen 15 RSVP (ProjectDemoEvent). Kept for the first-generation page."""
    event = db.execute(select(ProjectDemoEvent).filter_by(id=req.event_id, college_id=current_user.college_id)).scalar_one_or_none()
    if event:
        event.rsvp_status = req.status
        event.guest_count = req.guest_count
        db.commit()
    return {"success": True, "message": f"RSVP saved for {req.event_id}. Thank you!"}

# --- SCREEN 33: Parent Projects & Portfolio ---
@router.get("/portfolio")
def get_parent_portfolio(
    lang: str = "en",
    child_id: Optional[str] = None,
    current_user: TokenPayload = Depends(require_role(["parent"])),
    db: Session = Depends(get_db)
):
    college_id = current_user.college_id
    student = get_child_for_parent(current_user, db, child_id)
    ward_name = get_user_name(db, student.user_id, "Student")
    ward_branch = "Sem " + str(student.semester) + " · " + student.branch

    # Query the child's projects inside this tenant
    projects = db.execute(
        select(StudentProject).filter_by(college_id=college_id, student_id=student.id)
    ).scalars().all()

    formatted_projects = []
    for p in projects:
        try:
            stack = json.loads(p.tech_stack) if p.tech_stack else []
        except Exception:
            stack = [s.strip() for s in p.tech_stack.split(",") if s.strip()]

        formatted_projects.append({
            "id": p.id,
            "title": p.title,
            "tagline": p.tagline,
            "category": p.category,
            "what_ward_built": p.parent_summary or p.description,
            "role_description": p.role_description,
            "team_size": p.team_size,
            "team_name": p.team_name,
            "tech_stack": stack,
            "live_demo_url": p.live_demo_url,
            "github_url": p.github_url,
            "status": p.status,
            "score_percent": p.score_percent,
            "trainer_feedback": p.trainer_feedback,
            "is_featured": p.is_featured
        })

    # Query Demo Day event
    event = db.execute(select(ProjectDemoEvent).filter_by(college_id=college_id)).scalar_one_or_none()
    demo_day_info = {
        "id": event.id if event else "event_demo_day_nov",
        "title": event.title if event else "Project Demo Day – Capstone Showcase",
        "event_date": event.event_date if event else "Sat, Nov 8 · 10:00 AM – 1:00 PM",
        "venue": event.venue if event else "Auditorium A & Live Stream",
        "description": event.description if event else "Annual Industry-Ready Engineer Program Capstone Presentation.",
        "rsvp_status": event.rsvp_status if event else "none",
        "guest_count": event.guest_count if event else 1
    }

    return {
        "ward": {
            "name": ward_name,
            "details": ward_branch,
            "college": "Demo Engineering College",
            "readiness_score": student.readiness_score,
            "readiness_band": student.readiness_band if lang == "en" else BAND_TA.get(student.readiness_band, student.readiness_band)
        },
        "milestone_progress": {
            "sprint_name": "Sprint 2 of 3",
            "active_project": "Clinic Appointment & Token System",
            "progress_percent": 58,
            "completed_points": 21,
            "total_points": 36,
            "status_text": "On Track" if lang == "en" else "சரியான பாதையில் உள்ளது",
            "deadline": "Week 8 Capstone Deadline",
            "build_status": "Passing · Deployed to Staging"
        },
        "featured_projects": formatted_projects,
        "mentor_evaluation": {
            "trainer_name": "Arun Kumar",
            "title": "Lead Software Architecture Trainer",
            "remark": "Priya has taken an admirable leadership role in both the Crop Price Predictor and Clinic Appointment projects. Her code passes all automated unit tests, and she collaborates exceptionally well with her engineering peers." if lang == "en" else "பயிர் விலை கணிப்பு மற்றும் கிளினிக் நியமனத் திட்டங்கள் இரண்டிலும் பிரியா பாராட்டத்தக்க தலைமைப் பாத்திரத்தை வகித்துள்ளார். இவரது குறியீடு அனைத்து தானியங்கு சோதனைகளையும் கடந்துள்ளதுடன், சக பொறியாளர்களுடன் மிகச் சிறப்பாக இணைந்து செயல்படுகிறார்."
        },
        "demo_day_invitation": demo_day_info,
        "practical_skills": [
            {
                "skill": "Full-Stack Web Development",
                "tamil_label": "முழுமையான வலைப்பயன்பாட்டு உருவாக்கம்",
                "description": "Able to design and build complete web applications with modern frontend and backend databases.",
                "level": "Proficient"
            },
            {
                "skill": "Machine Learning & AI Modeling",
                "tamil_label": "இயந்திரக் கற்றல் மற்றும் AI மாடலிங்",
                "description": "Applies predictive algorithms to solve real-world agricultural and business forecasting problems.",
                "level": "Advanced"
            },
            {
                "skill": "API & Database Architecture",
                "tamil_label": "API மற்றும் தரவுத்தள வடிவமைப்பு",
                "description": "Designs high-speed, secure data pipelines and structured PostgreSQL storage.",
                "level": "Proficient"
            }
        ]
    }

@router.post("/portfolio/rsvp")
def submit_portfolio_rsvp(
    req: RSVPRequest,
    current_user: TokenPayload = Depends(require_role(["parent"])),
    db: Session = Depends(get_db)
):
    college_id = current_user.college_id
    event = db.execute(select(ProjectDemoEvent).filter_by(id=req.event_id, college_id=college_id)).scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Demo day event not found")

    event.rsvp_status = req.status
    event.guest_count = req.guest_count
    db.commit()

    return {
        "success": True,
        "message": f"RSVP recorded as '{req.status}' for {event.title}",
        "rsvp_status": event.rsvp_status,
        "guest_count": event.guest_count
    }


