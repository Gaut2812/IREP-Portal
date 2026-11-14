from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import json

from core.database import get_db
from core.security import get_current_user, TokenPayload
from models.schema import ParentMonthlyRecord, Student, StudentProject, StudentSkill, ProjectDemoEvent, User

router = APIRouter(prefix="/parent", tags=["Parent Screens"])

class RSVPRequest(BaseModel):
    event_id: str
    status: str # attending, declined, none
    guest_count: int = 1

# --- SCREEN 15: Parent View (PDF 10) ---
@router.get("/overview")
def get_parent_overview(lang: str = "en", db: Session = Depends(get_db)):
    records = db.execute(select(ParentMonthlyRecord)).scalars().all()
    
    return {
        "ward": {
            "name": "Priya R",
            "details": "Sem 5 · AI & DS",
            "college": "Demo Engineering College"
        },
        "kpis": {
            "readiness_score": 74,
            "readiness_delta": "+6",
            "readiness_band": "Nearly Ready" if lang == "en" else "கிட்டத்தட்ட தயார்",
            "attendance": "92%",
            "attendance_note": "Excellent" if lang == "en" else "சிறப்பானது",
            "problems_solved": 286,
            "certifications": "1",
            "cert_note": "AWS exam on Nov 22"
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
def submit_rsvp(req: RSVPRequest, db: Session = Depends(get_db)):
    event = db.execute(select(ProjectDemoEvent).filter_by(id=req.event_id)).scalar_one_or_none()
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
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    college_id = current_user.college_id if isinstance(current_user, TokenPayload) else "col_demo_001"
    
    student = db.execute(select(Student).filter_by(college_id=college_id)).scalar_one_or_none()
    ward_name = "Priya R"
    if student:
        user = db.execute(select(User).filter_by(id=student.user_id)).scalar_one_or_none()
        if user and user.name:
            ward_name = user.name
    ward_branch = f"Sem {student.semester if student else 5} · {student.branch if student else 'AI & DS'}"

    # Query student projects for this tenant
    projects = db.execute(
        select(StudentProject).filter_by(college_id=college_id)
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
            "readiness_score": 74,
            "readiness_band": "Nearly Ready" if lang == "en" else "கிட்டத்தட்ட தயார்"
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
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    college_id = current_user.college_id if isinstance(current_user, TokenPayload) else "col_demo_001"
    event = db.execute(select(ProjectDemoEvent).filter_by(id=req.event_id, college_id=college_id)).scalar_one_or_none()
    
    if not event:
        # Fallback without college filter if cross-checking
        event = db.execute(select(ProjectDemoEvent).filter_by(id=req.event_id)).scalar_one_or_none()

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


