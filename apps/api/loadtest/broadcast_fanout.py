"""Broadcast fan-out benchmark (S14): Master Plan target "a 50,000-recipient broadcast within 15 minutes".

Measures how fast one worker delivers announcement chunks (services/broadcasts.deliver_chunk:
an in-app notification per recipient, SMS queued for parents) on the real demo cohort, inside a
transaction that is rolled back, then projects the time for --target recipients over --workers
parallel workers (the outbox dispatcher runs chunks independently).

    venv/Scripts/python loadtest/broadcast_fanout.py --target 50000 --workers 4

Run it against the database you will deploy on (PostgreSQL); SQLite numbers are a floor.
Exit code 1 when the projection misses --minutes.
"""
import argparse
import sys
import time

sys.path.insert(0, __file__.rsplit("loadtest", 1)[0])

from sqlalchemy import select  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from models.schema import ParentStudent, Student  # noqa: E402
from services import broadcasts  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--college", default="col_demo_001")
    ap.add_argument("--target", type=int, default=50_000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--minutes", type=float, default=15)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        b = broadcasts.start_broadcast(db, college_id=args.college, author_user_id="usr_kavitha_01", author_name="Benchmark",
                                       author_role="college", audience="both", batch_ids=None, title="Benchmark",
                                       body="Fan-out benchmark (rolled back)", post_to_groups=False)
        students = [u for u in db.execute(select(Student.user_id).where(Student.college_id == args.college)).scalars() if u]
        parents = sorted(set(db.execute(select(ParentStudent.parent_user_id).where(ParentStudent.college_id == args.college)).scalars()))
        t0 = time.perf_counter()
        sent = 0
        for i in range(0, len(students), broadcasts.CHUNK):
            sent += broadcasts.deliver_chunk(db, b.id, "student", students[i:i + broadcasts.CHUNK])
        sent += broadcasts.deliver_chunk(db, b.id, "parent", parents)
        db.flush()
        elapsed = time.perf_counter() - t0
    finally:
        db.rollback()
        db.close()

    rate = sent / elapsed if elapsed else 0
    projected_min = args.target / (rate * args.workers) / 60 if rate else float("inf")
    print(f"delivered {sent} notifications in {elapsed:.2f}s on one worker: {rate:.0f}/s ({broadcasts.CHUNK} per chunk)")
    print(f"projected {args.target:,} recipients with {args.workers} worker(s): {projected_min:.1f} min (target {args.minutes} min)")
    ok = projected_min <= args.minutes
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
