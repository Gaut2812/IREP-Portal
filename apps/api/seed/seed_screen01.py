"""Screen 01 seed: reset sign-in state so demos and test runs start clean
(no lockouts, no failed-login counters, no OTP rate-limit history)."""
from sqlalchemy import update, delete

from models.schema import User, OtpAttempt


def seed_screen01(db, college_id: str = "col_demo_001") -> None:
    db.execute(update(User).where(User.college_id == college_id).values(failed_logins=0, locked_until=None))
    db.execute(delete(OtpAttempt))
    db.flush()
