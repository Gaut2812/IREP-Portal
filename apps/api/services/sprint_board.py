"""Screen 30 sprint board: membership, ordered columns, metrics, GitHub events."""
import datetime
import hashlib
import hmac
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.config import settings
from core.security import TokenPayload, normalize_role
from core.tenant import get_student_for_user, get_trainer_for_user, get_trainer_batch_ids
from models.schema import (
    Team, TeamMember, Sprint, SprintTask, ChangeRequest, Standup, BuildRun, PullRequest, Student, User,
)

COLUMNS = ["todo", "in_progress", "code_review", "done"]
COLUMN_LABEL = {"todo": "To Do", "in_progress": "In Progress", "code_review": "Code Review", "done": "Done"}


def team_for_user(db: Session, team_id: str, user: TokenPayload) -> Team:
    """Members see their team; trainers see teams that include a student from
    one of their batches. Everyone else gets 404."""
    team = db.execute(select(Team).filter_by(id=team_id, college_id=user.college_id)).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    role = normalize_role(user.role)
    member_ids = db.execute(select(TeamMember.student_id).filter_by(team_id=team.id)).scalars().all()
    if role == "student":
        st = get_student_for_user(user, db)
        if st.id not in member_ids:
            raise HTTPException(status_code=404, detail="Team not found")
    elif role == "trainer":
        tr = get_trainer_for_user(user, db)
        batches = set(get_trainer_batch_ids(tr, db))
        member_batches = set(db.execute(select(Student.batch_id).where(Student.id.in_(member_ids or ["_"]))).scalars().all())
        if not batches & member_batches:
            raise HTTPException(status_code=404, detail="Team not found")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")
    return team


def active_sprint(db: Session, team: Team) -> Optional[Sprint]:
    return db.execute(select(Sprint).filter_by(team_id=team.id, status="active").order_by(Sprint.number.desc())).scalars().first()


def build_board(db: Session, team: Team, now: Optional[datetime.datetime] = None) -> dict:
    now = now or datetime.datetime.now()
    sprint = active_sprint(db, team)
    tasks = db.execute(
        select(SprintTask).where(SprintTask.team_id == team.id, SprintTask.sprint_id == (sprint.id if sprint else None))
        .order_by(SprintTask.position, SprintTask.id)
    ).scalars().all()
    prs = {p.task_id: p for p in db.execute(select(PullRequest).where(PullRequest.task_id.in_([t.id for t in tasks] or ["_"]))).scalars().all()}
    columns = {c: [] for c in COLUMNS}
    for t in tasks:
        pr = prs.get(t.id)
        columns[t.column_name if t.column_name in columns else "todo"].append({
            "id": t.id, "title": t.title, "tag": t.tag, "tag_type": t.tag_type,
            "assignee_initials": t.assignee_initials, "assignee_name": t.assignee_name, "story_points": t.story_points,
            "pr_number": t.pr_number, "pr_status": pr.status if pr else None, "pr_id": pr.id if pr else None, "position": t.position,
        })
    total = sum(t.story_points for t in tasks)
    done = sum(t.story_points for t in tasks if t.column_name == "done")
    previous = db.execute(select(Sprint).where(Sprint.team_id == team.id, Sprint.status == "closed").order_by(Sprint.number.desc())).scalars().first()
    cr = db.execute(select(ChangeRequest).where(ChangeRequest.team_id == team.id, ChangeRequest.status != "done").order_by(ChangeRequest.created_at.desc())).scalars().first()
    build = db.execute(select(BuildRun).filter_by(team_id=team.id).order_by(BuildRun.finished_at.desc())).scalars().first()
    standups_today = db.execute(select(func.count(Standup.id)).where(Standup.sprint_id == (sprint.id if sprint else "_"), Standup.standup_date == now.date())).scalar_one()
    member_count = db.execute(select(func.count(TeamMember.id)).filter_by(team_id=team.id)).scalar_one()

    def ago(when: Optional[datetime.datetime]) -> Optional[str]:
        if not when:
            return None
        mins = int((now - when).total_seconds() // 60)
        if mins < 60:
            return f"{max(1, mins)} min ago"
        hrs = mins // 60
        return f"{hrs} hr{'s' if hrs != 1 else ''} ago" if hrs < 48 else f"{hrs // 24} days ago"

    return {
        "team": {"id": team.id, "name": team.name, "project_title": team.project_title, "client": team.client_name, "repo": team.repo_full_name, "members": member_count},
        "sprint": {"id": sprint.id, "number": sprint.number, "total": sprint.total_sprints, "ends_week": sprint.ends_week, "goal": sprint.goal} if sprint else None,
        "change_request": {"id": cr.id, "code": cr.code, "title": cr.title, "description": cr.description, "status": cr.status, "task_id": cr.task_id} if cr else None,
        "columns": [{"key": c, "label": COLUMN_LABEL[c], "tasks": columns[c]} for c in COLUMNS],
        "metrics": {
            "progress_pct": int(round(100 * done / total)) if total else 0,
            "points_done": done, "points_total": total,
            "velocity_last": previous.velocity if previous else None,
            "tasks_done": len(columns["done"]), "tasks_total": len(tasks),
        },
        "build": {"status": build.status, "run_number": build.run_number, "workflow": build.workflow, "environment": build.environment,
                  "url": build.url, "finished_ago": ago(build.finished_at)} if build else None,
        "standups_today": standups_today,
    }


def move_task(db: Session, task: SprintTask, column: str, position: Optional[int]) -> None:
    """Move a card and renumber both affected columns so positions stay dense."""
    if column not in COLUMNS:
        raise HTTPException(status_code=422, detail="Unknown column")
    if column == "done" and task.pr_number:
        pr = db.execute(select(PullRequest).filter_by(task_id=task.id)).scalar_one_or_none()
        if pr and pr.status != "approved":
            raise HTTPException(status_code=409, detail="This card moves to Done when its pull request is approved and merged")
    old_col = task.column_name
    siblings = db.execute(
        select(SprintTask).where(SprintTask.team_id == task.team_id, SprintTask.sprint_id == task.sprint_id,
                                 SprintTask.column_name == column, SprintTask.id != task.id).order_by(SprintTask.position, SprintTask.id)
    ).scalars().all()
    pos = len(siblings) if position is None else max(0, min(position, len(siblings)))
    siblings.insert(pos, task)
    task.column_name = column
    for i, t in enumerate(siblings):
        t.position = i
    if old_col != column:
        rest = db.execute(
            select(SprintTask).where(SprintTask.team_id == task.team_id, SprintTask.sprint_id == task.sprint_id,
                                     SprintTask.column_name == old_col).order_by(SprintTask.position, SprintTask.id)
        ).scalars().all()
        for i, t in enumerate(rest):
            t.position = i


def github_signature(body: bytes) -> str:
    return "sha256=" + hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def verify_github(body: bytes, header: Optional[str]) -> bool:
    return bool(header) and hmac.compare_digest(github_signature(body), header)
