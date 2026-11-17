"""Job triggers that stand in for the Celery beat schedule until the worker exists."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, require_role, TokenPayload
from services.readiness import run_readiness_job
from services.at_risk import run_rules
from services.audit import record_audit

router = APIRouter(prefix="/admin/jobs", tags=["Admin Jobs"])


@router.post("/readiness")
def trigger_readiness_job(
    current_user: TokenPayload = Depends(require_role(["college_admin", "trainer", "super_admin"])),
    db: Session = Depends(get_db),
):
    count = run_readiness_job(db, current_user.college_id)
    record_audit(db, current_user, "job.readiness.run", "college", current_user.college_id, {"students": count})
    db.commit()
    return {"success": True, "students_recomputed": count}


@router.post("/at-risk")
def trigger_at_risk_rules(
    current_user: TokenPayload = Depends(require_role(["college_admin", "trainer", "super_admin"])),
    db: Session = Depends(get_db),
):
    created = run_rules(db, current_user.college_id)
    record_audit(db, current_user, "job.at_risk.run", "college", current_user.college_id, {"flags_created": created})
    db.commit()
    return {"success": True, "flags_created": created}
