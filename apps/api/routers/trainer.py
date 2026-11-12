from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
import datetime

from apps.api.core.database import get_db
from apps.api.core.security import get_current_user, TokenPayload
from apps.api.models.schema import TrainerDirectThread, DirectMessage

router = APIRouter(prefix="/trainer", tags=["Trainer Screens"])

# --- SCREEN 13: Trainer Dashboard (PDF 8) ---
@router.get("/dashboard")
def get_trainer_dashboard(db: Session = Depends(get_db)):
    return {
        "kpis": {
            "active_batches": {"value": "5", "subtext": "248 students · 2 colleges"},
            "today_attendance": {"value": "91%", "subtext": "▲ 3% vs last week", "delta_positive": True},
            "pending_code_reviews": {"value": "17", "subtext": "6 older than 2 days", "warning": True},
            "at_risk_students": {"value": "12", "subtext": "Parents notified: 9"}
        },
        "batch_readiness": [
            {"batch": "CSE-A", "score": 82, "color": "teal"},
            {"batch": "CSE-B", "score": 76, "color": "teal"},
            {"batch": "IT-A", "score": 71, "color": "blue"},
            {"batch": "AI & DS", "score": 79, "color": "teal"},
            {"batch": "Cyber", "score": 68, "color": "blue"}
        ],
        "today_schedule": [
            {"time": "9:00 AM", "batch": "CSE-A · Sem 5", "topic": "System design basics", "status": "Done", "status_color": "green"},
            {"time": "11:00 AM", "batch": "AI & DS · Sem 5", "topic": "LLM APIs & RAG", "status": "Next", "status_color": "blue"},
            {"time": "2:00 PM", "batch": "IT-A · Sem 4", "topic": "SQL window functions", "status": "Later", "status_color": "grey"},
            {"time": "3:30 PM", "batch": "Cyber · Sem 5", "topic": "OWASP lab: XSS", "status": "Later", "status_color": "grey"}
        ],
        "students_needing_support": [
            {"name": "Karthik S.", "batch": "CSE-B", "score": 52, "issue": "Attendance 71%", "action": "Parent call", "action_color": "red"},
            {"name": "Divya M.", "batch": "IT-A", "score": 56, "issue": "DSA tests", "action": "Extra Sat", "action_color": "amber"},
            {"name": "Rahul V.", "batch": "Cyber", "score": 58, "issue": "Project delay", "action": "Mentor", "action_color": "blue"}
        ],
        "quick_actions": [
            {"label": "Mark attendance", "type": "primary", "variant": "blue"},
            {"label": "Create test", "type": "outline", "variant": "default"},
            {"label": "Review PRs", "type": "outline", "variant": "default"},
            {"label": "Send parent update", "type": "outline", "variant": "default"},
            {"label": "Schedule mock", "type": "outline", "variant": "default"},
            {"label": "Monthly report", "type": "primary", "variant": "teal"}
        ]
    }

# --- SCREEN 35: Trainer Message Hub (PDF 12) ---
class TrainerReplyRequest(BaseModel):
    thread_id: str
    text: str
    auto_translate_to_tamil: bool = True

class BroadcastRequest(BaseModel):
    target_audience: str # batches, parents, both
    title: str
    message: str

@router.get("/messages")
def get_trainer_messages(category: Optional[str] = "All", db: Session = Depends(get_db)):
    threads_query = select(TrainerDirectThread)
    if category and category != "All":
        threads_query = threads_query.filter_by(contact_category=category)
    threads = db.execute(threads_query).scalars().all()
    
    selected_thread = next((t for t in threads if t.id == "th_ramesh"), threads[0] if threads else None)
    messages = []
    if selected_thread:
        messages = db.execute(select(DirectMessage).filter_by(thread_id=selected_thread.id)).scalars().all()
        
    return {
        "threads": [
            {
                "id": t.id,
                "name": t.contact_name,
                "category": t.contact_category,
                "role_chip": t.contact_role_chip,
                "avatar": t.avatar_initials,
                "language_pref": t.pref_language,
                "unread_badge": t.unread_badge,
                "last_message": t.last_message_preview,
                "time": t.last_message_time,
                "is_selected": t.id == (selected_thread.id if selected_thread else "")
            }
            for t in threads
        ],
        "selected_contact": {
            "name": selected_thread.contact_name if selected_thread else "Mr. Ramesh K",
            "subtitle": "Parent of Priya R · Sem 5 AI & DS · Prefers Tamil",
            "has_progress_card": True,
            "auto_translate_available": True
        },
        "messages": [
            {
                "id": m.id,
                "is_incoming": m.is_incoming,
                "sender_name": m.sender_name,
                "text_en": m.text_en,
                "text_ta": m.text_ta,
                "time": m.timestamp_str
            }
            for m in messages
        ],
        "permission_matrix": [
            {"label": "Student ⇄ Student 1-1", "status": "Off", "color": "red"},
            {"label": "Student groups", "status": "Moderated", "color": "green"},
            {"label": "Trainer ⇄ Parent 1-1", "status": "Allowed", "color": "green"},
            {"label": "Trainer ⇄ College 1-1", "status": "Allowed", "color": "green"},
            {"label": "Announcements", "status": "Broadcast", "color": "blue"}
        ],
        "moderation_queue": [
            {"id": "mod_01", "author": "Anonymous in CSE Group", "snippet": "External test answers leak link", "time": "15 min ago"},
            {"id": "mod_02", "author": "Student in Track Doubts", "snippet": "Inappropriate comment flag", "time": "1 hr ago"}
        ]
    }

@router.post("/messages/reply")
def reply_direct_message(req: TrainerReplyRequest, db: Session = Depends(get_db)):
    msg = DirectMessage(
        id=f"dm_{int(datetime.datetime.utcnow().timestamp())}",
        college_id="col_demo_001",
        thread_id=req.thread_id,
        is_incoming=False,
        sender_name="Arun Kumar (Trainer)",
        text_en=req.text,
        text_ta=f"[தமிழ் மொழிபெயர்ப்பு] {req.text}" if req.auto_translate_to_tamil else None,
        timestamp_str=datetime.datetime.now().strftime("%I:%M %p")
    )
    db.add(msg)
    db.commit()
    return {"success": True, "message_id": msg.id}

@router.post("/messages/broadcast")
def send_broadcast_announcement(req: BroadcastRequest):
    return {
        "success": True,
        "message": f"Broadcast sent to {req.target_audience} successfully."
    }

@router.post("/messages/moderation/{item_id}/{action}")
def handle_moderation(item_id: str, action: str):
    # action: keep or remove
    return {"success": True, "action": action, "item_id": item_id}

