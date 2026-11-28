"""Remove stored files after the database change that dropped them has committed (rule 3: no external call
inside the request transaction; S3 is external). Idempotent: deleting a missing key is a no-op."""
from typing import Optional

from sqlalchemy.orm import Session

from models.schema import OutboxEvent
from services.outbox import emit, handler
from services.storage import get_storage


def delete_file_later(db: Session, key: Optional[str], *, college_id: str, entity_type: str, entity_id: str) -> None:
    """Queue the removal of a stored file in the caller's transaction."""
    if key:
        emit(db, "storage.delete", {"key": key}, college_id=college_id, entity_type=entity_type, entity_id=entity_id)


@handler("storage.delete")
def _delete_file(db: Session, ev: OutboxEvent) -> None:
    key = (ev.payload or {}).get("key")
    if key:
        get_storage().delete(key)
