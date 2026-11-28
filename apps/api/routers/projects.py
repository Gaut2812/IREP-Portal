"""Screen 30: Sprint Board (company simulation)."""
import datetime
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from core.security import require_role, TokenPayload, decode_access_token, websocket_user, normalize_role
from core.tenant import get_student_for_user
from models.schema import Team, TeamMember, Sprint, SprintTask, ChangeRequest, Standup, BuildRun, PullRequest, Student, User
from core.tenant import get_trainer_batch_ids, get_trainer_for_user
from services.sprint_board import (team_for_user, active_sprint, build_board, move_task, verify_github, team_members, initials,
                                   can_delete_task)
from services.realtime import hub, publish_sync
from services.audit import record_audit
from services.notifications import notify_user

router = APIRouter(tags=["Sprint Board"])
BOARD_ROLES = ["student", "trainer"]


class MoveRequest(BaseModel):
    column: str
    position: Optional[int] = None


class StandupRequest(BaseModel):
    yesterday: str = Field(min_length=2, max_length=1000)
    today: str = Field(min_length=2, max_length=1000)
    blockers: Optional[str] = Field(default=None, max_length=1000)


class ChangeRequestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None
    tag: str = "Feature"
    story_points: int = Field(default=3, ge=1, le=13)


def _publish(team_id: str, kind: str, **extra) -> None:
    publish_sync(f"board:{team_id}", {"type": kind, "team_id": team_id, **extra})


