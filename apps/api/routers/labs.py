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


# ------------------------------------------------------------------ S13: exercises with checkers

class CheckIn(BaseModel):
    rows: Optional[list] = None          # sql: the result rows the browser got
    output: Optional[str] = Field(default=None, max_length=20000)   # python: what the program printed


def _exercise_out(e, lang: str, result) -> dict:
    ta = lang == "ta"
    return {"id": e.id, "position": e.position, "title": e.title_ta if ta and e.title_ta else e.title_en,
            "prompt": e.prompt_ta if ta and e.prompt_ta else e.prompt_en, "setup": e.setup, "points": e.points,
            "passed": bool(result and result.passed), "attempts": result.attempts if result else 0}


@router.get("/student/labs/{lab_id}/exercises")
def lab_exercises(lab_id: str, lang: str = "en", current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    from models.schema import LabExercise, LabExerciseResult
    from services.lab_orchestrator import lock_reason
    student = get_student_for_user(current_user, db)
    lab = db.execute(select(VirtualLabItem).where(VirtualLabItem.id == lab_id, VirtualLabItem.college_id == student.college_id)).scalar_one_or_none()
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    locked = lock_reason(db, student, lab, datetime.datetime.now())
    if locked and locked[0] in ("semester", "track"):
        raise HTTPException(status_code=403, detail=locked[1])
    exs = db.execute(select(LabExercise).where(LabExercise.lab_id == lab.id, LabExercise.college_id == student.college_id)
                     .order_by(LabExercise.position)).scalars().all()
    results = {r.exercise_id: r for r in db.execute(select(LabExerciseResult).where(
        LabExerciseResult.student_id == student.id, LabExerciseResult.exercise_id.in_([e.id for e in exs] or ["_"]))).scalars()}
    rows = [_exercise_out(e, lang, results.get(e.id)) for e in exs]
    return {"lab_id": lab.id, "kit": lab.browser_kit, "exercises": rows,
            "score": sum(r["points"] for r in rows if r["passed"]), "max_score": sum(r["points"] for r in rows)}


@router.post("/student/lab-exercises/{exercise_id}/check")
def check_exercise(exercise_id: str, req: CheckIn, current_user: TokenPayload = Depends(require_role(["student"])), db: Session = Depends(get_db)):
    """A practice check: needs a running session of the exercise's lab; the expected result stays here."""
    import uuid
    from models.schema import LabExercise, LabExerciseResult
    from services.lab_checkers import check
    student = get_student_for_user(current_user, db)
    e = db.execute(select(LabExercise).where(LabExercise.id == exercise_id, LabExercise.college_id == student.college_id)).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    running = db.execute(select(LabSession.id).where(LabSession.student_id == student.id, LabSession.lab_id == e.lab_id,
                                                     LabSession.status == "running")).first()
    if not running:
        raise HTTPException(status_code=409, detail="Open the lab first, then check your answer there")
    lab = db.get(VirtualLabItem, e.lab_id)
    submitted = req.rows if lab.browser_kit == "sql" else req.output
    if submitted is None:
        raise HTTPException(status_code=422, detail="Send rows (SQL) or output (Python)")
    passed = check(lab.browser_kit or "", e.expected, submitted, e.ordered)
    r = db.execute(select(LabExerciseResult).where(LabExerciseResult.student_id == student.id,
                                                   LabExerciseResult.exercise_id == e.id)).scalar_one_or_none()
    if r is None:
        r = LabExerciseResult(id=f"exr_{uuid.uuid4().hex[:16]}", college_id=student.college_id, student_id=student.id, exercise_id=e.id)
        db.add(r)
    r.attempts = (r.attempts or 0) + 1
    if passed and not r.passed:
        r.passed, r.passed_at = True, datetime.datetime.utcnow()
    for s in db.execute(select(LabSession).where(LabSession.id == running[0])).scalars():
        s.last_active_at = datetime.datetime.now()
    db.commit()
    return {"passed": passed, "attempts": r.attempts, "points": e.points if passed else 0}


@router.get("/trainer/labs/exercises")
def exercise_progress(current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    """How many of the trainer's students passed each exercise (counts only)."""
    from sqlalchemy import func
    from models.schema import LabExercise, LabExerciseResult
    students = _trainer_students(db, current_user)
    exs = db.execute(select(LabExercise, VirtualLabItem.name).join(VirtualLabItem, VirtualLabItem.id == LabExercise.lab_id)
                     .where(LabExercise.college_id == current_user.college_id).order_by(VirtualLabItem.name, LabExercise.position)).all()
    counts = {}
    for ex_id, passed, n in db.execute(select(LabExerciseResult.exercise_id, LabExerciseResult.passed, func.count(LabExerciseResult.id))
                                       .where(LabExerciseResult.student_id.in_(list(students) or ["_"]))
                                       .group_by(LabExerciseResult.exercise_id, LabExerciseResult.passed)).all():
        counts.setdefault(ex_id, {"passed": 0, "tried": 0})
        counts[ex_id]["tried"] += n
        if passed:
            counts[ex_id]["passed"] += n
    return {"students": len(students), "exercises": [
        {"id": e.id, "lab": lab, "title": e.title_en, "passed": counts.get(e.id, {}).get("passed", 0),
         "tried": counts.get(e.id, {}).get("tried", 0)} for e, lab in exs]}


# ------------------------------------------------------------------ S13: metering job

@router.post("/admin/jobs/labs/meter")
def run_meter(current_user: TokenPayload = Depends(require_role(["college_admin", "super_admin"])), db: Session = Depends(get_db)):
    from services.lab_metering import meter
    out = meter(db)
    db.commit()
    return out


# ------------------------------------------------------------------ S13: spectate links on the class page

class SpectateIn(BaseModel):
    url: str = Field(min_length=10, max_length=512)
    label: Optional[str] = Field(default=None, max_length=128)


def spectate_allowed(url: str) -> bool:
    from urllib.parse import urlparse
    from core.config import settings
    u = urlparse(url)
    hosts = {h.strip().lower() for h in (settings.SPECTATE_ALLOWED_HOSTS or "").split(",") if h.strip()}
    for base in (settings.JUPYTERHUB_PUBLIC_URL, settings.JUPYTERHUB_URL):
        if base:
            hosts.add((urlparse(base).hostname or "").lower())
    host = (u.hostname or "").lower()
    if settings.ENVIRONMENT.lower() != "production" and host in ("localhost", "127.0.0.1"):
        return u.scheme in ("http", "https")
    return u.scheme == "https" and host in hosts


@router.put("/trainer/sessions/{session_id}/spectate")
def set_spectate(session_id: str, req: SpectateIn, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    """Post a read-only spectate link (e.g. a JupyterHub share of the trainer's lab) for students in this class."""
    from urllib.parse import urlparse
    from routers.live import _session_for_user
    s = _session_for_user(session_id, current_user, db)
    url = req.url.strip()
    if not spectate_allowed(url):
        raise HTTPException(status_code=422, detail="Use an https link on the lab hub (or a host your admin allowed)")
    s.spectate_url, s.spectate_label = url, (req.label or "").strip() or None
    record_audit(db, current_user, "class.spectate_posted", "session", s.id, {"host": urlparse(url).hostname})
    db.commit()
    return {"session_id": s.id, "spectate_url": s.spectate_url, "spectate_label": s.spectate_label}


@router.delete("/trainer/sessions/{session_id}/spectate")
def clear_spectate(session_id: str, current_user: TokenPayload = Depends(require_role(["trainer"])), db: Session = Depends(get_db)):
    from routers.live import _session_for_user
    s = _session_for_user(session_id, current_user, db)
    s.spectate_url = s.spectate_label = None
    db.commit()
    return {"session_id": s.id, "spectate_url": None}
