"""Moderation for Q&A, discussion groups and live chat (P16; screen 34, S10).

`check_text` decides what happens to a post:
- block (refused, with a reason the sender sees): the platform's insult and test-leak
  terms, phone numbers and emails (no private contact between students), invite links
  to off-platform chats, and a college's own `block` terms;
- flag (posted, and a system report goes to the group's moderators: link L18): a
  college's own `flag` terms;
- None: fine.
"""
import re
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

BLOCKED_TERMS = {
    "idiot", "stupid", "shut up", "dumb", "loser",
    "answer key", "leaked paper", "test answers",
}
PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
OFF_PLATFORM = re.compile(r"(chat\.whatsapp\.com|wa\.me/|t\.me/|telegram\.me/|discord\.gg/|discord\.com/invite)", re.I)

REASONS = {
    "insult": "Please rephrase: the message breaks the group rules (no insults, no graded-test answers).",
    "contact": "Please don't share phone numbers or email addresses in groups. Talk to your trainer if you need help.",
    "off_platform": "Invite links to other chat apps are not allowed. Keep the discussion here, where trainers can help.",
    "college": "Please rephrase: your college does not allow that word in groups.",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def contains_blocked(text: str) -> bool:
    lowered = _norm(text)
    return any(term in lowered for term in BLOCKED_TERMS)


def check_text(db: Optional[Session], college_id: Optional[str], text: str) -> Optional[Tuple[str, str]]:
    """Return ("block", reason_key), ("flag", term) or None."""
    lowered = _norm(text)
    if any(term in lowered for term in BLOCKED_TERMS):
        return "block", "insult"
    if PHONE.search(text or "") or EMAIL.search(text or ""):
        return "block", "contact"
    if OFF_PLATFORM.search(text or ""):
        return "block", "off_platform"
    if db is not None and college_id:
        from models.schema import ModerationTerm
        terms = db.execute(select(ModerationTerm.term, ModerationTerm.action).where(ModerationTerm.college_id == college_id)).all()
        for term, action in sorted(terms, key=lambda t: t[1] != "block"):           # block wins over flag
            if re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", lowered):
                return ("block", "college") if action == "block" else ("flag", term)
    return None
