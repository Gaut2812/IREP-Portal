"""Screen 01 seed: reset sign-in state so demos and test runs start clean
(no lockouts, no failed-login counters, no OTP rate-limit history)."""
from sqlalchemy import update, delete

from sqlalchemy import select

from models.schema import User, OtpAttempt, Notification


def seed_screen01(db, college_id: str = "col_demo_001") -> None:
    db.execute(update(User).where(User.college_id == college_id).values(failed_logins=0, locked_until=None))
    db.execute(delete(OtpAttempt))
    # demo language preferences (toggling the language while signed in saves it)
    db.execute(update(User).where(User.college_id == college_id).values(language_pref="en"))
    db.execute(update(User).where(User.id == "usr_ramesh_01").values(language_pref="ta"))
    # notification inboxes: drop test notices and repeats left by test/demo runs,
    # keeping the newest copy of each (user, title)
    db.execute(delete(Notification).where(Notification.college_id == college_id, Notification.title_en == "Test notice"))
    newest = {}
    for n in db.execute(select(Notification).where(Notification.college_id == college_id).order_by(Notification.created_at.desc())).scalars().all():
        key = (n.user_id, n.title_en, n.channel)
        if key in newest:
            db.delete(n)
        else:
            newest[key] = n.id
    for n in db.execute(select(Notification).where(Notification.college_id == college_id, Notification.link.in_(["/trainer/interviews", "/trainer/approvals"]))).scalars().all():
        n.link = "/trainer#lab-approvals" if n.link == "/trainer/approvals" else "/trainer"
    db.flush()
