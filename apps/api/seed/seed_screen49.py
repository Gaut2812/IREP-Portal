"""Screens 21, 16 and 49 seed hygiene. Re-seeding restores demo state:

- monthly cards other than the seeded September and October ones (screen 15
  seed) are removed, so screen 21 starts the current month with no drafts;
- support tickets, their messages and support or report notifications are removed;
- Study Buddy chats, AI-call usage and moderation terms in the demo college are removed;
- certificates added by tests are removed and Priya's scheduled AWS exam (voucher) is reset."""
from sqlalchemy import and_, delete, not_, or_

import re

from sqlalchemy import select

from models.schema import Certificate, ModerationTerm, MonthlyCard, Notification, StudyBuddyMessage, SupportMessage, SupportTicket, UsageLedger

SEEDED_MONTHS = ((2026, 9), (2026, 10))


def seed_screen49(db, college_id: str = "col_demo_001") -> None:
    keep = or_(*[and_(MonthlyCard.year == y, MonthlyCard.month == m) for y, m in SEEDED_MONTHS])
    db.execute(delete(MonthlyCard).where(MonthlyCard.college_id == college_id, not_(keep)))
    # the seeded cards go back to their demo state (September sent, October approved) if a test or demo moved them
    for card in db.execute(select(MonthlyCard).where(MonthlyCard.college_id == college_id, keep)).scalars():
        card.status = "sent" if card.month == 9 else "approved"
        card.approved_by = card.approved_by or "usr_arun_01"
    db.execute(delete(SupportMessage))
    db.execute(delete(SupportTicket))
    db.execute(delete(Notification).where(Notification.kind.in_(["support", "report"])))
    # S10 hygiene: Study Buddy chats and AI-call usage from tests or demos, and test moderation terms
    db.execute(delete(StudyBuddyMessage).where(StudyBuddyMessage.college_id == college_id))
    db.execute(delete(UsageLedger).where(UsageLedger.college_id == college_id, UsageLedger.kind == "ai_calls"))
    db.execute(delete(ModerationTerm).where(ModerationTerm.college_id == college_id))
    # S11 hygiene: certificates added by tests or demos go; Priya's scheduled AWS exam (with its voucher) is reset
    generated = [c for c in db.execute(select(Certificate.id).where(Certificate.college_id == college_id)).scalars()
                 if re.match(r"^cert_[0-9a-f]{14}$", c)]
    if generated:
        db.execute(delete(Certificate).where(Certificate.id.in_(generated)))
    aws = db.get(Certificate, "cert_priya_aws_sched")
    if aws is not None:
        aws.status, aws.voucher_code, aws.issued_on, aws.verify_code = "scheduled", "VCH-AWS-2026-0001", None, None
        aws.proof_key = aws.proof_filename = aws.proof_submitted_at = aws.credential_id = None
        aws.decided_by = aws.decided_at = aws.decision_note = None
    db.flush()
