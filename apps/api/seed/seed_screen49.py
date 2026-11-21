"""Screens 21, 16 and 49 seed hygiene. Re-seeding restores demo state:

- monthly cards other than the seeded September and October ones (screen 15
  seed) are removed, so screen 21 starts the current month with no drafts;
- support tickets, their messages and support or report notifications are removed;
- Study Buddy chats, AI-call usage and moderation terms in the demo college are removed."""
from sqlalchemy import and_, delete, not_, or_

from models.schema import ModerationTerm, MonthlyCard, Notification, StudyBuddyMessage, SupportMessage, SupportTicket, UsageLedger

SEEDED_MONTHS = ((2026, 9), (2026, 10))


def seed_screen49(db, college_id: str = "col_demo_001") -> None:
    keep = or_(*[and_(MonthlyCard.year == y, MonthlyCard.month == m) for y, m in SEEDED_MONTHS])
    db.execute(delete(MonthlyCard).where(MonthlyCard.college_id == college_id, not_(keep)))
    db.execute(delete(SupportMessage))
    db.execute(delete(SupportTicket))
    db.execute(delete(Notification).where(Notification.kind.in_(["support", "report"])))
    # S10 hygiene: Study Buddy chats and AI-call usage from tests or demos, and test moderation terms
    db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.college_id == college_id))
    db.execute(delete(UsageLedger).where(UsageLedger.college_id == college_id, UsageLedger.kind == "ai_calls"))
    db.execute(delete(ModerationTerm).where(ModerationTerm.college_id == college_id))
    db.flush()
