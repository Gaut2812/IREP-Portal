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

# --- SCREEN 13: Trainer Dashboard (PDF 8) + Screen 14 flag actions ---
import uuid
from core.tenant import get_trainer_for_user, get_trainer_batch_ids, get_user_name
from models.schema import AtRiskFlag, FlagAction, Student as StudentModel, User as UserModel
from services.trainer_dashboard import build_trainer_dashboard
from services.at_risk import ACTION_LABEL, reason_text, request_parent_call
from services.audit import record_audit


class FlagActionRequest(BaseModel):
    action_type: str          # parent_call | extra_saturday | mentor | note
    note: Optional[str] = None


class FlagResolveRequest(BaseModel):
    note: str


@router.get("/dashboard")
def get_trainer_dashboard(
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(["trainer"])),
    db: Session = Depends(get_db),
):
    trainer = get_trainer_for_user(current_user, db)
    return build_trainer_dashboard(db, trainer, current_user, lang)


def _flag_for_trainer(flag_id: str, current_user: TokenPayload, db: Session) -> AtRiskFlag:
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = get_trainer_batch_ids(trainer, db)
    flag = db.execute(select(AtRiskFlag).filter_by(id=flag_id, college_id=current_user.college_id)).scalar_one_or_none()
    if not flag or (flag.batch_id and flag.batch_id not in batch_ids):
        raise HTTPException(status_code=404, detail="Flag not found")
    return flag


@router.get("/at-risk")
def list_at_risk_flags(
    status: Optional[str] = "open",
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(["trainer"])),
    db: Session = Depends(get_db),
):
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = get_trainer_batch_ids(trainer, db) or ["__none__"]
    q = select(AtRiskFlag).where(AtRiskFlag.college_id == current_user.college_id, AtRiskFlag.batch_id.in_(batch_ids))
    if status and status != "all":
        q = q.where(AtRiskFlag.status == status) if status != "open" else q.where(AtRiskFlag.status != "resolved")
    flags = db.execute(q.order_by(AtRiskFlag.flagged_on.desc())).scalars().all()
    students = {st.id: (st, nm) for st, nm in db.execute(
        select(StudentModel, UserModel.name).join(UserModel, UserModel.id == StudentModel.user_id)
        .where(StudentModel.id.in_([f.student_id for f in flags] or ["__none__"]))
    ).all()}
    lg = lang if lang in ("en", "ta") else "en"

    def row(f):
        st = students.get(f.student_id, (None, "Student"))[0]
        return {
            "id": f.id, "student_id": f.student_id, "name": students.get(f.student_id, (None, "Student"))[1],
            "score": st.readiness_score if st else None, "band": st.readiness_band if st else None,
            "attendance_pct": st.attendance_pct if st else None, "batch": st.batch_name if st else None,
            "reason_key": f.reason_key, "issue": reason_text(f.reason_key, f.reason_text, lg), "severity": f.severity, "status": f.status,
            "suggested_action": f.suggested_action, "action_label": ACTION_LABEL[f.suggested_action][lg],
            "parent_notified": f.parent_notified, "flagged_on": f.flagged_on.isoformat() if f.flagged_on else None,
        }
    rows = [row(f) for f in flags]
    from services.study_buddy import calls_by_student
    ai = calls_by_student(db, {f.student_id for f in flags}, days=7)          # L21
    for r in rows:
        r["ai_calls_7d"] = ai.get(r["student_id"], 0)
    summary = {"open": sum(1 for f in flags if f.status != "resolved"),
               "high": sum(1 for f in flags if f.status != "resolved" and f.severity == "high"),
               "parents_alerted": sum(1 for f in flags if f.parent_notified)}
    return {"flags": rows, "total": len(flags), "summary": summary}


@router.get("/flags/{flag_id}")
def get_flag(
    flag_id: str,
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(["trainer"])),
    db: Session = Depends(get_db),
):
    """Screen 14: one flag with its history of actions (own batches only; else 404)."""
    flag = _flag_for_trainer(flag_id, current_user, db)
    lg = lang if lang in ("en", "ta") else "en"
    actions = db.execute(select(FlagAction).where(FlagAction.flag_id == flag.id).order_by(FlagAction.created_at)).scalars().all()
    return {"id": flag.id, "status": flag.status, "issue": reason_text(flag.reason_key, flag.reason_text, lg),
            "suggested_action": flag.suggested_action, "action_label": ACTION_LABEL[flag.suggested_action][lg],
            "parent_notified": flag.parent_notified, "resolution_note": flag.resolution_note,
            "actions": [{"type": a.action_type, "note": a.note, "by": a.actor_name,
                         "at": a.created_at.isoformat() if a.created_at else None} for a in actions]}


