"""API load test (S8): concurrent reads of the busiest screens, with latency percentiles.

Run against a local or staging API (never production without a maintenance window):

    venv/Scripts/python loadtest/load_api.py --base http://localhost:8000/api/v1 --users 50 --seconds 60

It signs in the demo accounts once (local auth), then each virtual user loops over a
role-appropriate mix of GET endpoints. It prints p50/p95/p99 and the error rate per
endpoint and exits 1 when a threshold is missed (default: p95 under 800 ms, errors
under 1%). The plan's other load targets (300 lab launches in 5 minutes, 2,000 open
WebSockets, a 50,000-recipient broadcast) belong to the labs (S12) and broadcast (S14)
sprints and get their own scripts there.
"""
import argparse
import asyncio
import random
import statistics
import sys
import time
from collections import defaultdict

import httpx

ACCOUNTS = {
    "student": ("priya.r@demo.edu", "password123"),
    "trainer": ("arun.k@demo.edu", "password123"),
    "college": ("admin@demo.edu", "password123"),
}
MIX = {
    "student": ["/student/dashboard", "/student/courses", "/notifications", "/student/live"],
    "trainer": ["/trainer/dashboard", "/trainer/at-risk", "/trainer/reports", "/notifications"],
    "college": ["/college/overview", "/college/events", "/college/reports"],
}
WEIGHTS = {"student": 0.75, "trainer": 0.15, "college": 0.10}   # roughly the pilot's population


async def login(client: httpx.AsyncClient, role: str) -> str:
    ident, pw = ACCOUNTS[role]
    r = await client.post("/auth/login", json={"role": role, "identifier": ident, "password": pw})
    r.raise_for_status()
    return r.json()["access_token"]


async def user_loop(client, role, token, deadline, samples, errors, think):
    headers = {"Authorization": f"Bearer {token}"}
    rng = random.Random()
    while time.monotonic() < deadline:
        path = rng.choice(MIX[role])
        t0 = time.perf_counter()
        try:
            r = await client.get(path, headers=headers)
            ok = r.status_code < 500 and r.status_code != 429
        except httpx.HTTPError:
            ok = False
        ms = (time.perf_counter() - t0) * 1000
        samples[path].append(ms)
        if not ok:
            errors[path] += 1
        await asyncio.sleep(rng.uniform(0, think))


def pct(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost:8000/api/v1")
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--think", type=float, default=0.5, help="max think time between a user's requests (s)")
    ap.add_argument("--p95-ms", type=float, default=800)
    ap.add_argument("--max-error-pct", type=float, default=1.0)
    args = ap.parse_args()

    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    async with httpx.AsyncClient(base_url=args.base, timeout=30, limits=limits) as client:
        tokens = {role: await login(client, role) for role in ACCOUNTS}
        roles = random.Random(7).choices(list(WEIGHTS), weights=list(WEIGHTS.values()), k=args.users)
        samples, errors = defaultdict(list), defaultdict(int)
        deadline = time.monotonic() + args.seconds
        started = time.monotonic()
        await asyncio.gather(*(user_loop(client, r, tokens[r], deadline, samples, errors, args.think) for r in roles))
        elapsed = time.monotonic() - started

    total = sum(len(v) for v in samples.values())
    failed = sum(errors.values())
    print(f"{args.users} users, {elapsed:.0f}s, {total} requests, {total / elapsed:.1f} req/s, errors {failed}")
    print(f"{'endpoint':32} {'n':>6} {'p50':>8} {'p95':>8} {'p99':>8} {'err':>5}")
    worst = 0.0
    for path in sorted(samples):
        v = samples[path]
        p95 = pct(v, 95)
        worst = max(worst, p95)
        print(f"{path:32} {len(v):6d} {statistics.median(v):8.0f} {p95:8.0f} {pct(v, 99):8.0f} {errors[path]:5d}")
    err_pct = 100 * failed / total if total else 100
    ok = worst <= args.p95_ms and err_pct <= args.max_error_pct
    print(f"\nworst p95 {worst:.0f} ms (limit {args.p95_ms:.0f}), errors {err_pct:.2f}% (limit {args.max_error_pct}%): {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
