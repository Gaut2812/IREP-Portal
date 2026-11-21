"""Link a trainer to their licensed Teams account; their classes are then organised from it
(otherwise TEAMS_DEFAULT_ORGANIZER is used). Idempotent.

    docker compose run --rm api python ops/set_teams_upn.py --trainer-email sid@college.edu --upn sid@college.onmicrosoft.com
    docker compose run --rm api python ops/set_teams_upn.py --trainer-email sid@college.edu --clear
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.database import SessionLocal
from models.schema import Trainer, User


def set_upn(db, trainer_email: str, upn) -> Trainer:
    row = db.execute(select(Trainer).join(User, User.id == Trainer.user_id)
                     .where(User.email == trainer_email.strip().lower(), User.role == "trainer")).scalar_one_or_none()
    if row is None:
        raise SystemExit(f"no trainer with email {trainer_email}")
    row.teams_upn = upn.strip().lower() if upn else None
    db.commit()
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trainer-email", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--upn")
    g.add_argument("--clear", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        t = set_upn(db, args.trainer_email, None if args.clear else args.upn)
        print(f"{args.trainer_email}: teams_upn = {t.teams_upn or '(default organizer)'}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
