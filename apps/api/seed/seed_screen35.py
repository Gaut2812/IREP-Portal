"""Screen 35 seed: Arun's parent/college threads with dated messages and
unread state (Lakshmi 2, Kavitha 1), two reported group messages for the
moderation queue, and a clean broadcast history. Re-seeding restores it."""
import datetime

from sqlalchemy import select, delete

from models.schema import (
    TrainerDirectThread, DirectMessage, GroupMessage, MessageReport, Broadcast, Notification, User,
)

THREADS = {
    "th_ramesh": ("usr_ramesh_01", "std_priya_01"),
    "th_lakshmi": ("usr_lakshmi_01", "std_cse_5_001_7868"),
    "th_kavitha": ("usr_kavitha_01", None),
    "th_placement": (None, None),
}
R04_EN = "Vanakkam sir, Priya's mock interview feedback received. Nandri."
R04_TA = "வணக்கம் சார், பிரியாவின் மாதிரி நேர்காணல் கருத்து கிடைத்தது. நன்றி."


def _utc(local: datetime.datetime) -> datetime.datetime:
    return local - (datetime.datetime.now() - datetime.datetime.utcnow())


def seed_screen35(db, college_id: str = "col_demo_001") -> None:
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    base = now.replace(hour=10, minute=45) if now.hour >= 11 else now - datetime.timedelta(minutes=5)
    yesterday = (now - datetime.timedelta(days=1)).replace(hour=18, minute=10)
    users = {u.id: u for u in db.execute(select(User).where(User.college_id == college_id)).scalars().all()}

    for tid, (contact, student) in THREADS.items():
        t = db.execute(select(TrainerDirectThread).filter_by(id=tid)).scalar_one_or_none()
        if t:
            t.contact_user_id, t.student_id, t.unread_badge = contact, student, 0

    # (id, thread, sender user or None, incoming, text_en, text_ta, at, read)
    rows = [
        ("dm_01", "th_ramesh", "usr_ramesh_01", True, None, None, base - datetime.timedelta(minutes=15), True),
        ("dm_02", "th_ramesh", "usr_arun_01", False, None, None, base - datetime.timedelta(minutes=7), True),
        ("dm_03", "th_ramesh", "usr_ramesh_01", True, None, None, base - datetime.timedelta(minutes=3), True),
        ("dm_seed_r04", "th_ramesh", "usr_ramesh_01", True, R04_EN, R04_TA, base, True),
        ("dm_seed_l01", "th_lakshmi", "usr_arun_01", False, "Karthik attended every session this week and his DSA streak is 9 days.", None, yesterday - datetime.timedelta(hours=3), True),
        ("dm_seed_l02", "th_lakshmi", "usr_lakshmi_01", True, "Thank you sir, that is good to hear.", None, yesterday, False),
        ("dm_seed_l03", "th_lakshmi", "usr_lakshmi_01", True, "Will Karthik have extra coaching this Saturday?", None, yesterday + datetime.timedelta(minutes=2), False),
        ("dm_seed_k01", "th_kavitha", "usr_kavitha_01", True, "MoU progress report due for the governing council review.", None, yesterday - datetime.timedelta(hours=6), False),
        ("dm_seed_p01", "th_placement", None, True, "Shortlisted candidates for Mock Drive 1 ready.", None, now - datetime.timedelta(days=10), True),
    ]
    seed_ids = [r[0] for r in rows]
    stray_threads = db.execute(select(TrainerDirectThread.id).where(TrainerDirectThread.college_id == college_id, TrainerDirectThread.id.not_in(list(THREADS)))).scalars().all()
    db.execute(delete(DirectMessage).where(DirectMessage.thread_id.in_(list(THREADS) + list(stray_threads)), DirectMessage.id.not_in(seed_ids)))
    db.execute(delete(TrainerDirectThread).where(TrainerDirectThread.id.in_(stray_threads or ["_"])))
    for mid, tid, sender, incoming, en, ta, at, read in rows:
        m = db.execute(select(DirectMessage).filter_by(id=mid)).scalar_one_or_none()
        if not m:
            if en is None:
                continue
            m = DirectMessage(id=mid, college_id=college_id, thread_id=tid, text_en=en, text_ta=ta)
            db.add(m)
        u = users.get(sender) if sender else None
        m.is_incoming, m.sender_user_id = incoming, sender
        m.sender_name = u.name if u else "Placement Cell"
        m.original_lang = "en"
        m.created_at = m.updated_at = _utc(at)
        m.timestamp_str = at.strftime("%I:%M %p").lstrip("0")
        m.read_at = _utc(at) if read else None
    db.flush()

    # reported group messages feeding the moderation queue
    reported = [
        ("msg_seed_r01", "grp_batch", "Karthik S", "Anyone want the external test answers? bit.ly/ext-answers", "rep_seed_01", "Sneha N", "External test answers leak link", 120),
        ("msg_seed_r02", "grp_gd", "Rahul D", "That point was stupid, nobody cares what you think.", "rep_seed_02", "Ananya P", "Inappropriate comment", 300),
    ]
    by_name = {u.name: u for u in users.values()}
    for mid, gid, author, text, rid, reporter, reason, mins in reported:
        a, r = by_name.get(author), by_name.get(reporter)
        if not a or not r:
            continue
        msg = db.execute(select(GroupMessage).filter_by(id=mid)).scalar_one_or_none()
        if not msg:
            msg = GroupMessage(id=mid, college_id=college_id, group_id=gid, sender_user_id=a.id, sender_name=a.name, sender_role="Student",
                               sender_initials=a.avatar_initials, message_text=text, reactions_count=0)
            db.add(msg)
        at = base - datetime.timedelta(minutes=mins)
        msg.created_at = msg.updated_at = _utc(at)
        msg.timestamp_str = at.strftime("%I:%M %p").lstrip("0")
        msg.is_removed, msg.removed_reason = False, None
        db.flush()
        rep = db.execute(select(MessageReport).filter_by(id=rid)).scalar_one_or_none()
        if not rep:
            rep = MessageReport(id=rid, college_id=college_id, message_id=mid, group_id=gid, reporter_user_id=r.id, reason=reason)
            db.add(rep)
        rep.status = "open"
        rep.created_at = rep.updated_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=15 if rid.endswith("1") else 60)

    db.execute(delete(Broadcast).where(Broadcast.college_id == college_id))
    db.execute(delete(Notification).where(Notification.kind == "broadcast", Notification.college_id == college_id))
    db.flush()