@router.get("/student/projects/my-team")
def my_team(current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    st = get_student_for_user(current_user, db)
    tm = db.execute(select(TeamMember).filter_by(student_id=st.id)).scalars().first()
    if not tm:
        return {"team_id": None}
    return {"team_id": tm.team_id}


@router.get("/teams/{team_id}/board")
def get_board(team_id: str, current_user: TokenPayload = Depends(require_role(BOARD_ROLES)), db: Session = Depends(get_db)):
    team = team_for_user(db, team_id, current_user)
    viewer, trainer = _viewer(db, current_user)
    return build_board(db, team, viewer_student_id=viewer, is_trainer=trainer)


def _viewer(db: Session, user: TokenPayload):
    """(students.id or None, is the caller a trainer)."""
    if normalize_role(user.role) == "student":
        return get_student_for_user(user, db).id, False
    return None, True


TAG_TYPES = {"feature": "Feature", "frontend": "Frontend", "backend": "Backend", "ai": "AI", "qa": "QA", "devops": "DevOps"}


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    tag_type: str = Field(default="feature", pattern="^(feature|frontend|backend|ai|qa|devops)$")
    story_points: int = Field(default=3, ge=1, le=13)
    assignee_student_id: Optional[str] = None


class TaskEdit(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    tag_type: Optional[str] = Field(default=None, pattern="^(feature|frontend|backend|ai|qa|devops)$")
    story_points: Optional[int] = Field(default=None, ge=1, le=13)
    assignee_student_id: Optional[str] = None
    unassign: bool = False


def _assign(db: Session, team: Team, task: SprintTask, student_id: Optional[str]) -> None:
    if not student_id:
        task.assignee_student_id, task.assignee_initials, task.assignee_name = None, "—", "Unassigned"
        return
    member = next((m for m in team_members(db, team) if m["student_id"] == student_id), None)
    if member is None:
        raise HTTPException(status_code=422, detail="Assign the task to a member of this team")
    task.assignee_student_id, task.assignee_initials, task.assignee_name = student_id, member["initials"], member["name"][:64]


def _task_for_member(db: Session, task_id: str, user: TokenPayload):
    task = db.execute(select(SprintTask).filter_by(id=task_id, college_id=user.college_id)).scalar_one_or_none()
    if not task or not task.team_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task, team_for_user(db, task.team_id, user)


@router.post("/teams/{team_id}/tasks", status_code=201)
def add_task(team_id: str, req: TaskIn, current_user: TokenPayload = Depends(require_role(BOARD_ROLES)), db: Session = Depends(get_db)):
    """Any team member (or the team's trainer) adds a card to To do of the active sprint."""
    team = team_for_user(db, team_id, current_user)
    sprint = active_sprint(db, team)
    if sprint is None:
        raise HTTPException(status_code=409, detail="This project has no active sprint; ask your trainer to start one")
    viewer, _ = _viewer(db, current_user)
    task = SprintTask(id=f"task_{uuid.uuid4().hex[:12]}", college_id=team.college_id, project_id=team.project_id or team.id,
                      title=req.title.strip(), tag=TAG_TYPES[req.tag_type], tag_type=req.tag_type, column_name="todo",
                      story_points=req.story_points, team_id=team.id, sprint_id=sprint.id, position=999, created_by_student_id=viewer)
    _assign(db, team, task, req.assignee_student_id)
    db.add(task)
    db.flush()
    move_task(db, task, "todo", 0)
    record_audit(db, current_user, "board.task_added", "sprint_task", task.id, {"team_id": team.id})
    db.commit()
    _publish(team.id, "task", task_id=task.id)
    return {"success": True, "task_id": task.id}


@router.patch("/tasks/{task_id}")
def edit_task(task_id: str, req: TaskEdit, current_user: TokenPayload = Depends(require_role(BOARD_ROLES)), db: Session = Depends(get_db)):
    """Team members edit any card of their team (title, tag, points, assignee): it is a shared board."""
    task, team = _task_for_member(db, task_id, current_user)
    if req.title is not None:
        task.title = req.title.strip()
    if req.tag_type is not None:
        task.tag_type, task.tag = req.tag_type, TAG_TYPES[req.tag_type]
    if req.story_points is not None:
        task.story_points = req.story_points
    if req.unassign:
        _assign(db, team, task, None)
    elif req.assignee_student_id:
        _assign(db, team, task, req.assignee_student_id)
    record_audit(db, current_user, "board.task_edited", "sprint_task", task.id, {"team_id": team.id})
    db.commit()
    _publish(team.id, "task", task_id=task.id)
    return {"success": True}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, current_user: TokenPayload = Depends(require_role(BOARD_ROLES)), db: Session = Depends(get_db)):
    """A student deletes a card they created or own while it is open; the trainer any card. A card with a pull request
    stays (the review history points at it)."""
    task, team = _task_for_member(db, task_id, current_user)
    viewer, trainer = _viewer(db, current_user)
    has_pr = bool(task.pr_number) or db.execute(select(PullRequest.id).where(PullRequest.task_id == task.id)).first() is not None
    if not can_delete_task(task, has_pr, viewer, trainer):
        raise HTTPException(status_code=403 if not has_pr else 409,
                            detail="This card has a pull request, so it stays" if has_pr else "You can delete only your own open cards")
    if db.execute(select(ChangeRequest.id).where(ChangeRequest.task_id == task.id)).first():
        raise HTTPException(status_code=409, detail="This card came from a change request; close the request instead")
    record_audit(db, current_user, "board.task_deleted", "sprint_task", task.id, {"team_id": team.id, "title": task.title})
    db.delete(task)
    db.commit()
    _publish(team.id, "task", task_id=task_id)
    return {"success": True}


# ------------------------------------------------------------------ trainer: projects (teams) for my batches

class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    project_title: str = Field(min_length=3, max_length=255)
    client_name: str = Field(default="Trainer", min_length=2, max_length=128)
    description: Optional[str] = Field(default=None, max_length=4000)
    goals: Optional[str] = Field(default=None, max_length=4000)
    repo_full_name: Optional[str] = Field(default=None, max_length=255, pattern=r"^[\w.-]+/[\w.-]+$")
    total_sprints: int = Field(default=3, ge=1, le=8)
    sprint_goal: Optional[str] = Field(default=None, max_length=1000)
    member_ids: list = Field(default_factory=list)
    lead_id: Optional[str] = None


class ProjectEdit(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    project_title: Optional[str] = Field(default=None, min_length=3, max_length=255)
    client_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    description: Optional[str] = Field(default=None, max_length=4000)
    goals: Optional[str] = Field(default=None, max_length=4000)
    repo_full_name: Optional[str] = Field(default=None, max_length=255)
    sprint_goal: Optional[str] = Field(default=None, max_length=1000)


class MembersIn(BaseModel):
    member_ids: list = Field(default_factory=list)
    lead_id: Optional[str] = None


class NextSprintIn(BaseModel):
    goal: Optional[str] = Field(default=None, max_length=1000)


TRAINER = require_role(["trainer"])


def _my_students(db: Session, user: TokenPayload) -> dict:
    trainer = get_trainer_for_user(user, db)
    batches = get_trainer_batch_ids(trainer, db)
    rows = db.execute(select(Student, User.name).join(User, User.id == Student.user_id)
                      .where(Student.college_id == user.college_id, Student.batch_id.in_(batches or ["_"]))
                      .order_by(Student.batch_name, User.name)).all()
    return {st.id: (st, name) for st, name in rows}


def _set_members(db: Session, team: Team, user: TokenPayload, member_ids: list, lead_id: Optional[str]) -> None:
    mine = _my_students(db, user)
    wanted = list(dict.fromkeys(str(i) for i in member_ids))
    unknown = [i for i in wanted if i not in mine]
    if unknown:
        raise HTTPException(status_code=422, detail="Pick students from your own batches")
    busy = db.execute(select(TeamMember.student_id, Team.name).join(Team, Team.id == TeamMember.team_id)
                      .where(TeamMember.student_id.in_(wanted or ["_"]), TeamMember.team_id != team.id)).all()
    if busy:
        names = ", ".join(f"{mine[sid][1]} ({tname})" for sid, tname in busy[:5])
        raise HTTPException(status_code=409, detail=f"Already in another project team: {names}")
    current = {m.student_id: m for m in db.execute(select(TeamMember).filter_by(team_id=team.id)).scalars()}
    for sid, m in current.items():
        if sid not in wanted:
            db.delete(m)
    for sid in wanted:
        role = "lead" if sid == lead_id else "developer"
        if sid in current:
            current[sid].role = role
        else:
            db.add(TeamMember(id=f"tm_{uuid.uuid4().hex[:12]}", college_id=team.college_id, team_id=team.id, student_id=sid, role=role))


def _my_team(db: Session, team_id: str, user: TokenPayload) -> Team:
    team = team_for_user(db, team_id, user)        # 404 unless a member is in one of my batches (or I made it)
    return team


def _project_row(db: Session, team: Team) -> dict:
    sprint = active_sprint(db, team)
    tasks = db.execute(select(SprintTask).where(SprintTask.team_id == team.id, SprintTask.sprint_id == (sprint.id if sprint else None))).scalars().all()
    total = sum(t.story_points for t in tasks)
    done = sum(t.story_points for t in tasks if t.column_name == "done")
    return {"id": team.id, "name": team.name, "project_title": team.project_title, "client": team.client_name,
            "description": team.description, "goals": team.goals, "repo": team.repo_full_name,
            "members": team_members(db, team),
            "sprint": {"id": sprint.id, "number": sprint.number, "total": sprint.total_sprints, "goal": sprint.goal} if sprint else None,
            "progress_pct": int(round(100 * done / total)) if total else 0, "tasks": len(tasks),
            "has_history": bool(db.execute(select(PullRequest.id).where(PullRequest.task_id.in_(
                select(SprintTask.id).where(SprintTask.team_id == team.id)))).first()
                or db.execute(select(Standup.id).join(Sprint, Sprint.id == Standup.sprint_id).where(Sprint.team_id == team.id)).first())}


@router.get("/trainer/projects")
def trainer_projects(current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """Project teams that include a student from my batches, and the students I can put in a team."""
    trainer = get_trainer_for_user(current_user, db)
    mine = _my_students(db, current_user)
    team_ids = set(db.execute(select(TeamMember.team_id).where(TeamMember.student_id.in_(list(mine) or ["_"]))).scalars())
    team_ids |= set(db.execute(select(Team.id).where(Team.trainer_id == trainer.id)).scalars())
    teams = db.execute(select(Team).where(Team.id.in_(list(team_ids) or ["_"]), Team.college_id == current_user.college_id)
                       .order_by(Team.name)).scalars().all()
    taken = dict(db.execute(select(TeamMember.student_id, TeamMember.team_id).where(TeamMember.student_id.in_(list(mine) or ["_"]))).all())
    return {"projects": [_project_row(db, t) for t in teams],
            "students": [{"student_id": sid, "name": name, "batch": st.batch_name, "team_id": taken.get(sid)} for sid, (st, name) in mine.items()]}


@router.post("/trainer/projects", status_code=201)
def create_project(req: ProjectIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    trainer = get_trainer_for_user(current_user, db)
    if not req.member_ids:
        raise HTTPException(status_code=422, detail="Add at least one student to the team")
    team = Team(id=f"team_{uuid.uuid4().hex[:12]}", college_id=current_user.college_id, name=req.name.strip(),
                project_title=req.project_title.strip(), client_name=req.client_name.strip(), trainer_id=trainer.id,
                description=(req.description or "").strip() or None, goals=(req.goals or "").strip() or None,
                repo_full_name=(req.repo_full_name or "").strip() or None)
    db.add(team)
    db.flush()
    _set_members(db, team, current_user, req.member_ids, req.lead_id)
    db.add(Sprint(id=f"sprint_{uuid.uuid4().hex[:12]}", college_id=team.college_id, team_id=team.id, number=1,
                  total_sprints=req.total_sprints, status="active", goal=(req.sprint_goal or "").strip() or None))
    db.flush()
    for uid in db.execute(select(Student.user_id).where(Student.id.in_(req.member_ids))).scalars():
        if uid:
            notify_user(db, uid, f"New project: {team.project_title}", f"You are in team {team.name}. Open the Sprint Board.",
                        title_ta=f"புதிய புராஜெக்ட்: {team.project_title}", body_ta=f"நீங்கள் {team.name} அணியில் உள்ளீர்கள். ஸ்பிரிண்ட் போர்டைத் திறக்கவும்.",
                        kind="info", link="/student/projects/board", college_id=team.college_id)
    record_audit(db, current_user, "project.created", "team", team.id, {"members": len(req.member_ids)})
    db.commit()
    return _project_row(db, team)


@router.put("/trainer/projects/{team_id}")
def edit_project(team_id: str, req: ProjectEdit, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    team = _my_team(db, team_id, current_user)
    for k in ("name", "project_title", "client_name"):
        v = getattr(req, k)
        if v is not None:
            setattr(team, k, v.strip())
    for k, col in (("description", "description"), ("goals", "goals"), ("repo_full_name", "repo_full_name")):
        v = getattr(req, k)
        if v is not None:
            setattr(team, col, v.strip() or None)
    if req.sprint_goal is not None:
        sprint = active_sprint(db, team)
        if sprint:
            sprint.goal = req.sprint_goal.strip() or None
    record_audit(db, current_user, "project.edited", "team", team.id, {})
    db.commit()
    _publish(team.id, "project")
    return _project_row(db, team)


@router.put("/trainer/projects/{team_id}/members")
def set_project_members(team_id: str, req: MembersIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    team = _my_team(db, team_id, current_user)
    if not req.member_ids:
        raise HTTPException(status_code=422, detail="A team needs at least one student")
    _set_members(db, team, current_user, req.member_ids, req.lead_id)
    record_audit(db, current_user, "project.members", "team", team.id, {"members": len(req.member_ids)})
    db.commit()
    _publish(team.id, "project")
    return _project_row(db, team)


@router.post("/trainer/projects/{team_id}/next-sprint")
def next_sprint(team_id: str, req: NextSprintIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """Close the active sprint (its velocity = points done) and start the next; unfinished cards move along."""
    team = _my_team(db, team_id, current_user)
    cur = active_sprint(db, team)
    if cur is None:
        raise HTTPException(status_code=409, detail="This project has no active sprint")
    if cur.number >= cur.total_sprints:
        raise HTTPException(status_code=409, detail="That was the last sprint of this project")
    tasks = db.execute(select(SprintTask).where(SprintTask.sprint_id == cur.id)).scalars().all()
    cur.status, cur.velocity = "closed", sum(t.story_points for t in tasks if t.column_name == "done")
    nxt = Sprint(id=f"sprint_{uuid.uuid4().hex[:12]}", college_id=team.college_id, team_id=team.id, number=cur.number + 1,
                 total_sprints=cur.total_sprints, ends_week=cur.ends_week + 2, status="active", goal=(req.goal or "").strip() or None)
    db.add(nxt)
    db.flush()
    for t in tasks:
        if t.column_name != "done":
            t.sprint_id = nxt.id
    record_audit(db, current_user, "project.next_sprint", "team", team.id, {"closed": cur.number, "velocity": cur.velocity})
    db.commit()
    _publish(team.id, "project")
    return _project_row(db, team)


@router.delete("/trainer/projects/{team_id}")
def delete_project(team_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    """Delete a project with no work on record yet (no pull requests, no stand-ups). Otherwise it is kept."""
    team = _my_team(db, team_id, current_user)
    if _project_row(db, team)["has_history"]:
        raise HTTPException(status_code=409, detail="This project has pull requests or stand-ups on record, so it is kept")
    for model, col in ((ChangeRequest, ChangeRequest.team_id), (SprintTask, SprintTask.team_id), (BuildRun, BuildRun.team_id)):
        for row in db.execute(select(model).where(col == team.id)).scalars():
            db.delete(row)
    db.flush()
    for row in db.execute(select(Sprint).where(Sprint.team_id == team.id)).scalars():
        db.delete(row)
    for row in db.execute(select(TeamMember).where(TeamMember.team_id == team.id)).scalars():
        db.delete(row)
    db.flush()
    record_audit(db, current_user, "project.deleted", "team", team.id, {"title": team.project_title})
    db.delete(team)
    db.commit()
    return {"success": True}


@router.patch("/tasks/{task_id}/move")
def move(task_id: str, req: MoveRequest, current_user: TokenPayload = Depends(require_role(BOARD_ROLES)), db: Session = Depends(get_db)):
    task = db.execute(select(SprintTask).filter_by(id=task_id, college_id=current_user.college_id)).scalar_one_or_none()
    if not task or not task.team_id:
        raise HTTPException(status_code=404, detail="Task not found")
    team_for_user(db, task.team_id, current_user)
    before = task.column_name
    move_task(db, task, req.column, req.position)
    record_audit(db, current_user, "board.move", "sprint_task", task.id, {"from": before, "to": req.column})
    db.commit()
    _publish(task.team_id, "move", task_id=task.id, column=req.column)
    return {"success": True, "task_id": task.id, "column": task.column_name, "position": task.position}


@router.post("/sprints/{sprint_id}/standups")
def submit_standup(sprint_id: str, req: StandupRequest, current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    sprint = db.execute(select(Sprint).filter_by(id=sprint_id, college_id=current_user.college_id)).scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    team = team_for_user(db, sprint.team_id, current_user)
    st = get_student_for_user(current_user, db)
    today = datetime.date.today()
    row = db.execute(select(Standup).filter_by(sprint_id=sprint.id, student_id=st.id, standup_date=today)).scalar_one_or_none()
    if row:
        row.yesterday, row.today, row.blockers = req.yesterday.strip(), req.today.strip(), (req.blockers or "").strip() or None
    else:
        row = Standup(id=f"su_{uuid.uuid4().hex[:16]}", college_id=team.college_id, sprint_id=sprint.id, student_id=st.id,
                      standup_date=today, yesterday=req.yesterday.strip(), today=req.today.strip(), blockers=(req.blockers or "").strip() or None)
        db.add(row)
    db.commit()
    _publish(team.id, "standup")
    return {"success": True, "standup_id": row.id, "date": today.isoformat()}


@router.get("/sprints/{sprint_id}/standups")
def list_standups(sprint_id: str, current_user: TokenPayload = Depends(require_role(BOARD_ROLES)), db: Session = Depends(get_db)):
    sprint = db.execute(select(Sprint).filter_by(id=sprint_id, college_id=current_user.college_id)).scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    team_for_user(db, sprint.team_id, current_user)
    from models.schema import Student, User
    rows = db.execute(
        select(Standup, User.name).join(Student, Student.id == Standup.student_id).join(User, User.id == Student.user_id)
        .where(Standup.sprint_id == sprint.id).order_by(Standup.standup_date.desc(), User.name)
    ).all()
    return {"standups": [{"id": s.id, "name": n, "date": s.standup_date.isoformat(), "yesterday": s.yesterday, "today": s.today, "blockers": s.blockers} for s, n in rows[:30]]}


@router.post("/teams/{team_id}/change-requests")
def raise_change_request(team_id: str, req: ChangeRequestCreate, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    """The trainer plays the client: a change request adds a card to To Do."""
    team = team_for_user(db, team_id, current_user)
    sprint = active_sprint(db, team)
    n = len(db.execute(select(ChangeRequest.id).filter_by(team_id=team.id)).scalars().all()) + 1
    code = f"CR-{n:02d}"
    task = SprintTask(id=f"task_{uuid.uuid4().hex[:10]}", college_id=team.college_id, project_id=team.project_id or team.id,
                      title=f"{req.title} ({code})", tag=req.tag, tag_type="feature", column_name="todo", assignee_initials="—",
                      assignee_name="Unassigned", story_points=req.story_points, team_id=team.id, sprint_id=sprint.id if sprint else None, position=999)
    db.add(task)
    db.flush()
    move_task(db, task, "todo", 0)
    cr = ChangeRequest(id=f"cr_{uuid.uuid4().hex[:12]}", college_id=team.college_id, team_id=team.id, sprint_id=sprint.id if sprint else None,
                       code=code, title=req.title, description=req.description, status="open", task_id=task.id, raised_by=current_user.sub)
    db.add(cr)
    record_audit(db, current_user, "board.change_request", "change_request", cr.id, {"team_id": team.id})
    member_users = db.execute(
        select(TeamMember.student_id).filter_by(team_id=team.id)
    ).scalars().all()
    from models.schema import Student
    for uid in db.execute(select(Student.user_id).where(Student.id.in_(member_users or ["_"]))).scalars().all():
        notify_user(db, uid, f"Change request {code}: {req.title}", req.description, kind="info", link="/student/projects/board", college_id=team.college_id)
    db.commit()
    _publish(team.id, "change_request")
    return {"success": True, "code": code, "task_id": task.id}


@router.post("/webhooks/github")
async def github_webhook(request: Request,
                         x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
                         x_github_event: Optional[str] = Header(default=None, alias="X-GitHub-Event")):
    """GitHub App webhook: pull_request opened -> Code Review; merged -> Done;
    workflow_run completed -> build status."""
    body = await request.body()
    if not verify_github(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = json.loads(body or b"{}")
    repo = (payload.get("repository") or {}).get("full_name")
    db = SessionLocal()
    changed_team = None
    result = {"success": True, "event": x_github_event}
    try:
        team = db.execute(select(Team).filter_by(repo_full_name=repo)).scalar_one_or_none()
        if not team:
            return {"success": True, "ignored": "unknown repository"}
        changed_team = team.id
        if x_github_event == "pull_request":
            pr = payload.get("pull_request") or {}
            number = f"#{pr.get('number')}"
            task = db.execute(select(SprintTask).filter_by(team_id=team.id, pr_number=number)).scalar_one_or_none()
            if not task:
                return {"success": True, "ignored": "no task for this pull request"}
            action = payload.get("action")
            if action in ("opened", "reopened", "ready_for_review") and task.column_name != "done":
                move_task(db, task, "code_review", None)
            elif action == "closed" and pr.get("merged"):
                row = db.execute(select(PullRequest).filter_by(task_id=task.id)).scalar_one_or_none()
                if row:
                    row.status = "approved"
                move_task(db, task, "done", None)
            result.update({"task_id": task.id, "column": task.column_name})
        elif x_github_event == "workflow_run" and (payload.get("action") == "completed"):
            run = payload.get("workflow_run") or {}
            status = "passing" if run.get("conclusion") == "success" else "failing"
            db.add(BuildRun(id=f"br_{uuid.uuid4().hex[:14]}", college_id=team.college_id, team_id=team.id,
                            run_number=int(run.get("run_number") or 0), workflow=run.get("name") or "CI", status=status,
                            environment="staging" if status == "passing" else None, url=run.get("html_url"),
                            finished_at=datetime.datetime.now()))
            result.update({"build": status})
        else:
            return {"success": True, "ignored": x_github_event}
        db.commit()
    finally:
        db.close()
    if changed_team:
        await hub.publish(f"board:{changed_team}", {"type": "github", "team_id": changed_team})
    return result


@router.websocket("/ws/board/{team_id}")
async def board_socket(websocket: WebSocket, team_id: str, token: Optional[str] = None):
    payload = websocket_user(token)          # local or Keycloak token, and still active
    if not payload:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        team_for_user(db, team_id, payload)
    except HTTPException:
        await websocket.close(code=4404)
        return
    finally:
        db.close()
    channel = f"board:{team_id}"
    await hub.subscribe(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(channel, websocket)
