# Judge0: review checklist

CLAUDE.md puts Judge0 in the list of changes that need a person's review, because it runs untrusted student code. This page gives the reviewer what to check and records what was checked when the code was written. It does not replace the review.

## What changed (28 Nov 2026)

| Area | Files |
|---|---|
| Dev runner | `infra/judge0/docker-compose.yml`, `infra/judge0/judge0.conf.example` (the real `judge0.conf` is git-ignored) |
| Adapter | `services/judge0_service.py`: `Judge0HttpAdapter._submit` and `run_program`; answers are compared in `services/code_harness.outputs_match` |
| Driver for LeetCode-style problems | `services/code_harness.py`: `wrap_python` (prelude + driver) and `make_stub` |
| Endpoints | `POST /student/coding/{id}/execute` (the terminal); `/run` and `/submit` now add the driver when the engine is real |
| Limits | the terminal allows 2 s between runs and 60 runs an hour per student (usage ledger `code_runs`) |

## Checked during the build

- [x] **Version.** The image is `judge0/judge0:1.13.1`, the release that fixed the 2024 sandbox-escape advisories in 1.13.0 and earlier. Re-check Judge0's security advisories before any deployment.
- [x] **No network for student code.** `enable_network: false` is sent with every submission, and the config sets `ENABLE_NETWORK=false` and `ALLOW_ENABLE_NETWORK=false`.
- [x] **Auth.** `AUTHN_HEADER`/`AUTHN_TOKEN` are required. The API sends `JUDGE0_AUTH_HEADER`/`JUDGE0_AUTH_TOKEN`, and production refuses Judge0 without a token (`core/production.py`).
- [x] **Not exposed.** Port 2358 is bound to `127.0.0.1` in dev. Judge0's Postgres and Redis publish no ports.
- [x] **Resource limits.** Per submission: CPU and wall time from the problem (the terminal allows up to 5 s CPU and 15 s wall), memory 256 MB, file size 1 MB, 60 processes. Per container: `mem_limit: 2g`, `cpus: 2`, `pids_limit: 512`, and log rotation.
- [x] **Timeout.** The API's HTTP timeout now outlasts Judge0's wall-time limit. Before, a slow but valid run was reported as "unavailable".
- [x] **Output.** stdout, stderr and compiler output are cut at 64 KB before they reach the browser.
- [x] **Hidden tests.** On a hidden test, the student sees "Test execution failed on hidden test." and never the input or the expected output.
- [x] **The driver runs only inside Judge0.** `tests/test_code_harness.py` runs only our own reference answers in a local subprocess, never student code.
- [x] **Secrets.** `infra/judge0/judge0.conf` is git-ignored, and only the `.example` file with `CHANGE_ME` values is committed.

## For the reviewer

- [ ] `privileged: true` is required by Judge0's `isolate` sandbox. Confirm this is acceptable on the target host. In production Judge0 must run on its **own VM**: no database, no secrets, firewall open only to the API (CLAUDE.md rule 10).
- [ ] Confirm the per-submission and per-container limits suit the expected class size. For example, 60 students pressing Run at once means about 60 queued jobs. Judge0's worker count is `COUNT` in `judge0.conf`, which defaults to the CPU count.
- [ ] Decide whether the rate limit (2 s apart, 60 an hour per student) is right for your classes.
- [ ] Pin the images by digest (`judge0/judge0@sha256:...`) for production.
- [ ] On Docker Desktop (Windows, WSL 2), check the cgroup v1 requirement noted in `docs/deploy/JUDGE0.md`.
- [ ] Run a live smoke test once Docker is running:
      `curl -H "X-Auth-Token: <token>" http://localhost:2358/languages`, then in the portal use the Coding lab terminal with Python, Java (class `Main`), C++ and Node.js, then Run and Submit on Two Sum.
- [ ] Try the obvious abuses in the terminal and confirm each is stopped by Judge0's limits, not by the API: an infinite loop, a fork bomb, reading `/etc/passwd`, and opening a socket.
