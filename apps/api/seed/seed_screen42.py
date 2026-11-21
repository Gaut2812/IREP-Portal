"""Screens 42, 17 and 14 seed hygiene. Re-seeding restores demo state:

- events created through screen 42 (they have `created_by`), their RSVPs,
  placement posts and event notifications are removed; seeded events stay;
- the demo L31 flag (Karthik S, Arun's CSE-A batch, parent Lakshmi) is open
  again with no actions and no parent alert, so a trainer can make the call.
Thread messages from a parent call are removed by the screen 35 seed."""
import datetime

from sqlalchemy import delete, select

from models.schema import AtRiskFlag, Event, FlagAction, GroupMessage, Notification, OutboxEvent, Rsvp

L31_FLAG = "flag_seed_l31"
L31_STUDENT = "std_cse_5_001_d90c"
L31_BATCH = "bat_cse_s5_csea"


def seed_screen42(db, college_id: str = "col_demo_001") -> None:
    made = list(db.execute(select(Event.id).where(Event.college_id == college_id, Event.created_by.is_not(None))).scalars())
    db.execute(delete(Rsvp).where(Rsvp.event_id.in_(made or ["_"])))
    db.execute(delete(Event).where(Event.id.in_(made or ["_"])))
    db.execute(delete(GroupMessage).where(GroupMessage.college_id == college_id, GroupMessage.id.like("gm_evt_%")))
    db.execute(delete(Notification).where(Notification.college_id == college_id, Notification.kind == "event"))

    db.execute(delete(FlagAction).where(FlagAction.flag_id == L31_FLAG))
    db.execute(delete(OutboxEvent).where(OutboxEvent.entity_id == L31_FLAG, OutboxEvent.status == "pending"))
    db.execute(delete(Notification).where(Notification.college_id == college_id, Notification.kind == "alert",
                                          Notification.title_en == "Support plan for Karthik S", Notification.link == "/parent/messages"))
    flag = db.get(AtRiskFlag, L31_FLAG)
    if flag is None:
        flag = AtRiskFlag(id=L31_FLAG, college_id=college_id, student_id=L31_STUDENT, batch_id=L31_BATCH)
        db.add(flag)
    flag.reason_key, flag.reason_text, flag.severity, flag.suggested_action = "missed_sessions", "4 sessions missed", "high", "parent_call"
    flag.status, flag.parent_notified, flag.parent_notified_at = "open", False, None
    flag.resolution_note = flag.resolved_by = flag.resolved_at = None
    flag.flagged_on = datetime.date.today() - datetime.timedelta(days=1)
    db.flush()
