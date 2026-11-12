from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import datetime

from apps.api.core.database import get_db
from apps.api.core.security import get_current_user, TokenPayload
from apps.api.models.schema import (
    Student, CodingProblem, CodingSubmission, PracticeTest,
    PracticeQuestion, VirtualLabItem, SprintTask, MockInterview,
    SessionItem, DiscussionGroup, GroupMessage
)

router = APIRouter(prefix="/student", tags=["Student Screens"])

# --- SCREEN 12: Student Dashboard (PDF 2) ---
@router.get("/dashboard")
def get_student_dashboard(
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    student = db.execute(select(Student).filter_by(college_id=current_user.college_id)).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
        
    return {
        "student": {
            "name": current_user.name or "Priya R",
            "greeting": "Good morning, Priya 👋",
            "semester": student.semester,
            "branch": student.branch,
            "batch": student.batch_name,
            "readiness_score": student.readiness_score,
            "readiness_band": student.readiness_band,
            "readiness_delta": student.readiness_delta,
            "problems_solved": student.problems_solved,
            "problems_delta": 34,
            "attendance_pct": student.attendance_pct,
            "attendance_target": 85,
            "streak_days": student.streak_days,
            "streak_best": 27
        },
        "skill_progress": [
            {"skill": "DSA patterns", "percentage": 78, "color": "teal"},
            {"skill": "Aptitude & reasoning", "percentage": 71, "color": "blue"},
            {"skill": "Cloud & DevOps", "percentage": 64, "color": "purple"},
            {"skill": "AI & Data Science track", "percentage": 82, "color": "teal"},
            {"skill": "Future Skills: AI engineering", "percentage": 58, "color": "orange"},
            {"skill": "Communication", "percentage": 69, "color": "blue"}
        ],
        "this_week": [
            {"day": "Mon", "topic": "DSA: Pattern drill – Union-Find", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Tue", "topic": "Track: Model evaluation lab", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Wed", "topic": "Aptitude: Data interpretation", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Thu", "topic": "Future Skills: LLM APIs & RAG", "duration": "1 hr", "type": "Live", "color": "teal"},
            {"day": "Fri", "topic": "GD + weekly quiz", "duration": "1 hr", "type": "Live", "color": "blue"},
            {"day": "Sat", "topic": "Track project kick-off + RAG mini-lab", "duration": "3 hrs", "type": "In-lab / Hybrid", "color": "purple"}
        ],
        "current_project": {
            "title": "Crop Price Predictor",
            "subtitle": "End-to-end ML · Team of 3 · Due Week 12",
            "progress_pct": 45,
            "open_tasks": 3
        },
        "upcoming_events": [
            {"title": "Mid-term DSA test", "date": "Sat"},
            {"title": "Mock interview", "date": "Wed 4:00 PM"},
            {"title": "AWS Cloud Practitioner", "date": "Nov 22"}
        ],
        "badges": [
            {"name": "Cloud Deployer", "description": "Deployed first app on cloud", "icon": "cloud", "earned_date": "Recently"},
            {"name": "DSA Master", "description": "100+ patterns solved", "icon": "code", "earned_date": "Oct 2"},
            {"name": "Consistent 15", "description": "15-day study streak", "icon": "flame", "earned_date": "Sep 28"},
            {"name": "Team Lead", "description": "Sprint 1 shipped", "icon": "users", "earned_date": "Sep 20"}
        ]
    }

# --- SCREEN 24: Coding Lab (PDF 3) ---
class CodeRunRequest(BaseModel):
    code: str
    language: str = "python"

class CodeSubmitRequest(BaseModel):
    code: str
    language: str = "python"

@router.get("/coding/{problem_id}")
def get_coding_problem(problem_id: str, db: Session = Depends(get_db)):
    prob = db.execute(select(CodingProblem).filter_by(id=problem_id)).scalar_one_or_none()
    if not prob:
        # Default to connected components problem
        prob = db.execute(select(CodingProblem)).first()[0]
        
    return {
        "id": prob.id,
        "title": prob.title,
        "difficulty": prob.difficulty,
        "topic": prob.topic,
        "company_tags": prob.company_tags,
        "week_info": prob.week_info,
        "statement": prob.statement,
        "example_input": prob.example_input,
        "example_output": prob.example_output,
        "constraints": prob.constraints,
        "starter_code": prob.starter_code,
        "trainer_notes": prob.trainer_notes,
        "trainer_author": prob.trainer_author,
        "ai_reviewer": {
            "tag": "Future Skills",
            "hints": [
                {"type": "good", "text": "Good: path compression keeps find() fast.", "color": "blue"},
                {"type": "try_next", "text": "Try next: add union by rank. Can you explain why it helps worst-case time?", "color": "amber"},
                {"type": "interview_tip", "text": "Interview tip: state the complexity aloud: near O(E · α(n)).", "color": "blue"}
            ],
            "hints_used": 1,
            "rules_note": "Hints only, no full solutions. AI help used in this problem: 1 hint"
        }
    }

@router.post("/coding/{problem_id}/run")
def run_code_sample(problem_id: str, req: CodeRunRequest):
    # Safe sandboxed simulation (adapter for Judge0)
    return {
        "status": "Passed",
        "runtime_ms": 42,
        "memory_mb": 16.1,
        "cases": [
            {"name": "Sample case 1", "status": "Passed", "time_ms": 12},
            {"name": "Sample case 2", "status": "Passed", "time_ms": 14}
        ]
    }

@router.post("/coding/{problem_id}/submit")
def submit_code(problem_id: str, req: CodeSubmitRequest, db: Session = Depends(get_db)):
    return {
        "status": "Accepted",
        "runtime_ms": 42,
        "memory_mb": 16.1,
        "tests_passed": 18,
        "tests_total": 18,
        "cases": [
            {"name": "Sample case 1", "status": "Passed"},
            {"name": "Sample case 2", "status": "Passed"},
            {"name": "Edge: no edges", "status": "Passed"},
            {"name": "Large graph (n=2000)", "status": "Passed"}
        ],
        "message": "18 / 18 hidden tests passed"
    }

# --- SCREEN 23: Practice Tests (PDF 4) ---
class AnswerSubmitRequest(BaseModel):
    answers: dict # { "12": "B", ... }

@router.get("/tests/{test_id}")
def get_practice_test(test_id: str, db: Session = Depends(get_db)):
    test = db.execute(select(PracticeTest).filter_by(id=test_id)).scalar_one_or_none()
    if not test:
        test = db.execute(select(PracticeTest)).first()[0]
        
    questions = db.execute(select(PracticeQuestion).filter_by(test_id=test.id).order_by(PracticeQuestion.question_number)).scalars().all()
    
    return {
        "id": test.id,
        "title": test.title,
        "category": test.category,
        "duration_min": test.duration_min,
        "time_remaining_sec": 1122, # 18:42
        "total_questions": test.total_questions,
        "sections": [
            {"name": "Quantitative", "answered": 12, "total": 15},
            {"name": "Logical reasoning", "answered": 0, "total": 10},
            {"name": "Verbal ability", "answered": 0, "total": 5}
        ],
        "questions": [
            {
                "id": q.id,
                "number": q.question_number,
                "section": q.section_name,
                "topic": q.topic,
                "text": q.question_text,
                "options": {
                    "A": q.option_a,
                    "B": q.option_b,
                    "C": q.option_c,
                    "D": q.option_d
                },
                "selected_option": "B" if q.question_number == 12 else ("A" if q.question_number < 12 else None),
                "is_marked_for_review": q.question_number in [7, 14]
            }
            for q in questions
        ]
    }

@router.post("/tests/{test_id}/submit")
def submit_practice_test(test_id: str, req: AnswerSubmitRequest):
    return {
        "success": True,
        "score": 26,
        "total": 30,
        "accuracy": "86.7%",
        "time_taken": "24 mins",
        "section_analysis": [
            {"section": "Quantitative", "score": "14/15", "status": "Strong"},
            {"section": "Logical reasoning", "score": "8/10", "status": "Good"},
            {"section": "Verbal ability", "score": "4/5", "status": "Good"}
        ]
    }

# --- SCREEN 29: Virtual Labs (PDF 5) ---
@router.get("/labs")
def get_virtual_labs(db: Session = Depends(get_db)):
    labs = db.execute(select(VirtualLabItem)).scalars().all()
    active_lab = next((lab for lab in labs if lab.is_active_session), None)
    
    return {
        "labs": [
            {
                "id": l.id,
                "name": l.name,
                "category": l.category,
                "description": l.description,
                "eligibility_chip": l.eligibility_chip,
                "status_chip": l.status_chip,
                "tag_color": l.tag_color,
                "footer_text": l.footer_text,
                "requires_approval": l.requires_approval
            }
            for l in labs
        ],
        "active_session": {
            "lab_name": active_lab.name if active_lab else "AI Notebook Lab",
            "active_filename": active_lab.active_filename if active_lab else "rag_notes_demo.ipynb",
            "running_minutes": active_lab.active_minutes if active_lab else 38,
            "session_id": "session_rag_demo_01"
        } if active_lab else None
    }

@router.post("/labs/{lab_id}/launch")
def launch_lab(lab_id: str, db: Session = Depends(get_db)):
    db.execute(update(VirtualLabItem).where(VirtualLabItem.id == lab_id).values(
        is_active_session=True,
        active_filename="workspace_session.ipynb",
        active_minutes=1
    ))
    db.commit()
    return {"status": "started", "session_url": f"/live/lab_{lab_id}"}

@router.post("/labs/{lab_id}/stop")
def stop_lab(lab_id: str, db: Session = Depends(get_db)):
    db.execute(update(VirtualLabItem).where(VirtualLabItem.id == lab_id).values(is_active_session=False))
    db.commit()
    return {"status": "stopped"}

# --- SCREEN 30: Sprint Board (PDF 6) ---
class TaskMoveRequest(BaseModel):
    task_id: str
    target_column: str

class StandupRequest(BaseModel):
    yesterday: str
    today: str
    blockers: Optional[str] = None

@router.get("/projects/board")
def get_sprint_board(db: Session = Depends(get_db)):
    tasks = db.execute(select(SprintTask)).scalars().all()
    
    columns = {"todo": [], "in_progress": [], "code_review": [], "done": []}
    for t in tasks:
        col = t.column_name if t.column_name in columns else "todo"
        columns[col].append({
            "id": t.id,
            "title": t.title,
            "tag": t.tag,
            "tag_type": t.tag_type,
            "assignee_initials": t.assignee_initials,
            "assignee_name": t.assignee_name,
            "story_points": t.story_points,
            "pr_number": t.pr_number
        })
        
    return {
        "team_name": "Team Phoenix",
        "sprint_info": "Sprint 2 of 3",
        "project_title": "Clinic Appointment System",
        "client": "Trainer (Arun K.)",
        "deadline": "Ends Week 8",
        "change_request": "SMS reminder for appointments (CR-04)",
        "progress_pct": 58,
        "story_points": {"completed": 21, "total": 36, "velocity_last": 30},
        "build_status": {"state": "Passing", "deployed_time": "Deployed to staging 2 hrs ago"},
        "columns": columns
    }

@router.post("/projects/tasks/move")
def move_sprint_task(req: TaskMoveRequest, db: Session = Depends(get_db)):
    db.execute(update(SprintTask).where(SprintTask.id == req.task_id).values(column_name=req.target_column))
    db.commit()
    return {"success": True, "task_id": req.task_id, "column": req.target_column}

@router.post("/projects/standup")
def submit_standup(req: StandupRequest):
    return {"success": True, "message": "Daily standup shared with Team Phoenix & Trainer Arun K."}

# --- SCREEN 36: Mock Interviews (PDF 7) ---
class SlotBookRequest(BaseModel):
    slot_id: str

@router.get("/interviews")
def get_mock_interviews(db: Session = Depends(get_db)):
    interview = db.execute(select(MockInterview)).first()
    int_data = interview[0] if interview else None
    
    return {
        "latest_interview": {
            "title": int_data.round_title if int_data else "Mock Interview #2 – Technical",
            "date_info": int_data.interview_date if int_data else "Oct 8 · 40 min",
            "interviewer": int_data.interviewer_name if int_data else "Arun K.",
            "overall_score": int_data.overall_score if int_data else 3.8,
            "service_chip": int_data.service_chip if int_data else "Hire-ready for service roles",
            "product_chip": int_data.product_chip if int_data else "Improve for product roles",
            "rubrics": [
                {"category": "Problem solving", "score": int_data.problem_solving if int_data else 4, "max": 5},
                {"category": "Coding & correctness", "score": int_data.coding_correctness if int_data else 4, "max": 5},
                {"category": "Thinking aloud", "score": int_data.thinking_aloud if int_data else 3, "max": 5},
                {"category": "Core CS knowledge", "score": int_data.core_cs if int_data else 4, "max": 5},
                {"category": "Project explanation", "score": int_data.project_explanation if int_data else 4, "max": 5},
                {"category": "Communication & confidence", "score": int_data.communication if int_data else 3, "max": 5}
            ],
            "trainer_feedback": int_data.feedback_text if int_data else "Strong grasp of graph traversals and Union-Find.",
            "recording_url": int_data.recording_url if int_data else "/videos/mock_02.mp4"
        },
        "progress_trend": [
            {"round": "#1", "score": 3.0, "label": "#1 · 3.0"},
            {"round": "#2", "score": 3.8, "label": "#2 · 3.8"},
            {"target": 4.2, "label": "Target 4.2"}
        ],
        "available_slots": [
            {"id": "slot_01", "time": "Wed, Oct 15 · 4:00 PM", "type": "Technical", "tag_color": "blue"},
            {"id": "slot_02", "time": "Sat, Oct 18 · 10:30 AM", "type": "HR round", "tag_color": "green"},
            {"id": "slot_03", "time": "Sat, Oct 18 · 12:00 PM", "type": "AI-allowed coding", "tag_color": "purple"}
        ]
    }

@router.post("/interviews/book")
def book_interview_slot(req: SlotBookRequest):
    return {"success": True, "message": "Slot booked successfully! Confirmation sent to trainer."}

# --- SCREEN 08: Live Sessions & Recordings (PDF 14) ---
@router.get("/live")
def get_student_live_sessions(db: Session = Depends(get_db)):
    sessions = db.execute(select(SessionItem).order_by(SessionItem.scheduled_start)).scalars().all()
    
    return {
        "hero_session": {
            "badge": "Starting in 4 min",
            "title": "Future Skills: LLM APIs & RAG",
            "time_info": "Thu, Oct 9 · 11:00 AM to 12:00 PM · Arun K. · Lab: AI Notebook pre-loaded",
            "device_check": "Mic & camera check passed",
            "session_id": "sess_thu_rag"
        },
        "week_sessions": [
            {
                "id": s.id,
                "when": s.scheduled_start.strftime("%a %I:%M–") + s.scheduled_end.strftime("%I:%M"),
                "title": s.title,
                "type": s.session_type,
                "status": s.status,
                "recording_url": s.recording_url
            }
            for s in sessions
        ],
        "attendance_summary": {
            "semester": "Semester 5",
            "overall_pct": 92,
            "sessions_attended": "53 of 58 sessions",
            "weekday_pct": 93,
            "saturday_pct": 89,
            "recordings_watched": "4 of 5 for missed"
        },
        "recording_library": [
            {"title": "Cloud deploy walkthrough", "duration": "58 min"},
            {"title": "Docker Compose lab", "duration": "2 hr 51 min"},
            {"title": "Mock interview tips", "duration": "42 min"}
        ]
    }

# --- SCREEN 34: Discussion Groups (PDF 11) ---
class GroupMessageRequest(BaseModel):
    message_text: str
    code_snippet: Optional[str] = None

@router.get("/discussions")
def get_discussions(db: Session = Depends(get_db)):
    groups = db.execute(select(DiscussionGroup)).scalars().all()
    selected_group = next((g for g in groups if g.id == "grp_doubts"), groups[0] if groups else None)
    
    messages = []
    if selected_group:
        messages = db.execute(select(GroupMessage).filter_by(group_id=selected_group.id)).scalars().all()
        
    return {
        "safe_space_banner": "Safe learning space: students chat in moderated groups only. One-to-one messaging between students is turned off. All groups are moderated by trainers.",
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "badge": g.unread_badge,
                "is_locked": g.is_locked_announcement,
                "members_count": g.members_count,
                "online_count": g.online_count,
                "moderators": g.moderators,
                "pinned_note": g.pinned_note
            }
            for g in groups
        ],
        "active_group_id": selected_group.id if selected_group else "",
        "active_group_info": {
            "name": selected_group.name if selected_group else "",
            "members": 42,
            "trainers": 2,
            "doubts_answered": 128,
            "avg_reply_time": "35 min"
        },
        "top_helpers": [
            {"name": "Vikram R", "answers": 24, "medal": "gold"},
            {"name": "Ananya P", "answers": 19, "medal": "silver"},
            {"name": "Sneha N", "answers": 15, "medal": "bronze"}
        ],
        "messages": [
            {
                "id": m.id,
                "sender_name": m.sender_name,
                "sender_role": m.sender_role,
                "sender_initials": m.sender_initials,
                "message_text": m.message_text,
                "code_snippet": m.code_snippet,
                "is_marked_as_answer": m.is_marked_as_answer,
                "reactions_count": m.reactions_count,
                "timestamp": m.timestamp_str
            }
            for m in messages
        ]
    }

@router.post("/discussions/{group_id}/messages")
def send_group_message(
    group_id: str,
    req: GroupMessageRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msg = GroupMessage(
        id=f"msg_{int(datetime.datetime.utcnow().timestamp())}",
        college_id=current_user.college_id,
        group_id=group_id,
        sender_name=current_user.name or "Priya R",
        sender_role=current_user.role.capitalize(),
        sender_initials=current_user.avatar or "PR",
        message_text=req.message_text,
        code_snippet=req.code_snippet,
        timestamp_str=datetime.datetime.now().strftime("%I:%M %p")
    )
    db.add(msg)
    db.commit()
    return {"success": True, "message_id": msg.id}

