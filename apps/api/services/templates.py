"""Notification templates from the content library (screen 46 -> 44, link L37).

render(db, key, fallback, **vars) returns {title_en, title_ta, body_en, body_ta}
from the template for `key`, filled with vars; when there is no template it
returns the caller's fallback text unchanged, so a missing template never
blocks a notification.
"""
import string
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.schema import NotificationTemplate


class _Safe(dict):
    def __missing__(self, key):            # leave unknown {placeholders} visible instead of failing
        return "{" + key + "}"


def _fill(text: Optional[str], values: Dict[str, object]) -> Optional[str]:
    if text is None:
        return None
    return string.Formatter().vformat(text, (), _Safe({k: v for k, v in values.items()}))


def render(db: Session, key: str, fallback: Dict[str, Optional[str]], **values) -> Dict[str, Optional[str]]:
    t = db.execute(select(NotificationTemplate).where(NotificationTemplate.key == key)).scalar_one_or_none()
    if t is None:
        return dict(fallback)
    return {"title_en": _fill(t.title_en, values), "title_ta": _fill(t.title_ta, values),
            "body_en": _fill(t.body_en, values), "body_ta": _fill(t.body_ta, values)}
