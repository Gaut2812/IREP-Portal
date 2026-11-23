"""Screen 39 · Placement readiness (college): drill-down by branch, batch and student.

L34: the one readiness score and band from the readiness engine (students.readiness_score/band, kept
current by services/readiness; the monthly change and the components come from the latest snapshot).
L35 and 5.4: aggregates and bands. Per student only score, band and monthly change; never trainer
notes or chats. Spec: docs/screens/37-38-39-interviews-drives-readiness.md
"""
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from models.schema import Batch, Branch, ReadinessSnapshot, Student, User
from services.readiness import COMPONENT_LABELS

router = APIRouter(prefix="/college/readiness", tags=["Screen 39 · Placement readiness"])
COLLEGE = require_role(["college_admin", "placement_officer"])
BANDS = ("Placement Ready", "Nearly Ready", "Needs Support")
BAND_KEY = {"Placement Ready": "ready", "Nearly Ready": "nearly", "Needs Support": "support"}
BAND_TA = {"Placement Ready": "வேலைக்குத் தயார்", "Nearly Ready": "கிட்டத்தட்ட தயார்", "Needs Support": "உதவி தேவை"}


def _latest_snapshots(db: Session, college_id: str, student_ids: List[str]) -> Dict[str, ReadinessSnapshot]:
    out: Dict[str, ReadinessSnapshot] = {}
    if not student_ids:
        return out
    for s in db.execute(select(ReadinessSnapshot).where(ReadinessSnapshot.college_id == college_id,
                                                        ReadinessSnapshot.student_id.in_(student_ids))
                        .order_by(ReadinessSnapshot.snapshot_date, ReadinessSnapshot.created_at)).scalars():
        out[s.student_id] = s                                  # ordered: the latest wins
    return out


def _aggregate(rows: list, snaps: Dict[str, ReadinessSnapshot]) -> dict:
    n = len(rows)
    bands = {k: 0 for k in BAND_KEY.values()}
    for st, _ in rows:
        bands[BAND_KEY.get(st.readiness_band, "support")] += 1
    deltas = [snaps[st.id].delta for st, _ in rows if st.id in snaps]
    return {"students": n, "avg_score": round(sum(st.readiness_score for st, _ in rows) / n, 1) if n else None,
            "avg_delta": round(sum(deltas) / len(deltas), 1) if deltas else None, "bands": bands}


def _components(rows: list, snaps: Dict[str, ReadinessSnapshot], lang: str) -> list:
    acc: Dict[str, list] = defaultdict(list)
    for st, _ in rows:
        for c in (snaps[st.id].breakdown if st.id in snaps else []) or []:
            if isinstance(c, dict) and c.get("key") is not None and c.get("value") is not None:
                acc[c["key"]].append(c["value"])
    return [{"key": k, "label": COMPONENT_LABELS.get(k, {}).get("ta" if lang == "ta" else "en", k),
             "avg": round(sum(v) / len(v), 1)} for k, v in acc.items()]


@router.get("")
def readiness(branch_id: Optional[str] = None, batch_id: Optional[str] = None,
              band: Optional[str] = Query(None, pattern="^(ready|nearly|support)$"), lang: str = "en",
              current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid = current_user.college_id
    branch = batch = None
    if batch_id:
        batch = db.execute(select(Batch).where(Batch.id == batch_id, Batch.college_id == cid)).scalar_one_or_none()
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        branch_id = branch_id or batch.branch_id
    if branch_id:
        branch = db.execute(select(Branch).where(Branch.id == branch_id, Branch.college_id == cid)).scalar_one_or_none()
        if branch is None or (batch is not None and batch.branch_id != branch.id):
            raise HTTPException(status_code=404, detail="Branch not found")

    q = select(Student, User.name).join(User, User.id == Student.user_id).where(Student.college_id == cid, User.is_active.is_(True))
    if branch:
        q = q.where(Student.branch_id == branch.id)
    if batch:
        q = q.where(Student.batch_id == batch.id)
    rows = db.execute(q.order_by(Student.readiness_score.desc(), Student.register_no)).all()
    snaps = _latest_snapshots(db, cid, [st.id for st, _ in rows])

    def band_label(b: str) -> str:
        return BAND_TA.get(b, b) if lang == "ta" else b

    out = {"scope": {"branch": {"id": branch.id, "name": branch.name} if branch else None,
                     "batch": {"id": batch.id, "name": batch.name} if batch else None},
           "summary": _aggregate(rows, snaps), "components": _components(rows, snaps, lang),
           "band_labels": {BAND_KEY[b]: band_label(b) for b in BANDS}}
    if batch:                                         # students of one batch: score, band, change only
        picked = [(st, name) for st, name in rows if not band or BAND_KEY.get(st.readiness_band) == band]
        out["students"] = [{"id": st.id, "name": name, "register_no": st.register_no, "score": st.readiness_score,
                            "band": BAND_KEY.get(st.readiness_band, "support"), "band_label": band_label(st.readiness_band),
                            "delta": snaps[st.id].delta if st.id in snaps else None} for st, name in picked]
        return out
    if branch:                                        # batches of one branch
        groups = db.execute(select(Batch).where(Batch.branch_id == branch.id, Batch.college_id == cid).order_by(Batch.name)).scalars().all()
        key = "batch_id"
    else:                                             # branches of the college
        groups = db.execute(select(Branch).where(Branch.college_id == cid).order_by(Branch.name)).scalars().all()
        key = "branch_id"
    out["groups"] = []
    for g in groups:
        members = [(st, n) for st, n in rows if getattr(st, key) == g.id]
        out["groups"].append({"id": g.id, "name": g.name, "level": "batch" if key == "batch_id" else "branch",
                              **_aggregate(members, snaps)})
    return out
