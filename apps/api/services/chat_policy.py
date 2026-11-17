"""Who-can-message-whom policy (Screen 34/35, interconnect map §5.1).

Enforced at the API: a forbidden pair gets 403 whatever the UI shows.
"""
from typing import Optional, Tuple

from core.security import normalize_role

# (role a, role b) -> allowed one-to-one
ONE_TO_ONE = {
    frozenset(["trainer", "parent"]): True,
    frozenset(["trainer", "college_admin"]): True,
    frozenset(["student"]): False,                  # student <-> student
    frozenset(["trainer", "student"]): False,       # use groups and review comments (recommended "no")
    frozenset(["parent", "college_admin"]): False,  # route through the trainer
    frozenset(["parent", "student"]): False,
    frozenset(["parent"]): False,
}

MATRIX = [
    {"key": "student_student", "label_en": "Student ⇄ Student 1-1", "label_ta": "மாணவர் ⇄ மாணவர் 1-1", "status_en": "Off", "status_ta": "இல்லை", "color": "red"},
    {"key": "student_groups", "label_en": "Student groups", "label_ta": "மாணவர் குழுக்கள்", "status_en": "Moderated", "status_ta": "கண்காணிக்கப்படுகிறது", "color": "green"},
    {"key": "trainer_parent", "label_en": "Trainer ⇄ Parent", "label_ta": "பயிற்சியாளர் ⇄ பெற்றோர்", "status_en": "1-1", "status_ta": "1-1", "color": "green"},
    {"key": "trainer_college", "label_en": "Trainer ⇄ College", "label_ta": "பயிற்சியாளர் ⇄ கல்லூரி", "status_en": "1-1", "status_ta": "1-1", "color": "green"},
    {"key": "announcements", "label_en": "Announcements", "label_ta": "அறிவிப்புகள்", "status_en": "Broadcast", "status_ta": "ஒளிபரப்பு", "color": "blue"},
]


def can_message(role_a: str, role_b: str) -> Tuple[bool, Optional[str]]:
    a, b = normalize_role(role_a), normalize_role(role_b)
    allowed = ONE_TO_ONE.get(frozenset([a, b]), False)
    if allowed:
        return True, None
    if a == b == "student":
        return False, "One-to-one messaging between students is turned off. Use your moderated groups."
    if {a, b} == {"trainer", "student"}:
        return False, "Students and trainers talk in moderated groups and code reviews, not private chats."
    if {a, b} == {"parent", "college_admin"}:
        return False, "Parents reach the college through their child's trainer."
    return False, "This conversation is not allowed by the college messaging policy."
