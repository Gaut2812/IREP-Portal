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
from models.schema import Team, TeamMember, Sprint, SprintTask, ChangeRequest, Standup, BuildRun, PullRequest
from services.sprint_board import team_for_user, active_sprint, build_board, move_task, verify_github
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
    return build_board(db, team)


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
