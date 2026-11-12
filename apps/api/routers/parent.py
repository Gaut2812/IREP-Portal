from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from apps.api.core.database import get_db
from apps.api.models.schema import ParentMonthlyRecord, Student

router = APIRouter(prefix="/parent", tags=["Parent Screens"])

class RSVPRequest(BaseModel):
    event_id: str
    status: str # attending, cannot_attend, maybe
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
def submit_rsvp(req: RSVPRequest):
    return {
        "success": True,
        "message": f"RSVP saved for {req.event_id}. Thank you!"
    }
