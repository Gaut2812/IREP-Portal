# Screen 47 · Usage and quotas (IREP staff), and the S12 labs work

**Sprint:** S12 (quotas). Full billing (invoices and lab usage on invoices) is S16.
**Routes:** `/admin/usage` (47). `GET /college/usage` gives a college its own totals.

## Links

| Link | Direction | What moves | Status |
| --- | --- | --- | --- |
| L36 | 47 → 29, 25, 08 | Quotas for lab hours, AI calls and recording storage | active |
| L23 | 47 → 20 | Usage figures in the MoU report | active: the report adds this month's lab minutes, AI calls and recording storage against quota |

## Where quotas come from

Quotas are terms of the college's **active MoU** (edited on 45, so every change is a new, audited MoU version). `services/quotas.py` is the one place that reads them:

| Screen | Quota | From the MoU | Without an MoU |
| --- | --- | --- | --- |
| 29 Virtual labs | lab minutes per student per month | `lab_hours_per_student` × 60 | 20 h |
| 25 Study Buddy | AI calls per student per day | `ai_calls_per_day` | 30 |
| 08 Live sessions | recording storage per college | `storage_gb` | 50 GB |

Cloud credits stay a per-student education allowance (100 a month).

- **29:** a launch that would pass the quota is refused (`quota`), and a session never runs past the minutes left.
- **25:** questions over the daily cap are refused (`quota`).
- **08:** a published recording records its size. When it does not fit, it is kept as `over_quota` and cannot be played ("ask your college").

## Screen 47

- IREP staff see every college (not the platform tenant) for a month. Each metric shows used against quota with ok, near (≥ 80%) or over. A filter shows only flagged colleges.
- College admins see their own totals (`/college/usage`). Both views are aggregates only.

## Labs work in S11 and S12 (see docs/labs/README.md)

- **Docker & Kubernetes profile:** Sysbox runtime only (`LAB_SYSBOX=1`). Docker and kind run without `--privileged`, and images come only through a docker.io pull-through cache, the lab network's only way out.
- **Cyber Range:** its own node and hub (`infra/cyber-range`). Juice Shop and DVWA sit on an internal network with no egress, and workstations have all capabilities dropped except `NET_RAW`.
  - The portal sends Cyber Range sessions only to `CYBER_RANGE_HUB_URL`. With JupyterHub set up but no range hub, launches are refused (`range_unavailable`); it never falls back to the shared lab hub.
  - Access needs trainer approval and the signed AUP (43). It now expires `LAB_APPROVAL_DAYS` (30) after approval, then the student requests again.
- **Isolation test** (`tests/test_lab_isolation.py`): CI loads both hub configs and compose files and fails if spawner limits, internal networks, the Sysbox-only profile or the range's isolation are weakened.
- **Launch storm** (`loadtest/lab_storm.py`): 300 launches in 5 minutes. Locally (fake adapter, SQLite) all 300 were accepted, p95 accept latency was 130 ms, and every session was ready. Against a real hub, time to ready is the number to watch.
  - The first run found duplicate user emails that broke sign-in for two accounts. Migration 0018 repairs duplicates and makes `users.email` unique.

## Acceptance tests

- **API:**
  - L36: a new MoU's quotas show on 29 (quota and lock message), 25 (cap) and 08 (storage); an over-quota recording is refused.
  - Staff see all colleges and colleges their own; role guards; 404 for unknown colleges and the platform tenant; month validation.
  - L23: the MoU report carries usage.
  - Cyber Range access expires and can be requested again.
  - The isolation tests.
- **E2E:** staff see the usage table and filter it; Tamil; role guard.
