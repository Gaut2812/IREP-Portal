"""Drain the outbox without a broker (demo VM, debugging, cron).

    python -m irep_workers.run_outbox            # one pass
    python -m irep_workers.run_outbox --loop     # poll every OUTBOX_POLL_SECONDS
"""
import argparse
import time

import irep_workers  # noqa: F401  (puts apps/api on sys.path)

from core.config import settings
from core.database import SessionLocal
from services.outbox import dispatch_pending


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()
    while True:
        counts = dispatch_pending(SessionLocal, limit=args.limit)
        if any(counts.values()):
            print(counts, flush=True)
        if not args.loop:
            return
        time.sleep(settings.OUTBOX_POLL_SECONDS)


if __name__ == "__main__":
    main()
