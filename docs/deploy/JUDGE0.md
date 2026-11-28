# Judge0: the coding lab's code runner

The coding lab (screen 24) runs student code in [Judge0 CE](https://github.com/judge0/judge0) 1.13.1, behind `services/judge0_service.py`.

- `JUDGE0_ADAPTER=fake` (the default) never runs code. Run and Submit pattern-match, for CI only. The Terminal says "the code runner is not set up".
- `JUDGE0_ADAPTER=judge0` runs everything for real.

Judge0 runs untrusted code. It must never run on the database host (CLAUDE.md rule 10), and any shared use needs a person's review.

## What runs where

| Action | What Judge0 runs | How it is judged |
|---|---|---|
| **Terminal** ("Run with my input") | The student's program as written, any of Python 3, Java (class `Main`), C++ or Node.js, with their input as stdin | Not judged; stdout, stderr and compiler output are shown |
| **Run** (sample tests) and **Submit** (all tests) on a *function* problem (the LeetCode-style seeded ones) | The student's class plus the judge driver (`services/code_harness.py`), which parses `nums = [2,7], target = 9`, builds linked lists and trees, calls the method and prints compact JSON | `outputs_match`: equal JSON values, spacing ignored. Python only for now. |
| **Run** and **Submit** on a *stdio* problem (trainer-made) | The student's program, reading stdin | `outputs_match` |

`tests/test_code_harness.py` runs every seeded problem's reference answer through the driver and checks every expected output, including the 18 hidden tests.

## Development setup

```bash
cp infra/judge0/judge0.conf.example infra/judge0/judge0.conf     # set the passwords and AUTHN_TOKEN; never commit it
docker compose -f infra/judge0/docker-compose.yml up -d
curl -H "X-Auth-Token: <AUTHN_TOKEN>" http://localhost:2358/languages    # 71 Python, 62 Java, 54 C++, 63 JavaScript
```

Then start the API with:

```bash
JUDGE0_ADAPTER=judge0 JUDGE0_URL=http://localhost:2358 JUDGE0_AUTH_TOKEN=<AUTHN_TOKEN> venv/Scripts/python -m uvicorn main:app --port 8000
```

**Docker Desktop on Windows (WSL 2):** Judge0 1.13's sandbox (`isolate`) expects cgroup v1, and WSL 2 uses cgroup v2 by default. When that bites, every submission comes back as *Internal Error*, and the Terminal shows "Unavailable". The workaround reported by Judge0 users is to boot WSL with cgroup v1: set `kernelCommandLine` in `%UserProfile%\.wslconfig` and run `wsl --shutdown`. Check the current Judge0 issues before relying on it. A Linux VM avoids the problem.

## Production

Production runs Judge0 on its own node, with no database, no secrets and a firewall that allows only the API.

- `ENVIRONMENT=production` refuses `JUDGE0_ADAPTER=fake` unless `judge0` is listed in `ALLOW_DEMO_ADAPTERS` (`core/production.py`).
- Production needs `JUDGE0_URL` and `JUDGE0_AUTH_TOKEN`.
- Keep `ENABLE_NETWORK=false` and `ALLOW_ENABLE_NETWORK=false`.

## Not done yet

- Judging Java, C++ and Node.js on function problems: each needs a per-language driver. Until then those problems are judged in Python, and the other languages run in the Terminal.
- Batched submissions: Submit sends one request per test case.
- A per-student rate limit on the Terminal.
