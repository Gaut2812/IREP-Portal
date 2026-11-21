"""Clash detection for screens 05/06 (docs/screens/05-06-schedule-and-timetable.md).

A proposed [start, end) clashes with an existing, non-cancelled session when
they overlap and share the batch, a trainer, or the room. Clashes are a warning
for the college, not a hard block.
"""
import datetime
from typing import Iterable, List, Optional, Set

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models.schema import Batch, BatchTrainer, SessionItem

CANCELLED = "Cancelled"


def trainer_batch_ids(db: Session, trainer_ids: Iterable[str]) -> Set[str]:
    ids = [t for t in trainer_ids if t]
    if not ids:
        return set()
    return set(db.execute(select(BatchTrainer.batch_id).where(BatchTrainer.trainer_id.in_(ids))).scalars())


def find_clashes(db: Session, *, college_id: str, batch_id: str, start: datetime.datetime, end: datetime.datetime,
                 trainer_ids: Iterable[str] = (), room: Optional[str] = None, exclude_session_id: Optional[str] = None) -> List[dict]:
    trainer_ids = [t for t in trainer_ids if t]
    q = select(SessionItem).where(
        SessionItem.college_id == college_id,
        SessionItem.status != CANCELLED,
        SessionItem.scheduled_start < end,
        SessionItem.scheduled_end > start,
    )
    if exclude_session_id:
        q = q.where(SessionItem.id != exclude_session_id)
    their_batches = trainer_batch_ids(db, trainer_ids)
    conds = [SessionItem.batch_id == batch_id]
    if their_batches:
        conds.append(SessionItem.batch_id.in_(their_batches))
    if trainer_ids:
        conds.append(SessionItem.substitute_trainer_id.in_(trainer_ids))
    if room and room.strip():
        conds.append(func.lower(SessionItem.room) == room.strip().lower())
    rows = db.execute(q.where(or_(*conds))).scalars().all()
    names = dict(db.execute(select(Batch.id, Batch.short_name).where(Batch.id.in_({r.batch_id for r in rows if r.batch_id} or {"_"}))).all())
    out = []
    for r in rows:
        kinds = []
        if r.batch_id == batch_id:
            kinds.append("batch")
        if (r.batch_id in their_batches and r.batch_id != batch_id) or (r.substitute_trainer_id and r.substitute_trainer_id in trainer_ids):
            kinds.append("trainer")
        if room and r.room and r.room.strip().lower() == room.strip().lower():
            kinds.append("room")
        for k in kinds:
            out.append({"kind": k, "session_id": r.id, "title": r.title, "batch": names.get(r.batch_id),
                        "start": r.scheduled_start.isoformat(), "end": r.scheduled_end.isoformat(), "room": r.room})
    return out
