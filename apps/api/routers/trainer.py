from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
import datetime

from core.database import get_db
from core.security import get_current_user, require_role, TokenPayload
from models.schema import (
    TrainerDirectThread, DirectMessage, CodingProblem, CodingSubmission,
    PullRequest, PullRequestFile, PullRequestComment, SprintTask, StudentProject
)

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

@router.get("/coding-problems")
def list_trainer_coding_problems(
    current_user: TokenPayload = Depends(require_role(["trainer", "college_admin"])),
    db: Session = Depends(get_db)
):
    problems = db.execute(
        select(CodingProblem).filter_by(college_id=current_user.college_id).order_by(CodingProblem.created_at.asc())
    ).scalars().all()
    
    result = []
    for p in problems:
        total_subs = db.execute(
            select(CodingSubmission).filter_by(problem_id=p.id, college_id=current_user.college_id)
        ).scalars().all()
        accepted = len([s for s in total_subs if s.status == "Accepted"])
        result.append({
            "id": p.id,
            "title": p.title,
            "difficulty": p.difficulty,
            "topic": p.topic,
            "company_tags": p.company_tags,
            "week_info": p.week_info,
            "trainer_author": p.trainer_author or "Arun K.",
            "total_submissions": len(total_subs),
            "accepted_submissions": accepted,
            "solved_percentage": round((accepted / max(1, len(total_subs))) * 100) if total_subs else 0
        })
    return {"problems": result, "total": len(result)}

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

# --- SCREEN 31: Trainer Code Reviews ---
class ReviewActionRequest(BaseModel):
    action: str  # "approve" | "request_changes"
    review_feedback: str
    code_quality_score: Optional[int] = 5
    test_coverage_score: Optional[int] = 5
    modularity_score: Optional[int] = 4
    score_percent: Optional[int] = 92

class InlineCommentRequest(BaseModel):
    file_id: Optional[str] = None
    line_number: Optional[int] = None
    comment_text: str

