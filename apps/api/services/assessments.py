"""Screen 22 (Assessments): what students may see on 23 and 24 (link L13), and the
IREP bank in the platform tenant that trainers import from (link L37)."""
from typing import Optional, Union

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import TokenPayload, normalize_role
from models.schema import CodingProblem, PracticeTest, Student

Item = Union[CodingProblem, PracticeTest]


def visible_to(item: Item, student: Optional[Student]) -> bool:
    """Published, and either for every batch or for the student's batch."""
    if item.status != "published":
        return False
    return not item.batch_ids or (student is not None and student.batch_id in item.batch_ids)


def caller_student(db: Session, user: TokenPayload) -> Optional[Student]:
    if normalize_role(user.role) != "student":
        return None
    return db.execute(select(Student).where(Student.user_id == user.sub, Student.college_id == user.college_id)).scalar_one_or_none()


def get_for_caller(db: Session, model, item_id: str, user: TokenPayload) -> Item:
    """Tenant-scoped lookup. Students also need the item published to their batch;
    trainers and college staff preview drafts of their own college. Else 404."""
    item = db.execute(select(model).where(model.id == item_id, model.college_id == user.college_id)).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    if normalize_role(user.role) == "student" and not visible_to(item, caller_student(db, user)):
        raise HTTPException(status_code=404, detail="Not found")
    return item
