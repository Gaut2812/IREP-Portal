"""Keyword filter shared by Q&A, discussion groups and messages (P16).
Extend BLOCKED_TERMS per college later via the content library."""
import re

BLOCKED_TERMS = {
    "idiot", "stupid", "shut up", "dumb", "loser",
    "answer key", "leaked paper", "test answers",
}


def contains_blocked(text: str) -> bool:
    lowered = re.sub(r"\s+", " ", (text or "").lower())
    return any(term in lowered for term in BLOCKED_TERMS)
