"""Job triggers that stand in for the Celery beat schedule until the worker exists."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, require_role, TokenPayload
from services.readiness import run_nightly
from services.at_risk import run_rules
from services.audit import record_audit

router = APIRouter(prefix="/admin/jobs", tags=["Admin Jobs"])


@router.post("/readiness")
def trigger_readiness_job(
    current_user: TokenPayload = Depends(require_role(["college_admin", "trainer", "irep_admin"])),
    db: Session = Depends(get_db),
):
    out = run_nightly(db, current_user.college_id)
    record_audit(db, current_user, "job.readiness.run", "college", current_user.college_id, out)
    db.commit()
    return {"success": True, "students_recomputed": out["students"], **out}


@router.post("/at-risk")
def trigger_at_risk_rules(
    current_user: TokenPayload = Depends(require_role(["college_admin", "trainer", "irep_admin"])),
    db: Session = Depends(get_db),
):
    created = run_rules(db, current_user.college_id)
    record_audit(db, current_user, "job.at_risk.run", "college", current_user.college_id, {"flags_created": created})
    db.commit()
    return {"success": True, "flags_created": created}


@router.post("/labs/cull")
def trigger_lab_cull(
    current_user: TokenPayload = Depends(require_role(["college_admin", "trainer", "irep_admin"])),
    db: Session = Depends(get_db),
):
    from services.lab_orchestrator import cull
    stopped = cull(db, current_user.college_id)
    db.commit()
    return {"success": True, "stopped": stopped}


@router.post("/teams")
def trigger_teams_sync(
    current_user: TokenPayload = Depends(require_role(["college_admin", "irep_admin"])),
    db: Session = Depends(get_db),
):
    """Queue Teams meeting creation for upcoming sessions and attendance pulls
    for ended ones (the Celery beat runs the same for every college)."""
    from core.config import settings
    if settings.LIVE_CLASS_ADAPTER.lower() != "teams":
        return {"success": True, "skipped": "LIVE_CLASS_ADAPTER is not teams"}
    from services.teams import queue_due_work
    out = queue_due_work(db, college_id=current_user.college_id)
    db.commit()
    return {"success": True, **out}
