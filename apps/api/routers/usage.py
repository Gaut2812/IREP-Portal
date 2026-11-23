"""Screen 47 · Usage and billing (IREP staff), the quota half (S12): each college's use this month
against its MoU quotas (link L36), which 29, 25 and 08 enforce. Full billing is S16.
Spec: docs/screens/47-usage-quotas.md"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import PLATFORM_TENANT, TokenPayload, require_role
from models.schema import College
from services.quotas import all_colleges, college_usage

router = APIRouter(tags=["Usage and quotas"])
STAFF = require_role(["irep_admin"])
PERIOD = r"^\d{4}-(0[1-9]|1[0-2])$"


@router.get("/admin/usage")
def usage_all(period: Optional[str] = Query(None, pattern=PERIOD), current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    rows = all_colleges(db, period)
    levels = [u["level"] for r in rows for u in r["usage"].values()]
    return {"period": rows[0]["period"] if rows else period, "colleges": rows,
            "summary": {"colleges": len(rows), "warn": sum(1 for r in rows if any(u["level"] == "warn" for u in r["usage"].values())),
                        "over": sum(1 for r in rows if any(u["level"] == "over" for u in r["usage"].values())),
                        "metrics_over": levels.count("over")}}


@router.get("/admin/usage/{college_id}")
def usage_one(college_id: str, period: Optional[str] = Query(None, pattern=PERIOD), current_user: TokenPayload = Depends(STAFF),
              db: Session = Depends(get_db)):
    c = db.get(College, college_id)
    if c is None or c.id == PLATFORM_TENANT:
        raise HTTPException(status_code=404, detail="College not found")
    return {"college_id": c.id, "name": c.name, **college_usage(db, c.id, period)}


@router.get("/college/usage")
def usage_mine(period: Optional[str] = Query(None, pattern=PERIOD), current_user: TokenPayload = Depends(require_role(["college_admin"])),
               db: Session = Depends(get_db)):
    """The college's own totals against its MoU (aggregates only)."""
    return college_usage(db, current_user.college_id, period)