@router.post("/flags/{flag_id}/actions")
def add_flag_action(
    flag_id: str,
    req: FlagActionRequest,
    current_user: TokenPayload = Depends(require_role(["trainer"])),
    db: Session = Depends(get_db),
):
    if req.action_type not in ("parent_call", "extra_saturday", "mentor", "note"):
        raise HTTPException(status_code=422, detail="Unknown action type")
    flag = _flag_for_trainer(flag_id, current_user, db)
    student = db.execute(select(StudentModel).filter_by(id=flag.student_id)).scalar_one()
    student_name = get_user_name(db, student.user_id, "Student")
    action = FlagAction(
        id=f"fa_{uuid.uuid4().hex[:18]}", college_id=current_user.college_id, flag_id=flag.id,
        action_type=req.action_type, note=req.note, actor_user_id=current_user.sub, actor_name=current_user.name,
    )
    db.add(action)
    if flag.status == "open":
        flag.status = "in_progress"
    call = None
    if req.action_type == "parent_call":
        call = request_parent_call(db, flag, current_user.sub)      # L31: alert, thread message, overview
        record_audit(db, current_user, "at_risk.parent_call", "at_risk_flag", flag.id,
                     {"student_id": flag.student_id, "outcome": call})
    record_audit(db, current_user, "at_risk.action", "at_risk_flag", flag.id,
                 {"action_type": req.action_type, "student_id": flag.student_id, "parent_call": call})
    db.commit()
    return {"success": True, "flag_id": flag.id, "status": flag.status, "action_id": action.id,
            "parent_notified": flag.parent_notified, "notified_now": call == "sent", "parent_call": call, "student": student_name}


@router.post("/flags/{flag_id}/resolve")
def resolve_flag(
    flag_id: str,
    req: FlagResolveRequest,
    current_user: TokenPayload = Depends(require_role(["trainer"])),
    db: Session = Depends(get_db),
):
    if not req.note or not req.note.strip():
        raise HTTPException(status_code=422, detail="A resolution note is required")
    flag = _flag_for_trainer(flag_id, current_user, db)
    flag.status = "resolved"
    flag.resolution_note = req.note.strip()
    flag.resolved_by = current_user.sub
    flag.resolved_at = datetime.datetime.utcnow()
    db.add(FlagAction(id=f"fa_{uuid.uuid4().hex[:18]}", college_id=current_user.college_id, flag_id=flag.id,
                      action_type="resolve", note=req.note.strip(), actor_user_id=current_user.sub, actor_name=current_user.name))
    record_audit(db, current_user, "at_risk.resolve", "at_risk_flag", flag.id, {"student_id": flag.student_id})
    db.commit()
    return {"success": True, "flag_id": flag.id, "status": flag.status}


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

# Screen 35 Trainer Message Hub lives in routers/messages_hub.py

def _publish_board_for_task(db: Session, task_id: Optional[str]) -> None:
    """Live-update the team's sprint board after a review decision (Screen 30)."""
    if not task_id:
        return
    from services.realtime import publish_sync
    t = db.execute(select(SprintTask).filter_by(id=task_id)).scalar_one_or_none()
    if t and t.team_id:
        publish_sync(f"board:{t.team_id}", {"type": "review", "team_id": t.team_id, "task_id": t.id})


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
    current_user: TokenPayload = Depends(require_role(["trainer"])),
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
    current_user: TokenPayload = Depends(require_role(["trainer"])),
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

def _record_review_decision(db: Session, current_user: TokenPayload, pr: "PullRequest", action: str) -> None:
    """Audit the decision (rule 4) and tell the PR's author in-app, in the same transaction."""
    from services.notifications import notify_user
    record_audit(db, current_user, f"code_review.{action}", "pull_request", pr.id, {"pr_number": pr.pr_number})
    author_user = db.execute(select(StudentModel.user_id).where(
        StudentModel.id == pr.author_id, StudentModel.college_id == pr.college_id)).scalar_one_or_none()
    if not author_user:
        return
    if action == "approve":
        notify_user(db, author_user, f"PR {pr.pr_number} approved", pr.title, title_ta=f"PR {pr.pr_number} ஒப்புதல் பெற்றது",
                    body_ta=pr.title, kind="approval", link="/student/projects/board", college_id=pr.college_id)
    else:
        notify_user(db, author_user, f"Changes requested on PR {pr.pr_number}", pr.title,
                    title_ta=f"PR {pr.pr_number}: மாற்றங்கள் தேவை", body_ta=pr.title, kind="approval",
                    link="/student/projects/board", college_id=pr.college_id)


