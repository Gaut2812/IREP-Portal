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
    status: str  # attending or declined (yes / no / maybe also accepted)
    guest_count: int = 1  # 0..10
    child_id: Optional[str] = None  # parents of two children say which one; default: the first linked child

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
    """Legacy Screen 15 RSVP. Stored per parent like every RSVP (it used to overwrite one shared row)."""
    _save_card_rsvp(db, current_user, req)
    db.commit()
    return {"success": True, "message": f"RSVP saved for {req.event_id}. Thank you!"}


CARD_STATUS = {"attending": "yes", "declined": "no", "yes": "yes", "no": "no", "maybe": "maybe"}


def _save_card_rsvp(db: Session, current_user: TokenPayload, req: "RSVPRequest"):
    from routers.events import save_parent_rsvp
    status = CARD_STATUS.get((req.status or "").strip().lower())
    if status is None:
        raise HTTPException(status_code=422, detail="status must be attending or declined")
    return save_parent_rsvp(db, current_user, req.event_id, status, req.guest_count, req.child_id)

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

    # The next real event that takes RSVPs (a demo day first), with this parent's own answer; None when there is none
    from routers.events import next_demo_day_for_parent
    demo_day_info = next_demo_day_for_parent(db, current_user, student, lang)

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
    rsvp = _save_card_rsvp(db, current_user, req)
    db.commit()
    card = {"yes": "attending", "no": "declined", "maybe": "maybe"}[rsvp.status]
    return {
        "success": True,
        "message": f"RSVP recorded as '{card}'",
        "rsvp_status": card,
        "guest_count": rsvp.guests
    }


