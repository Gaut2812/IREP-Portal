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
    child = get_child_for_parent(current_user, db, child_id)
    child_name = get_user_name(db, child.user_id, "Student")
    records = db.execute(
        select(ParentMonthlyRecord).filter_by(student_id=child.id, college_id=current_user.college_id)
    ).scalars().all()
    certs = db.execute(
        select(Certificate).filter_by(student_id=child.id, college_id=current_user.college_id)
    ).scalars().all()
    earned = [c for c in certs if c.status == "earned"]
    scheduled = [c for c in certs if c.status == "scheduled" and c.exam_date]
    cert_note = ""
    if scheduled:
        cert_note = scheduled[0].title.split(" ")[0] + " exam on " + scheduled[0].exam_date.strftime("%b %d")
    good_attendance = child.attendance_pct >= 85

    return {
        "ward": {
            "id": child.id,
            "name": child_name,
            "details": "Sem " + str(child.semester) + " · " + child.branch,
            "college": "Demo Engineering College"
        },
        "kpis": {
            "readiness_score": child.readiness_score,
            "readiness_delta": ("+" if child.readiness_delta >= 0 else "") + str(child.readiness_delta),
            "readiness_band": child.readiness_band if lang == "en" else BAND_TA.get(child.readiness_band, child.readiness_band),
            "attendance": str(child.attendance_pct) + "%",
            "attendance_note": ("Excellent" if good_attendance else "Needs attention") if lang == "en" else ("சிறப்பானது" if good_attendance else "கவனம் தேவை"),
            "problems_solved": child.problems_solved,
            "certifications": str(len(earned)),
            "cert_note": cert_note
        },
        "monthly_progress": [
            {
                "area": r.area,
                "september": r.prev_month_val,
                "october": r.curr_month_val,
                "status": r.status_text,
                "color": r.status_color
            }
            for r in records
        ],
        "how_you_can_help": {
            "en": "Encourage 10 minutes of spoken English daily and ask Priya to explain her project to you at home.",
            "ta": "தினமும் 10 நிமிடங்கள் வீட்டில் ஆங்கிலத்தில் பேச ஊக்குவிக்கவும், மேலும் பிரியாவிடம் அவரது புராஜெக்ட் பற்றி விளக்குமாறு கேட்கவும்."
        },
        "trainer_remark": {
            "month": "October",
            "trainer_name": "Arun Kumar",
            "en": "Priya showed outstanding consistency in coding lab problems this month. If she focuses on thinking aloud during mock interviews, she will easily attain top-tier product company placement readiness.",
            "ta": "இந்த மாதம் கோடிங் பயிற்சியில் பிரியா சிறப்பான அர்ப்பணிப்பைக் காட்டியுள்ளார். மாக் இன்டர்வியூவில் யோசனைகளை உரக்க வெளிப்படுத்துவதில் கவனம் செலுத்தினால் எளிதில் முன்னணி நிறுவனங்களின் வேலைவாய்ப்பைப் பெறுவார்."
        },
        "invitations": [
            {
                "id": "event_demo_day",
                "title": "Project Demo Day",
                "when": "Sat, Nov 8 · 10:00 AM",
                "subtitle": "You are invited to watch students present live projects",
                "rsvp_status": "none"
            }
        ],
        "portfolio": {
            "github_projects": 5,
            "live_project": "Crop Price Predictor",
            "demo_video": "Sem 4 project available"
        }
    }

@router.post("/rsvp")
def submit_rsvp(
    req: RSVPRequest,
    current_user: TokenPayload = Depends(require_role(["parent"])),
    db: Session = Depends(get_db),
):
    event = db.execute(select(ProjectDemoEvent).filter_by(id=req.event_id, college_id=current_user.college_id)).scalar_one_or_none()
    if event:
        event.rsvp_status = req.status
        event.guest_count = req.guest_count
        db.commit()
    return {
        "success": True,
        "message": f"RSVP saved for {req.event_id}. Thank you!"
    }

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