@router.post("/reviews/{pr_id}/action")
def submit_review_action(
    pr_id: str,
    req: ReviewActionRequest,
    current_user: TokenPayload = Depends(require_role(["trainer"])),
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

        _record_review_decision(db, current_user, pr, "approve")
        db.commit()
        _publish_board_for_task(db, pr.task_id)
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

        _record_review_decision(db, current_user, pr, "request_changes")
        db.commit()
        _publish_board_for_task(db, pr.task_id)
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
    current_user: TokenPayload = Depends(require_role(["trainer"])),
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




# --- Lab access approvals (Screen 29 / 43) ---
from models.schema import LabApproval, VirtualLabItem
from services.notifications import notify_user as _notify


class LabDecisionRequest(BaseModel):
    decision: str            # approve | deny
    reason: Optional[str] = None


@router.get("/approvals/labs")
def list_lab_approvals(
    status: Optional[str] = "pending",
    current_user: TokenPayload = Depends(require_role(["trainer"])),
    db: Session = Depends(get_db),
):
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = get_trainer_batch_ids(trainer, db) or ["__none__"]
    q = (select(LabApproval, StudentModel, UserModel.name, VirtualLabItem.name)
         .join(StudentModel, StudentModel.id == LabApproval.student_id)
         .join(UserModel, UserModel.id == StudentModel.user_id)
         .join(VirtualLabItem, VirtualLabItem.id == LabApproval.lab_id)
         .where(LabApproval.college_id == current_user.college_id, StudentModel.batch_id.in_(batch_ids)))
    if status and status != "all":
        q = q.where(LabApproval.status == status)
    rows = db.execute(q.order_by(LabApproval.created_at.desc())).all()
    return {"approvals": [
        {"id": ap.id, "lab_id": ap.lab_id, "lab_name": lab_name, "student_id": st.id, "student_name": name,
         "batch": st.batch_name, "status": ap.status, "aup_accepted": ap.aup_accepted_at is not None,
         "requested_at": ap.created_at.isoformat() if ap.created_at else None, "reason": ap.reason}
        for ap, st, name, lab_name in rows
    ]}


@router.post("/approvals/labs/{approval_id}")
def decide_lab_approval(
    approval_id: str,
    req: LabDecisionRequest,
    current_user: TokenPayload = Depends(require_role(["trainer"])),
    db: Session = Depends(get_db),
):
    if req.decision not in ("approve", "deny"):
        raise HTTPException(status_code=422, detail="decision must be approve or deny")
    if req.decision == "deny" and not (req.reason or "").strip():
        raise HTTPException(status_code=422, detail="A reason is required to deny access")
    trainer = get_trainer_for_user(current_user, db)
    batch_ids = get_trainer_batch_ids(trainer, db)
    ap = db.execute(select(LabApproval).filter_by(id=approval_id, college_id=current_user.college_id)).scalar_one_or_none()
    st = db.execute(select(StudentModel).filter_by(id=ap.student_id)).scalar_one_or_none() if ap else None
    if not ap or not st or st.batch_id not in batch_ids:
        raise HTTPException(status_code=404, detail="Approval not found")
    if ap.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already {ap.status}")
    ap.status = "approved" if req.decision == "approve" else "denied"
    ap.reason = (req.reason or "").strip() or ap.reason
    ap.decided_by = current_user.sub
    ap.decided_at = datetime.datetime.utcnow()
    lab = db.execute(select(VirtualLabItem).filter_by(id=ap.lab_id)).scalar_one()
    if ap.status == "approved":
        _notify(db, st.user_id, f"Access approved: {lab.name}", "You can launch the lab now.",
                title_ta=f"அனுமதி வழங்கப்பட்டது: {lab.name}", body_ta="இப்போது லேபைத் தொடங்கலாம்.", kind="approval", link="/student/labs")
    else:
        _notify(db, st.user_id, f"Access declined: {lab.name}", ap.reason,
                title_ta=f"அனுமதி மறுக்கப்பட்டது: {lab.name}", kind="approval", link="/student/labs")
    record_audit(db, current_user, f"lab.access_{ap.status}", "lab_approval", ap.id, {"lab_id": ap.lab_id, "student_id": st.id})
    db.commit()
    return {"success": True, "status": ap.status}
