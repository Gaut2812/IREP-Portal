"""Lab launch storm (labs track, S11): Master Plan target "300 lab launches in 5 minutes".

Signs in N demo students, then launches a lab for each, spread over the window, through
the portal's labs service (entitlement, quota, outbox start). It measures:
- accept latency: POST /student/labs/{lab}/launch until the API answers;
- time to ready: until GET /student/lab-sessions/{id} reports "running" (with
  LAB_ADAPTER=jupyterhub the server starts after commit, through the outbox).
Every session it started is stopped at the end, even on failure.

Run against a local or staging stack, never production:

    venv/Scripts/python loadtest/lab_storm.py --base http://127.0.0.1:8000/api/v1 --students 300 --window 300

Exit code 1 when a target is missed (default: every launch accepted, p95 accept <= 2 s,
99% ready within --ready-timeout seconds).
"""
import argparse
import asyncio
import random
import statistics
import sys
import time

import httpx
from sqlalchemy import select


def demo_students(n: int, min_semester: int):
    """Students of the demo college who are entitled to the lab (semester), as (email, user_id)."""
    sys.path.insert(0, __file__.rsplit("loadtest", 1)[0])
    from core.database import SessionLocal
    from models.schema import Student, User
    with SessionLocal() as db:
        rows = db.execute(select(User.email).join(Student, Student.user_id == User.id)
                          .where(Student.college_id == "col_demo_001", Student.semester >= min_semester)
                          .order_by(User.email)).scalars().all()
    return rows[:n]


def pct(values, p):
    if not values:
        return 0.0
    v = sorted(values)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


async def run(args) -> int:
    emails = demo_students(args.students, args.min_semester)
    if len(emails) < args.students:
        print(f"only {len(emails)} entitled demo students; continuing with those")
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(base_url=args.base, timeout=60, limits=limits) as client:
        sem = asyncio.Semaphore(args.concurrency)

        async def login(email):
            async with sem:
                r = await client.post("/auth/login", json={"role": "student", "identifier": email, "password": args.password})
                r.raise_for_status()
                return r.json()["access_token"]

        tokens = await asyncio.gather(*(login(e) for e in emails))
        print(f"signed in {len(tokens)} students")

        accept, ready, outcomes, started = [], [], {}, []

        async def one(token, delay):
            await asyncio.sleep(delay)
            h = {"Authorization": f"Bearer {token}"}
            t0 = time.perf_counter()
            async with sem:
                r = await client.post(f"/student/labs/{args.lab}/launch", headers=h)
            accept.append((time.perf_counter() - t0) * 1000)
            key = str(r.status_code) if r.status_code != 200 else "accepted"
            if r.status_code in (403, 409):
                key += ":" + str((r.json().get("detail") or {}).get("reason", ""))
            outcomes[key] = outcomes.get(key, 0) + 1
            if r.status_code != 200:
                return
            sid = r.json()["session"]["id"]
            started.append((sid, h))
            deadline = t0 + args.ready_timeout
            while time.perf_counter() < deadline:
                s = (await client.get(f"/student/lab-sessions/{sid}", headers=h)).json()
                if s.get("status") == "running":
                    ready.append(time.perf_counter() - t0)
                    return
                if s.get("status") in ("failed", "stopped", "expired"):
                    outcomes["failed_to_start"] = outcomes.get("failed_to_start", 0) + 1
                    return
                await asyncio.sleep(2)
            outcomes["not_ready_in_time"] = outcomes.get("not_ready_in_time", 0) + 1

        rng = random.Random(42)
        t_start = time.monotonic()
        try:
            await asyncio.gather(*(one(tok, rng.uniform(0, args.window)) for tok in tokens))
        finally:
            for sid, h in started:                       # always clean up
                try:
                    await client.post(f"/student/lab-sessions/{sid}/stop", headers=h)
                except httpx.HTTPError:
                    pass
        elapsed = time.monotonic() - t_start

    accepted = outcomes.get("accepted", 0)
    print(f"\n{len(tokens)} launches over {elapsed:.0f}s ({args.lab})")
    for k in sorted(outcomes):
        print(f"  {k:28} {outcomes[k]}")
    if accept:
        print(f"accept latency ms: p50 {statistics.median(accept):.0f}  p95 {pct(accept, 95):.0f}  p99 {pct(accept, 99):.0f}")
    if ready:
        print(f"time to ready s:   p50 {statistics.median(ready):.1f}  p95 {pct(ready, 95):.1f}  max {max(ready):.1f}")
    ready_rate = 100 * len(ready) / accepted if accepted else 0
    ok = (accepted == len(tokens) and pct(accept, 95) <= args.p95_accept_ms and ready_rate >= args.min_ready_pct)
    print(f"\naccepted {accepted}/{len(tokens)}, ready {ready_rate:.1f}% (limit {args.min_ready_pct}%), "
          f"p95 accept {pct(accept, 95):.0f} ms (limit {args.p95_accept_ms:.0f}): {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--students", type=int, default=300)
    ap.add_argument("--window", type=float, default=300, help="spread launches over this many seconds")
    ap.add_argument("--lab", default="lab_linux")
    ap.add_argument("--min-semester", type=int, default=2)
    ap.add_argument("--password", default="password123")
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--ready-timeout", type=float, default=180)
    ap.add_argument("--p95-accept-ms", type=float, default=2000)
    ap.add_argument("--min-ready-pct", type=float, default=99.0)
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
