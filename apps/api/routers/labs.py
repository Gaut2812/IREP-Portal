"""Labs service endpoints beyond the catalog (screen 29): open a server or external lab,
browser-lab beacons, and the trainer lab board. Spec: docs/labs/README.md"""
import datetime
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_student_for_user, get_trainer_batch_ids, get_trainer_for_user
from models.schema import LabSession, Student, User, VirtualLabItem
from services.audit import record_audit
from services.lab_orchestrator import IDLE_LIMIT_MIN, accept_beacon, connect_url, running_minutes, stop_session
from services.notifications import notify_user

router = APIRouter(tags=["Labs"])


class TrainerStopIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=255)


@router.get("/student/lab-sessions/{session_id}/connect")
def connect(session_id: str, current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    """A short-lived URL into the student's own running workspace (JupyterHub) or external sandbox."""
    student = get_student_for_user(current_user, db)
    s = db.execute(select(LabSession).where(LabSession.id == session_id, LabSession.student_id == student.id)).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Lab session not found")
    if s.status == "starting":
        raise HTTPException(status_code=409, detail={"reason": "starting", "message": "Your workspace is starting. Try again in a few seconds."})
    lab = db.get(VirtualLabItem, s.lab_id)
    try:
        url = connect_url(db, s, lab)
    except Exception:
        raise HTTPException(status_code=503, detail={"reason": "unavailable", "message": "The lab server is not reachable right now. Try again shortly."})
    if not url:
        raise HTTPException(status_code=409, detail={"reason": "nothing_to_open", "message": "This lab runs inside this page."})
    s.last_active_at = datetime.datetime.now()
    record_audit(db, current_user, "lab.connect", "lab_session", s.id, {"lab_id": lab.id, "runtime": lab.runtime})
    db.commit()
    return {"url": url}


@router.post("/labs/beacon")
async def beacon(request: Request, db: Session = Depends(get_db)):
    """Browser-lab heartbeat. Authenticated by a token scoped to one session, so it also works
    from navigator.sendBeacon (text/plain body) when the tab closes."""
    raw = await request.body()
    try:
        token = json.loads(raw or b"{}").get("token", "")
    except (ValueError, AttributeError):
        token = ""
    s = accept_beacon(db, token) if token else None
    if s is None:
        raise HTTPException(status_code=401, detail="Invalid lab token")
    db.commit()
    now = datetime.datetime.now()
    return {"status": s.status, "minutes_left": max(0, int((s.expires_at - now).total_seconds() // 60)) if s.status == "running" else 0}


# ------------------------------------------------------------------ trainer lab board

def _trainer_students(db: Session, user: TokenPayload) -> dict:
    batch_ids = get_trainer_batch_ids(get_trainer_for_user(user, db), db) or ["_"]
    rows = db.execute(select(Student, User.name).join(User, User.id == Student.user_id)
                      .where(Student.college_id == user.college_id, Student.batch_id.in_(batch_ids))).all()
    return {s.id: (s, name) for s, name in rows}


@router.get("/trainer/labs")
def lab_board(current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    """Live lab sessions in the trainer's batches (no workspace contents, only who, which lab and for how long)."""
    students = _trainer_students(db, current_user)
    now = datetime.datetime.now()
    sessions = db.execute(select(LabSession).where(LabSession.college_id == current_user.college_id,
                                                   LabSession.student_id.in_(list(students) or ["_"]),
                                                   LabSession.status.in_(["running", "starting"]))
                          .order_by(LabSession.started_at)).scalars().all()
    labs = {l.id: l for l in db.execute(select(VirtualLabItem).where(VirtualLabItem.college_id == current_user.college_id)).scalars()}
    out = []
    for s in sessions:
        st, name = students[s.student_id]
        lab = labs.get(s.lab_id)
        idle = int((now - s.last_active_at).total_seconds() // 60)
        out.append({"id": s.id, "student": name, "batch": st.batch_name, "lab": lab.name if lab else s.lab_id,
                    "runtime": lab.runtime if lab else None, "status": s.status, "running_minutes": running_minutes(s, now),
                    "idle_minutes": idle, "idle_warning": idle >= IDLE_LIMIT_MIN // 2,
                    "minutes_left": max(0, int((s.expires_at - now).total_seconds() // 60))})
    return {"sessions": out, "summary": {"live": len(out), "idle": sum(1 for r in out if r["idle_warning"])}}


@router.post("/trainer/lab-sessions/{session_id}/stop")
def trainer_stop(session_id: str, req: TrainerStopIn, current_user: TokenPayload = Depends(require_role(["trainer"])),
                 db: Session = Depends(get_db)):
    students = _trainer_students(db, current_user)
    s = db.execute(select(LabSession).where(LabSession.id == session_id, LabSession.college_id == current_user.college_id)).scalar_one_or_none()
    if s is None or s.student_id not in students:
        raise HTTPException(status_code=404, detail="Lab session not found")
    minutes = stop_session(db, s, "trainer", datetime.datetime.now())
    st, _ = students[s.student_id]
    lab = db.get(VirtualLabItem, s.lab_id)
    reason = (req.reason or "").strip()
    notify_user(db, st.user_id, f"Your trainer stopped {lab.name if lab else 'your lab'}", reason or "Save your work and ask your trainer if you need it again.",
                title_ta=f"உங்கள் பயிற்சியாளர் {lab.name if lab else 'ஆய்வகத்தை'} நிறுத்தினார்", kind="lab", link="/student/labs",
                college_id=current_user.college_id)
    record_audit(db, current_user, "lab.stop_by_trainer", "lab_session", s.id, {"student_id": s.student_id, "minutes": minutes, "reason": reason})
    db.commit()
    return {"status": s.status, "minutes": minutes}
