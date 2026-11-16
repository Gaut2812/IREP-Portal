"""Tenant and identity resolution helpers shared by every router.

Every query in the API must be scoped by the college_id carried in the
verified token. These helpers resolve the student / parent / trainer rows
for the current user inside that tenant and never trust ids from the client
unless they are checked against the tenant.
"""
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import TokenPayload
from models.schema import Student, Trainer, ParentStudent, User, BatchTrainer


def get_student_for_user(current_user: TokenPayload, db: Session) -> Student:
    """Resolve the Student profile of the signed-in user inside their tenant."""
    student = db.execute(
        select(Student).filter_by(user_id=current_user.sub, college_id=current_user.college_id)
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found for this user")
    return student


def get_trainer_for_user(current_user: TokenPayload, db: Session) -> Trainer:
    trainer = db.execute(
        select(Trainer).filter_by(user_id=current_user.sub, college_id=current_user.college_id)
    ).scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer profile not found for this user")
    return trainer


def get_trainer_batch_ids(trainer: Trainer, db: Session) -> List[str]:
    rows = db.execute(
        select(BatchTrainer.batch_id).filter_by(trainer_id=trainer.id, college_id=trainer.college_id)
    ).scalars().all()
    return list(rows)


def get_parent_children(current_user: TokenPayload, db: Session) -> List[Student]:
    """All students linked to the signed-in parent (siblings included)."""
    links = db.execute(
        select(ParentStudent.student_id).filter_by(
            parent_user_id=current_user.sub, college_id=current_user.college_id
        )
    ).scalars().all()
    if not links:
        return []
    return list(db.execute(
        select(Student).where(Student.id.in_(links), Student.college_id == current_user.college_id)
    ).scalars().all())


def get_child_for_parent(current_user: TokenPayload, db: Session, child_id: Optional[str] = None) -> Student:
    """Resolve one child of the parent. A child_id that is not linked to this
    parent (or belongs to another college) is reported as not found, never as
    forbidden, so ids cannot be probed."""
    children = get_parent_children(current_user, db)
    if not children:
        raise HTTPException(status_code=404, detail="No student is linked to this parent account")
    if child_id is None:
        return children[0]
    for c in children:
        if c.id == child_id:
            return c
    raise HTTPException(status_code=404, detail="Child not found for this parent")


def get_user_name(db: Session, user_id: str, default: str = "") -> str:
    user = db.execute(select(User).filter_by(id=user_id)).scalar_one_or_none()
    return user.name if user and user.name else default