@router.get("/reviews")
def list_code_reviews(
    status: Optional[str] = "all",
    team: Optional[str] = None,
    search: Optional[str] = None,
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    college_id = current_user.college_id if isinstance(current_user, TokenPayload) else "col_demo_001"
    
    query = select(PullRequest).filter_by(college_id=college_id)
    all_prs = db.execute(query).scalars().all()

    # Calculate status counts across all PRs for this tenant
    total_count = len(all_prs)
    pending_count = sum(1 for p in all_prs if p.status == "pending")
    approved_count = sum(1 for p in all_prs if p.status == "approved")
    changes_requested_count = sum(1 for p in all_prs if p.status == "changes_requested")

    # Filter
    filtered = all_prs
    if status and status != "all":
        filtered = [p for p in filtered if p.status == status]
    if team:
        filtered = [p for p in filtered if team.lower() in p.team_name.lower()]
    if search:
        s_lower = search.lower()
        filtered = [
            p for p in filtered
            if s_lower in p.title.lower() or s_lower in p.author_name.lower() or s_lower in p.pr_number.lower()
        ]

    prs_list = [
        {
            "id": p.id,
            "pr_number": p.pr_number,
            "title": p.title,
            "project_id": p.project_id,
            "project_name": p.project_name,
            "team_name": p.team_name,
            "task_id": p.task_id,
            "author_id": p.author_id,
            "author_name": p.author_name,
            "author_initials": p.author_initials,
            "source_branch": p.source_branch,
            "target_branch": p.target_branch,
            "status": p.status,
            "story_points": p.story_points,
            "automated_checks_passed": p.automated_checks_passed,
            "automated_checks_summary": p.automated_checks_summary,
            "diff_summary": p.diff_summary,
            "review_feedback": p.review_feedback,
            "code_quality_score": p.code_quality_score,
            "test_coverage_score": p.test_coverage_score,
            "modularity_score": p.modularity_score,
            "reviewed_by": p.reviewed_by,
            "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
            "created_at": p.created_at.strftime("%b %d · %I:%M %p") if p.created_at else "Today"
        }
        for p in filtered
    ]

    return {
        "prs": prs_list,
        "counts": {
            "total": total_count,
            "pending": pending_count,
            "approved": approved_count,
            "changes_requested": changes_requested_count
        }
    }

@router.get("/reviews/{pr_id}")
def get_code_review_detail(
    pr_id: str,
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    college_id = current_user.college_id if isinstance(current_user, TokenPayload) else "col_demo_001"

    pr = db.execute(
        select(PullRequest).filter_by(id=pr_id, college_id=college_id)
    ).scalar_one_or_none()

    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found for this tenant")

    files = db.execute(
        select(PullRequestFile).filter_by(pr_id=pr.id, college_id=college_id)
    ).scalars().all()

    comments = db.execute(
        select(PullRequestComment).filter_by(pr_id=pr.id, college_id=college_id).order_by(PullRequestComment.created_at.asc())
    ).scalars().all()

    files_list = [
        {
            "id": f.id,
            "filename": f.filename,
            "change_type": f.change_type,
            "additions": f.additions,
            "deletions": f.deletions,
            "diff_content": f.diff_content
        }
        for f in files
    ]

    comments_list = [
        {
            "id": c.id,
            "file_id": c.file_id,
            "line_number": c.line_number,
            "author_name": c.author_name,
            "author_role": c.author_role,
            "comment_text": c.comment_text,
            "created_at": c.created_at.strftime("%b %d, %I:%M %p") if c.created_at else "Just now"
        }
        for c in comments
    ]

    # Task info if associated with sprint board
    task_info = None
    if pr.task_id:
        task = db.execute(select(SprintTask).filter_by(id=pr.task_id, college_id=college_id)).scalar_one_or_none()
        if task:
            task_info = {
                "id": task.id,
                "title": task.title,
                "column_name": task.column_name,
                "story_points": task.story_points,
                "assignee_name": task.assignee_name
            }

    return {
        "pr": {
            "id": pr.id,
            "pr_number": pr.pr_number,
            "title": pr.title,
            "project_id": pr.project_id,
            "project_name": pr.project_name,
            "team_name": pr.team_name,
            "task_id": pr.task_id,
            "author_id": pr.author_id,
            "author_name": pr.author_name,
            "author_initials": pr.author_initials,
            "source_branch": pr.source_branch,
            "target_branch": pr.target_branch,
            "status": pr.status,
            "story_points": pr.story_points,
            "automated_checks_passed": pr.automated_checks_passed,
            "automated_checks_summary": pr.automated_checks_summary,
            "diff_summary": pr.diff_summary,
            "review_feedback": pr.review_feedback,
            "code_quality_score": pr.code_quality_score or 5,
            "test_coverage_score": pr.test_coverage_score or 5,
            "modularity_score": pr.modularity_score or 4,
            "reviewed_by": pr.reviewed_by,
            "reviewed_at": pr.reviewed_at.isoformat() if pr.reviewed_at else None,
            "created_at": pr.created_at.strftime("%b %d · %I:%M %p") if pr.created_at else "Today"
        },
        "task": task_info,
        "files": files_list,
        "comments": comments_list,
        "automated_checks": {
            "all_passed": pr.automated_checks_passed,
            "tests_run": 14,
            "tests_passed": 14 if pr.automated_checks_passed else 13,
            "tests_failed": 0 if pr.automated_checks_passed else 1,
            "cyclomatic_complexity": "3.2 (Low)",
            "lint_errors": 0,
            "security_alerts": 0,
            "maintainability_rating": "A (96/100)"
        }
    }

@router.post("/reviews/{pr_id}/action")
def submit_review_action(
    pr_id: str,
    req: ReviewActionRequest,
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    college_id = current_user.college_id if isinstance(current_user, TokenPayload) else "col_demo_001"
    trainer_name = current_user.name if isinstance(current_user, TokenPayload) and current_user.name else "Arun Kumar"

    pr = db.execute(
        select(PullRequest).filter_by(id=pr_id, college_id=college_id)
    ).scalar_one_or_none()

    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found for this tenant")

    now = datetime.datetime.utcnow()

    if req.action == "approve":
        pr.status = "approved"
        pr.review_feedback = req.review_feedback
        pr.code_quality_score = req.code_quality_score
        pr.test_coverage_score = req.test_coverage_score
        pr.modularity_score = req.modularity_score
        pr.reviewed_by = trainer_name
        pr.reviewed_at = now

        # Auto-advance task on Sprint Board from 'code_review' to 'done'
        if pr.task_id:
            task = db.execute(
                select(SprintTask).filter_by(id=pr.task_id, college_id=college_id)
            ).scalar_one_or_none()
            if task:
                task.column_name = "done"

        # Auto-verify student project in Portfolio
        if pr.project_id:
            project = db.execute(
                select(StudentProject).filter_by(id=pr.project_id, college_id=college_id)
            ).scalar_one_or_none()
            if project:
                project.trainer_verified = True
                project.trainer_name = trainer_name
                project.trainer_feedback = req.review_feedback
                if req.score_percent:
                    project.score_percent = req.score_percent

        db.commit()
        return {
            "success": True,
            "message": "Pull Request approved! Sprint task moved to 'Done' and Student Portfolio verified.",
            "status": "approved",
            "pr_id": pr.id
        }

    elif req.action == "request_changes":
        pr.status = "changes_requested"
        pr.review_feedback = req.review_feedback
        pr.code_quality_score = req.code_quality_score
        pr.test_coverage_score = req.test_coverage_score
        pr.modularity_score = req.modularity_score
        pr.reviewed_by = trainer_name
        pr.reviewed_at = now

        # Move task back to 'in_progress' for adjustments
        if pr.task_id:
            task = db.execute(
                select(SprintTask).filter_by(id=pr.task_id, college_id=college_id)
            ).scalar_one_or_none()
            if task:
                task.column_name = "in_progress"

        db.commit()
        return {
            "success": True,
            "message": "Changes requested. Team notified and task moved to In Progress.",
            "status": "changes_requested",
            "pr_id": pr.id
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid review action. Must be 'approve' or 'request_changes'.")

@router.post("/reviews/{pr_id}/comments")
def add_inline_review_comment(
    pr_id: str,
    req: InlineCommentRequest,
    current_user: Optional[TokenPayload] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import uuid
    college_id = current_user.college_id if isinstance(current_user, TokenPayload) else "col_demo_001"
    author_name = current_user.name if isinstance(current_user, TokenPayload) and current_user.name else "Arun Kumar"
    author_role = current_user.role.capitalize() if isinstance(current_user, TokenPayload) else "Trainer"

    pr = db.execute(
        select(PullRequest).filter_by(id=pr_id, college_id=college_id)
    ).scalar_one_or_none()

    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found for this tenant")

    comment_id = f"prc_{uuid.uuid4().hex[:10]}"
    new_comment = PullRequestComment(
        id=comment_id,
        college_id=college_id,
        pr_id=pr.id,
        file_id=req.file_id,
        line_number=req.line_number,
        author_name=author_name,
        author_role=author_role,
        comment_text=req.comment_text,
        created_at=datetime.datetime.utcnow()
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return {
        "success": True,
        "comment": {
            "id": new_comment.id,
            "pr_id": new_comment.pr_id,
            "file_id": new_comment.file_id,
            "line_number": new_comment.line_number,
            "author_name": new_comment.author_name,
            "author_role": new_comment.author_role,
            "comment_text": new_comment.comment_text,
            "created_at": "Just now"
        }
    }


